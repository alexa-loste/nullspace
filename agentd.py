"""The agent as an entity.

An agent belongs to one scientist, holds their profile and open problems, and
decides for itself what to do next. Nothing here is called with "run the
pipeline": you tick an agent and it picks the most useful thing it can do.

Actions, in the order an agent prefers them:

  scout     an open problem with no brief   -> search, explain, name people
  broadcast a scouted problem, not yet sent -> restate it for other fields
  respond   another agent's broadcast       -> can my scientist actually help?
  broker    a response nobody has acted on  -> introduce the two humans

Everything an agent does lands in its scientist's inbox as an event, because
the point is that the work happened while the scientist was elsewhere.
"""

import agents
import litsearch
import pipeline
import store


class Agent:
    def __init__(self, scientist_id):
        self.sid = scientist_id
        self.sci = store.get("scientists", scientist_id)
        if not self.sci:
            raise ValueError(f"no scientist {scientist_id}")

    # ------------------------------------------------------------ memory
    @property
    def name(self):
        return self.sci.get("agent_name") or "agent"

    def profile(self):
        """What this agent knows about its own scientist."""
        k = ("name", "field", "institution", "adjacent_fields", "techniques",
             "equipment", "can_offer", "interests")
        return {x: self.sci.get(x) for x in k if self.sci.get(x)}

    def problems(self, status="open"):
        ps = store.where("problems", scientist_id=self.sid)
        return [p for p in ps if not status or p.get("status") == status]

    def problem_summaries(self):
        return [
            {"title": p["card"].get("title"), "field": p["card"].get("field"),
             "open_questions": p["card"].get("open_questions", [])}
            for p in self.problems()
        ]

    # ------------------------------------------------------------ deciding
    def next_action(self):
        """The most useful thing this agent could do right now, or None."""
        for p in self.problems():
            if not p.get("brief_id"):
                return ("scout", p, f"{(p['card'].get('title') or 'a problem')[:60]} has not been looked into")
        # Checking its own old reasoning against what the field went on to
        # publish comes before asking anyone else, because the answer may
        # already be in print and there is no point broadcasting a solved one.
        for p in self.problems():
            if p.get("brief_id") and p.get("as_of"):
                b = store.get("briefs", p["brief_id"]) or {}
                if not b.get("since"):
                    return ("recheck", p,
                            f"it reasoned as of {p['as_of']}; the field has had time to answer")
        for p in self.problems():
            if p.get("brief_id") and not p.get("signal_id"):
                return ("broadcast", p, "scouted but no one else has been asked")

        judged = {r.get("signal_id") for r in store.where("matches", responder_id=self.sid)}
        for sig in store.all_of("signals"):
            if sig.get("scientist_id") == self.sid or sig["id"] in judged:
                continue
            return ("respond", sig, f"another agent asked about {(sig.get('headline') or 'an unexplained result')[:50]}")

        for m in store.where("matches", asker_id=self.sid, brokered=False):
            if m.get("can_help"):
                return ("broker", m, "a match is waiting to be introduced")
        return None

    # ------------------------------------------------------------ acting
    def tick(self, on_progress=None):
        """Do one thing. Returns a short record of what happened, or None."""
        nxt = self.next_action()
        if not nxt:
            return None
        action, target, reason = nxt
        say = on_progress or (lambda *a, **k: None)
        say(f"{self.name}: {reason}")
        return getattr(self, f"do_{action}")(target, say)

    # -- scout ---------------------------------------------------------
    def do_scout(self, prob, say):
        card = prob["card"]
        # A problem carrying `as_of` is one whose fate the field has already
        # decided. The agent is held to the literature of the time, so that
        # what it concludes can be checked afterwards rather than taken on
        # trust. Everything else sees the literature as it stands today.
        as_of = prob.get("as_of")
        say(f"{self.name}: choosing searches for “{(card.get('title') or '')[:50]}”")
        qs = agents.queries(card).get("queries", [])
        for q in qs:
            say(f"    [{q.get('kind','?')}] {q.get('q','')}", data={"query": q})

        say(f"{self.name}: searching the literature"
            + (f", nothing published after {as_of}" if as_of else ""))
        papers = litsearch.multi_search([q["q"] for q in qs if q.get("q")],
                                        to_year=as_of)
        for p in papers[:12]:
            say(f"    {p.get('year')} · {(p.get('title') or '')[:70]}", data={"paper": p})
        say(f"{self.name}: {len(papers)} papers; working out what they mean")

        analysis = pipeline.resolve_refs(
            agents.recontextualize(card, papers, as_of=as_of), papers)
        contacts, rejected = pipeline.verify_contacts(
            agents.connect(card, analysis, papers).get("contacts", []), papers)

        brief = store.put("briefs", {
            "id": store.new_id("brf_"),
            "problem_id": prob["id"], "scientist_id": self.sid,
            "card": card, "queries": qs, "papers": papers,
            "analysis": analysis, "contacts": contacts, "rejected_contacts": rejected,
            "as_of": as_of,
        })
        if prob.get("truth"):
            brief["score"] = agents.score_against_truth(analysis, prob["truth"])
            brief["truth"] = prob["truth"]
            store.put("briefs", brief)

        store.patch("problems", prob["id"], brief_id=brief["id"])
        top = (analysis.get("hypotheses") or [{}])[0]
        store.event(self.sid, "scouted",
                    f"I looked into “{(card.get('title') or 'your result')[:70]}”",
                    top.get("claim", ""), problem_id=prob["id"],
                    brief_id=brief["id"], actionable=True)
        say(f"{self.name}: brief ready, {len(analysis.get('hypotheses',[]))} explanations")
        return {"action": "scout", "brief_id": brief["id"], "problem_id": prob["id"]}

    # -- recheck -------------------------------------------------------
    def do_recheck(self, prob, say):
        """Go back to a null it explained as-of a date and see what happened."""
        card, as_of = prob["card"], prob.get("as_of")
        brief = store.get("briefs", prob["brief_id"]) or {}
        analysis = brief.get("analysis") or {}
        say(f"{self.name}: looking for work published since {as_of}")
        qs = [q["q"] for q in (brief.get("queries") or []) if q.get("q")][:5]
        if not qs:
            qs = [card.get("title") or ""]
        newer = litsearch.multi_search(qs, from_year=(as_of or 0) + 1, cap=24)
        for p in newer[:10]:
            say(f"    {p.get('year')} · {(p.get('title') or '')[:70]}", data={"paper": p})
        if not newer:
            say(f"{self.name}: nothing published since. The question is still open.")
            since = {"verdicts": [], "overall": "open", "agent_was_right": None,
                     "what_the_field_did": "Nothing retrieved was published after "
                                           f"{as_of} that bears on this.",
                     "best_missed": None, "papers": []}
        else:
            say(f"{self.name}: {len(newer)} newer papers; checking its own reasoning")
            since = agents.check_since(card, analysis, newer, as_of=as_of)
            # Same discipline as a citation: an index that is not in the list
            # we handed over is dropped rather than shown.
            for v in since.get("verdicts") or []:
                v["papers"] = [newer[i] for i in (v.get("papers") or [])
                               if isinstance(i, int) and 0 <= i < len(newer)]
            since["papers"] = newer
        brief["since"] = since
        store.put("briefs", brief)
        verdict = since.get("overall", "open")
        # The moment the product stops being somewhere you go and becomes
        # something that comes to you. A null nobody was thinking about has
        # become answerable, and the only person who can act on that is the
        # one who shelved it.
        scooped = since.get("someone_else_published_it")
        if scooped:
            head = f"Someone else published this: “{(card.get('title') or '')[:52]}”"
        elif verdict == "resolved":
            head = f"You can revisit this now — “{(card.get('title') or '')[:52]}”"
        elif verdict == "narrowed":
            head = f"The question got sharper — “{(card.get('title') or '')[:52]}”"
        else:
            head = f"Still open — “{(card.get('title') or '')[:52]}”"
        store.event(self.sid, "revisit" if verdict != "open" else "scouted",
                    head, since.get("what_the_field_did", ""),
                    problem_id=prob["id"], brief_id=brief["id"],
                    actionable=verdict != "open")
        say(f"{self.name}: {verdict}"
            + (" — and its own top explanation held up" if since.get("agent_was_right")
               else " — its own top explanation did not hold up"
               if since.get("agent_was_right") is False else ""))
        return {"action": "recheck", "problem_id": prob["id"], "overall": verdict}

    # -- broadcast -----------------------------------------------------
    def do_broadcast(self, prob, say):
        say(f"{self.name}: restating this so other fields recognise it")
        b = agents.broadcast(prob["card"], self.profile())
        if not b.get("headline"):
            # An empty broadcast would sit in the network saying nothing and
            # every other agent would judge it. Leave the problem unbroadcast
            # so the next tick tries again.
            say(f"{self.name}: the restatement came back empty, leaving it for next time")
            return {"action": "broadcast", "signal_id": None, "empty": True}
        sig = store.put("signals", {
            "id": store.new_id("sig_"),
            "scientist_id": self.sid, "problem_id": prob["id"],
            "headline": b.get("headline"), "plain": b.get("plain"),
            "restatements": b.get("restatements", []),
            "asks": b.get("asks", []), "offers": b.get("offers", []),
        })
        store.patch("problems", prob["id"], signal_id=sig["id"])
        for r in b.get("restatements", [])[:4]:
            say(f"    for {r.get('field')}: {r.get('as_they_would_say_it','')[:80]}")
        store.event(self.sid, "note",
                    "I asked other fields about your result",
                    b.get("headline", ""), problem_id=prob["id"], signal_id=sig["id"])
        return {"action": "broadcast", "signal_id": sig["id"]}

    # -- respond -------------------------------------------------------
    def do_respond(self, sig, say):
        asker = store.get("scientists", sig["scientist_id"])
        say(f"{self.name}: can {self.sci['name']} help with this?")
        r = agents.respond(sig, self.profile(), self.problem_summaries())
        m = store.put("matches", {
            "id": store.new_id("mch_"),
            "signal_id": sig["id"], "problem_id": sig.get("problem_id"),
            "asker_id": sig["scientist_id"], "responder_id": self.sid,
            "can_help": bool(r.get("can_help")), "response": r, "brokered": False,
        })
        if r.get("can_help"):
            say(f"    yes: {r.get('specifically','')[:90]}")
            store.event(sig["scientist_id"], "match",
                        f"{self.sci['name']} can help with your result",
                        r.get("specifically", ""), match_id=m["id"],
                        problem_id=sig.get("problem_id"), actionable=True)
            store.event(self.sid, "request",
                        f"You can help {asker['name'] if asker else 'another lab'}",
                        r.get("specifically", ""), match_id=m["id"], actionable=True)
        else:
            say(f"    no: {r.get('why_not','')[:90]}")
        return {"action": "respond", "match_id": m["id"], "can_help": m["can_help"]}

    # -- broker --------------------------------------------------------
    def do_broker(self, m, say):
        asker = store.get("scientists", m["asker_id"])
        responder = store.get("scientists", m["responder_id"])
        sig = store.get("signals", m["signal_id"])
        say(f"{self.name}: introducing {asker['name']} and {responder['name']}")
        intro = agents.broker(sig, asker, responder, m.get("response", {}))
        store.patch("matches", m["id"], brokered=True, intro=intro)
        for sid_, who in ((m["asker_id"], responder), (m["responder_id"], asker)):
            store.event(sid_, "match", f"Introduction drafted: {who['name']}",
                        intro.get("why_this_works", ""), match_id=m["id"],
                        actionable=True)
        return {"action": "broker", "match_id": m["id"]}


# ------------------------------------------------------------------ world

def all_agents():
    return [Agent(s["id"]) for s in store.all_of("scientists")]


def world_tick(rounds=1, on_progress=None, only=None):
    """Tick every agent. This is what makes the thing feel alive."""
    done = []
    for _ in range(rounds):
        moved = False
        for a in all_agents():
            if only and a.sid not in only:
                continue
            r = a.tick(on_progress=on_progress)
            if r:
                done.append({"scientist_id": a.sid, **r})
                moved = True
        if not moved:
            break
    return done


def react_to(scientist_id, on_progress=None):
    """Let every other agent judge this scientist's open broadcasts.

    Without this a scientist logs a result, their agent broadcasts, and the
    network stays silent until something else ticks. The point of the thing is
    that other agents answer, so answering has to follow broadcasting.
    """
    say = on_progress or (lambda *a, **k: None)
    mine = [s for s in store.all_of("signals") if s["scientist_id"] == scientist_id]
    if not mine:
        return []
    done = []
    others = [a for a in all_agents() if a.sid != scientist_id]
    say(f"asking {len(others)} other agents about your result")
    for sig in mine:
        judged = {m["responder_id"] for m in store.where("matches", signal_id=sig["id"])}
        for a in others:
            if a.sid in judged:
                continue
            done.append({"scientist_id": a.sid, **a.do_respond(sig, say)})
    # Introduce anyone who said yes.
    for m in store.where("matches", asker_id=scientist_id, brokered=False):
        if m.get("can_help"):
            done.append({"scientist_id": scientist_id,
                         **Agent(scientist_id).do_broker(m, say)})
    return done


def work_for(scientist_id, rounds=3, on_progress=None):
    """One scientist pressing 'let my agent work'.

    Their agent acts, and then the rest of the network answers whatever it put
    out. This is the loop a user actually experiences.
    """
    done = world_tick(rounds=rounds, on_progress=on_progress, only={scientist_id})
    done += react_to(scientist_id, on_progress=on_progress)
    return done


def pending(only=None):
    """What every agent would do next, without doing it."""
    out = []
    for a in all_agents():
        if only and a.sid not in only:
            continue
        n = a.next_action()
        if n:
            out.append({"scientist_id": a.sid, "agent": a.name,
                        "action": n[0], "reason": n[2]})
    return out
