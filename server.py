"""Nullspace server. Standard library only.

    python3 server.py        # http://localhost:8799  (PORT overrides)

Two things worth knowing:

* One worker thread runs every agent job. Claude runs through the CLI on one
  personal subscription, so concurrent invocations are untested; jobs queue and
  the client is told its position rather than finding out the hard way.
* Jobs stream. A job's `log` and `partial` fill as the agent works, so the
  client can show queries and retrieved papers during the wait instead of a
  spinner.
"""

import json
import mimetypes
import os
import pathlib
import queue
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import agentd
import agents
import examples
import store

ROOT = pathlib.Path(__file__).parent
STATIC = ROOT / "static"
PORT = int(os.environ.get("PORT") or 8799)

JOBS = {}
JOBS_LOCK = threading.Lock()
WORK = queue.Queue()


# ------------------------------------------------------------------ jobs

def submit(fn, *a, **kw):
    jid = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[jid] = {"status": "queued", "log": [], "partial": {}, "result": None,
                     "error": None, "position": WORK.qsize() + 1}
    WORK.put((jid, fn, a, kw))
    return jid


def _say(jid):
    def say(msg, data=None):
        with JOBS_LOCK:
            j = JOBS.get(jid)
            if not j:
                return
            j["log"].append(msg)
            if data:
                for k, v in data.items():
                    j["partial"].setdefault(k + "s", []).append(v)
    return say


def worker():
    while True:
        jid, fn, a, kw = WORK.get()
        with JOBS_LOCK:
            JOBS[jid]["status"] = "running"
            JOBS[jid]["position"] = 0
        try:
            if kw.pop("_wants_progress", False):
                kw["on_progress"] = _say(jid)
            res = fn(*a, **kw)
            with JOBS_LOCK:
                JOBS[jid].update(result=res, status="done")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            with JOBS_LOCK:
                JOBS[jid].update(error=f"{type(exc).__name__}: {exc}", status="error")
        finally:
            WORK.task_done()
            with JOBS_LOCK:
                for n, (q_jid, *_rest) in enumerate(list(WORK.queue), start=1):
                    if q_jid in JOBS:
                        JOBS[q_jid]["position"] = n


threading.Thread(target=worker, daemon=True).start()


# ------------------------------------------------------------------ scheduler
# "Your agent worked while you were away" was only true inside a session, which
# made the central claim of the product a figure of speech. This makes it
# literal. It only ever submits when the queue is empty, so a background tick
# can never put a person behind a robot: the one worker is shared.

SCHED = {"on": False, "every": 180, "last": 0, "runs": 0, "last_action": None}


def scheduler():
    while True:
        time.sleep(5)
        if not SCHED["on"]:
            continue
        if time.time() - SCHED["last"] < SCHED["every"]:
            continue
        if WORK.qsize() or any(j["status"] == "running" for j in JOBS.values()):
            continue
        try:
            todo = agentd.pending()
        except Exception:  # noqa: BLE001
            continue
        if not todo:
            continue
        SCHED["last"] = time.time()
        SCHED["runs"] += 1
        SCHED["last_action"] = todo[0].get("action")
        submit(agentd.world_tick, rounds=1, _wants_progress=True)


threading.Thread(target=scheduler, daemon=True).start()


# ------------------------------------------------------------------ views

def agent_card(s):
    probs = store.where("problems", scientist_id=s["id"])
    return {
        "id": s["id"], "name": s["name"], "field": s["field"],
        "agent_name": s.get("agent_name"), "institution": s.get("institution"),
        "demo_persona": s.get("demo_persona", False), "lab": s.get("lab"),
        "techniques": s.get("techniques", []), "equipment": s.get("equipment", []),
        "can_offer": s.get("can_offer", []), "adjacent_fields": s.get("adjacent_fields", []),
        "n_problems": len(probs),
        "n_open": sum(1 for p in probs if p.get("status") == "open"),
    }


def brief_view(b):
    if not b:
        return None
    a = b.get("analysis") or {}
    return {
        "id": b["id"], "problem_id": b.get("problem_id"),
        "card": b.get("card"), "queries": b.get("queries", []),
        "n_papers": len(b.get("papers") or []),
        "papers": b.get("papers", []),
        "verdict": a.get("verdict"), "hypotheses": a.get("hypotheses", []),
        "what_was_not_retrieved": a.get("what_was_not_retrieved"),
        "dropped_citations": a.get("_dropped_citations", 0),
        "contacts": b.get("contacts", []), "rejected_contacts": b.get("rejected_contacts", []),
        "score": b.get("score"), "truth": b.get("truth"),
        "since": b.get("since"), "as_of": b.get("as_of"),
        "created": b.get("created"),
    }


def match_view(m):
    if not m:
        return None
    asker = store.get("scientists", m["asker_id"])
    resp = store.get("scientists", m["responder_id"])
    sig = store.get("signals", m["signal_id"])
    return {
        "id": m["id"], "can_help": m.get("can_help"), "brokered": m.get("brokered"),
        "response": m.get("response", {}), "intro": m.get("intro"),
        "asker": agent_card(asker) if asker else None,
        "responder": agent_card(resp) if resp else None,
        "signal": sig, "problem_id": m.get("problem_id"),
        "created": m.get("created"),
    }


# ------------------------------------------------------------------ http

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _me(self):
        tok = self.headers.get("X-Token") or ""
        return store.by_token(tok) if tok else None

    def json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def file(self, p):
        if not p.is_file():
            return self.json({"error": "not found"}, 404)
        body = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(p.name)[0] or "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    # -------------------------------------------------------------- GET
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p, me = u.path, self._me()

        if p in ("/", "/index.html"):
            return self.file(STATIC / "index.html")

        if p == "/api/me":
            if not me:
                return self.json({"scientist": None,
                                  "world": [agent_card(s) for s in store.all_of("scientists")]})
            return self.json({
                "scientist": agent_card(me), "token": me["token"],
                "unread": store.unread_count(me["id"]),
                "pending": agentd.pending(only={me["id"]}),
                "schedule": dict(SCHED),
                "world": [agent_card(s) for s in store.all_of("scientists")
                          if s["id"] != me["id"]],
            })

        if p == "/api/inbox":
            if not me:
                return self.json({"error": "no scientist"}, 401)
            return self.json({"events": store.inbox(me["id"])})

        if p == "/api/problems":
            if not me:
                return self.json({"error": "no scientist"}, 401)
            return self.json({"problems": store.where("problems", scientist_id=me["id"])})

        if p == "/api/shelf":
            # Everything shelved in your lab, which is what a student inheriting
            # a project needs to see. Falls back to your own if you have no lab.
            if not me:
                return self.json({"error": "no scientist"}, 401)
            full = store.get("scientists", me["id"]) or {}
            lab = full.get("lab")
            members = [s for s in store.all_of("scientists")
                       if (s.get("lab") == lab if lab else s["id"] == me["id"])]
            rows = []
            for s in members:
                for pr in store.where("problems", scientist_id=s["id"]):
                    b = store.get("briefs", pr["brief_id"]) if pr.get("brief_id") else None
                    a = (b or {}).get("analysis") or {}
                    hs = a.get("hypotheses") or []
                    card = pr["card"]
                    newer = 0
                    if b and card.get("year"):
                        newer = sum(1 for x in (b.get("papers") or [])
                                    if (x.get("year") or 0) > card["year"])
                    # Status the agent assigns from what it found, not a label
                    # the scientist has to pick. Each one implies a next move.
                    top_kind = hs[0].get("kind") if hs else None
                    status = ("unread" if not b
                              else "answered" if top_kind == "already_known"
                              else "blocked" if top_kind == "artifact"
                              else "open")
                    rows.append({
                        "id": pr["id"], "title": card.get("title"),
                        "project": card.get("project"),
                        "project_context": card.get("project_context"),
                        "field": card.get("field"), "year": card.get("year"),
                        "result_type": card.get("result_type"), "status": status,
                        "owner": s["name"], "owner_id": s["id"], "is_mine": s["id"] == me["id"],
                        "scouted": bool(b), "brief_id": pr.get("brief_id"),
                        "n_hypotheses": len(hs), "n_papers": len(b.get("papers") or []) if b else 0,
                        "top_kind": (hs[0].get("kind") if hs else None),
                        "n_newer": newer,
                        "n_matches": sum(1 for m in store.where("matches", problem_id=pr["id"])
                                         if m.get("can_help")),
                        "flags": len(card.get("quality_flags") or []),
                        "visibility": pr.get("visibility", "lab"),
                        "confidence": pr.get("confidence"),
                        "n_cosigns": len(pr.get("cosigns") or []),
                        "origin": pr.get("origin", "logged"),
                        "unclaimed": pr.get("unclaimed", False),
                        "has_pickup": bool(pr.get("pickup")),
                    })
            rows.sort(key=lambda r: (-(r["year"] or 0), r["title"] or ""))
            return self.json({"lab": lab, "members": len(members), "rows": rows})

        if p == "/api/home":
            # What a person needs on landing: what their agent did without them,
            # what is waiting on them, and the one next thing worth doing.
            if not me:
                return self.json({"error": "no scientist"}, 401)
            full = store.get("scientists", me["id"]) or {}
            lab = full.get("lab")
            members = [s for s in store.all_of("scientists")
                       if (s.get("lab") == lab if lab else s["id"] == me["id"])]
            mine_probs = store.where("problems", scientist_id=me["id"])
            lab_probs = [pr for s in members
                         for pr in store.where("problems", scientist_id=s["id"])]
            unread_lit, needs_read, never_shared, unclaimed = 0, [], [], []
            for pr in lab_probs:
                b = store.get("briefs", pr["brief_id"]) if pr.get("brief_id") else None
                card = pr["card"]
                if not b:
                    needs_read.append({"id": pr["id"], "title": card.get("title"),
                                       "mine": pr["scientist_id"] == me["id"]})
                elif card.get("year"):
                    unread_lit += sum(1 for x in (b.get("papers") or [])
                                      if (x.get("year") or 0) > card["year"])
                if pr.get("unclaimed"):
                    unclaimed.append({"id": pr["id"], "title": card.get("title")})
                elif (pr["scientist_id"] == me["id"]
                      and pr.get("visibility", "lab") == "lab" and b):
                    never_shared.append({"id": pr["id"], "title": card.get("title")})
            evs = [e for e in store.inbox(me["id"], limit=12)]
            return self.json({
                "lab": lab, "members": len(members),
                "n_mine": len(mine_probs), "n_lab": len(lab_probs),
                "n_new_papers": unread_lit,
                "needs_read": needs_read[:5],
                "never_shared": never_shared[:5],
                "unclaimed": unclaimed[:5],
                "events": evs,
                "unread": store.unread_count(me["id"]),
                "pending": agentd.pending(only={me["id"]}),
                "n_can_help": sum(1 for m in store.where("matches", responder_id=me["id"])
                                  if m.get("can_help")),
            })

        if p == "/api/record":
            # Credit is the whole long-run argument, so it has to be visible even
            # while it is only a count. Every line here is something they did.
            if not me:
                return self.json({"error": "no scientist"}, 401)
            probs = store.where("problems", scientist_id=me["id"])
            answered = [m for m in store.where("matches", responder_id=me["id"])
                        if m.get("can_help")]
            cosigned = [pr for pr in store.all_of("problems")
                        if any(c.get("scientist_id") == me["id"]
                               for c in (pr.get("cosigns") or []))]
            shared = [pr for pr in probs if pr.get("visibility", "lab") != "lab"]
            return self.json({
                "scientist": agent_card(me),
                "logged": [{"id": pr["id"], "title": pr["card"].get("title"),
                            "year": pr["card"].get("year"),
                            "visibility": pr.get("visibility", "lab"),
                            "cosigns": len(pr.get("cosigns") or [])} for pr in probs],
                "answered": [{"id": m["id"],
                              "what": (m.get("response") or {}).get("specifically"),
                              "asker": (store.get("scientists", m["asker_id"]) or {}).get("name")}
                             for m in answered],
                "cosigned": [{"id": pr["id"], "title": pr["card"].get("title"),
                              "owner": (store.get("scientists", pr["scientist_id"]) or {}).get("name")}
                             for pr in cosigned],
                "n_shared": len(shared),
            })

        if p == "/api/problem":
            pr = store.get("problems", (q.get("id") or [""])[0])
            if not pr:
                return self.json({"error": "not found"}, 404)
            owner = store.get("scientists", pr["scientist_id"])
            # Who this could be handed to: the reader's own lab. A handover
            # across labs is a collaboration, which is a different thing.
            mylab = (store.get("scientists", me["id"]) or {}).get("lab") if me else None
            mates = [agent_card(s) for s in store.all_of("scientists")
                     if mylab and s.get("lab") == mylab and me and s["id"] != me["id"]]
            return self.json({
                "problem": pr,
                "brief": brief_view(store.get("briefs", pr["brief_id"])) if pr.get("brief_id") else None,
                "signal": store.get("signals", pr["signal_id"]) if pr.get("signal_id") else None,
                "matches": [match_view(m) for m in store.where("matches", problem_id=pr["id"])],
                "scientist": agent_card(owner),
                "labmates": mates,
            })

        if p == "/api/brief":
            return self.json({"brief": brief_view(store.get("briefs", (q.get("id") or [""])[0]))})

        if p == "/api/match":
            return self.json({"match": match_view(store.get("matches", (q.get("id") or [""])[0]))})

        if p == "/api/answerable":
            # The repository read from outside: every null anyone can see,
            # ranked by how much the field has moved since it was shelved.
            # This is the view somebody looking for a project opens, and the
            # one a PI scans. It is also the only screen that needs more than
            # one lab to make sense.
            if not me:
                return self.json({"error": "no scientist"}, 401)
            full = store.get("scientists", me["id"]) or {}
            my_lab = full.get("lab")
            rows = []
            for pr in store.all_of("problems"):
                owner = store.get("scientists", pr["scientist_id"]) or {}
                vis = pr.get("visibility", "lab")
                mine_lab = owner.get("lab") == my_lab
                if vis == "lab" and not mine_lab:
                    continue
                b = store.get("briefs", pr["brief_id"]) if pr.get("brief_id") else None
                card = pr["card"]
                since = (b or {}).get("since") or {}
                newer = 0
                if b and card.get("year"):
                    newer = sum(1 for x in (b.get("papers") or [])
                                if (x.get("year") or 0) > card["year"])
                newer += len(since.get("papers") or [])
                hs = ((b or {}).get("analysis") or {}).get("hypotheses") or []
                rows.append({
                    "id": pr["id"], "title": card.get("title"),
                    "year": card.get("year"), "as_of": pr.get("as_of"),
                    "field": card.get("field"),
                    "owner": owner.get("name"), "lab": owner.get("lab"),
                    "same_lab": mine_lab, "visibility": vis,
                    "origin": pr.get("origin", "logged"),
                    "unclaimed": pr.get("unclaimed", False),
                    "assigned_to": pr.get("assigned_to_name"),
                    "n_newer": newer, "n_explanations": len(hs),
                    "read": bool(b),
                    "overall": since.get("overall"),
                    "what_the_field_did": since.get("what_the_field_did"),
                    "agent_was_right": since.get("agent_was_right"),
                    "has_pickup": bool(pr.get("pickup")),
                    "cheapest": (pr.get("pickup") or {}).get("first_thing"),
                })
            order = {"resolved": 0, "narrowed": 1, "open": 2, None: 3}
            rows.sort(key=lambda r: (order.get(r["overall"], 3), -r["n_newer"]))
            return self.json({
                "rows": rows,
                "labs": sorted({r["lab"] for r in rows if r["lab"]}),
                "n_resolved": sum(1 for r in rows if r["overall"] == "resolved"),
                "n_narrowed": sum(1 for r in rows if r["overall"] == "narrowed"),
                "people": [agent_card(s) for s in store.all_of("scientists")
                           if s.get("lab") == my_lab and s["id"] != me["id"]],
            })

        if p == "/api/connections":
            # Anchored on the result, not the person. Two agents agreeing their
            # scientists should collaborate is not how collaborations start; a
            # specific question attached to a specific dead end is.
            if not me:
                return self.json({"error": "no scientist"}, 401)
            out = []
            for pr in store.where("problems", scientist_id=me["id"]):
                ms = [match_view(m) for m in store.where("matches", problem_id=pr["id"])
                      if m.get("can_help")]
                refused = sum(1 for m in store.where("matches", problem_id=pr["id"])
                              if not m.get("can_help"))
                if not ms and not refused:
                    continue
                out.append({"id": pr["id"], "title": pr["card"].get("title"),
                            "project": pr["card"].get("project"),
                            "year": pr["card"].get("year"),
                            "asked": len(ms) + refused, "refused": refused,
                            "people": ms})
            out.sort(key=lambda r: -len(r["people"]))
            return self.json({"results": out})

        if p == "/api/requests":
            # Broadcasts from other agents that mine has judged, plus the raw asks.
            if not me:
                return self.json({"error": "no scientist"}, 401)
            out = []
            for m in store.where("matches", responder_id=me["id"]):
                if not m.get("can_help"):
                    continue
                out.append(match_view(m))
            return self.json({"requests": out})

        if p == "/api/examples":
            return self.json({"examples": [
                {"id": e["id"], "label": e["label"], "field": e["field"],
                 "paste": e["paste"]}
                for e in examples.EXAMPLES
            ]})

        if p == "/api/demo-token":
            # Local demo convenience, seeded profiles only: it hands out a key,
            # so it must never return one for somebody who signed themselves up.
            s = store.get("scientists", (q.get("id") or [""])[0])
            if not s or not s.get("seeded"):
                return self.json({"error": "not a demo profile"}, 404)
            return self.json({"token": s["token"], "scientist": agent_card(s)})

        if p == "/api/signals":
            sigs = []
            for s in store.all_of("signals"):
                sci = store.get("scientists", s["scientist_id"])
                sigs.append({**s, "scientist": agent_card(sci) if sci else None})
            return self.json({"signals": sorted(sigs, key=lambda x: x.get("created", 0), reverse=True)})

        if p == "/api/job":
            with JOBS_LOCK:
                j = JOBS.get((q.get("id") or [""])[0])
                return self.json(dict(j) if j else {"error": "no such job"},
                                 200 if j else 404)

        if p.startswith("/static/"):
            t = (STATIC / p[len("/static/"):]).resolve()
            if STATIC.resolve() not in t.parents:
                return self.json({"error": "forbidden"}, 403)
            return self.file(t)

        return self.json({"error": "not found"}, 404)

    # -------------------------------------------------------------- POST
    def do_POST(self):
        p = urlparse(self.path).path
        me = self._me()
        try:
            b = self.body()
        except json.JSONDecodeError:
            return self.json({"error": "bad json"}, 400)

        if p == "/api/onboard":
            text = (b.get("text") or "").strip()
            if not text:
                return self.json({"error": "say something about yourself"}, 400)

            # Re-running onboarding with a key rewrites that profile rather than
            # creating a second one: the confirm step has to be correctable.
            existing = store.by_token((b.get("token") or "").strip())

            def go():
                prof = agents.profile_from_text(text)
                if existing:
                    upd = store.patch(
                        "scientists", existing["id"],
                        name=prof.get("name") or existing["name"],
                        field=prof.get("field") or existing["field"],
                        institution=prof.get("institution") or existing.get("institution"),
                        adjacent_fields=prof.get("adjacent_fields", []),
                        techniques=prof.get("techniques", []),
                        equipment=prof.get("equipment", []),
                        can_offer=prof.get("can_offer", []),
                        interests=prof.get("interests", []),
                    )
                    return {"scientist": agent_card(upd), "token": upd["token"]}
                s = store.scientist(
                    name=prof.get("name") or "You",
                    field=prof.get("field") or "unspecified",
                    institution=prof.get("institution"),
                    adjacent_fields=prof.get("adjacent_fields", []),
                    techniques=prof.get("techniques", []),
                    equipment=prof.get("equipment", []),
                    can_offer=prof.get("can_offer", []),
                    interests=prof.get("interests", []),
                    onboarded=True,
                )
                store.event(s["id"], "note", "Your agent is set up",
                            "Tell it what you're stuck on and it will start looking.")
                return {"scientist": agent_card(s), "token": s["token"]}

            return self.json({"job": submit(go)})

        if p == "/api/use-token":
            s = store.by_token((b.get("token") or "").strip())
            if not s:
                return self.json({"error": "unknown key"}, 404)
            return self.json({"scientist": agent_card(s), "token": s["token"]})

        if not me:
            return self.json({"error": "no scientist"}, 401)

        if p == "/api/interview/next":
            tr = b.get("transcript") or []
            return self.json({"job": submit(agents.next_question, tr, max_questions=6)})

        if p == "/api/interview/answer":
            # Walkthrough affordance: answer as the scientist from an example's
            # source material, so the product can be demoed without typing.
            ex = examples.BY_ID.get(b.get("example_id") or "")
            if not ex:
                return self.json({"error": "unknown example"}, 400)
            asked = [t["text"] for t in (b.get("transcript") or [])
                     if t.get("role") == "scientist"]
            return self.json({"job": submit(agents.answer_as_scientist,
                                            b.get("question") or "",
                                            ex["material"], asked_before=asked)})

        if p == "/api/problem/create":
            tr = b.get("transcript") or []
            paste = (b.get("paste") or "").strip()

            def go():
                card = agents.structure(tr, field_hint=me.get("field", ""))
                pr = store.problem(me["id"], card, transcript=tr,
                                   source=paste[:400] or None)
                store.event(me["id"], "note", "Your agent picked this up",
                            card.get("title", ""), problem_id=pr["id"])
                return {"problem": pr}

            return self.json({"job": submit(go)})

        if p == "/api/chat":
            msg = (b.get("message") or "").strip()
            if not msg:
                return self.json({"error": "say something"}, 400)
            hist = (b.get("history") or [])[-8:]

            def go():
                full = store.get("scientists", me["id"]) or {}
                lab = full.get("lab")
                members = [x for x in store.all_of("scientists")
                           if (x.get("lab") == lab if lab else x["id"] == me["id"])]
                shelf = []
                for sci in members:
                    for pr in store.where("problems", scientist_id=sci["id"]):
                        card = pr["card"]
                        br = store.get("briefs", pr["brief_id"]) if pr.get("brief_id") else None
                        an = (br or {}).get("analysis") or {}
                        hs = an.get("hypotheses") or []
                        shelf.append({
                            "id": pr["id"], "owner": sci["name"],
                            "is_yours": sci["id"] == me["id"],
                            "project": card.get("project"),
                            "title": card.get("title"), "year": card.get("year"),
                            "observed": card.get("observation"),
                            "quality_flags": card.get("quality_flags"),
                            "open_questions": card.get("open_questions"),
                            "read": bool(br),
                            "verdict": an.get("verdict"),
                            "explanations": [
                                {"claim": h.get("claim"), "kind": h.get("kind"),
                                 "test": h.get("test"),
                                 "papers": [{"title": x.get("title"), "year": x.get("year")}
                                            for x in (h.get("papers") or [])[:3]]}
                                for h in hs[:4]],
                            "people": [c.get("name") for c in (br or {}).get("contacts", [])],
                        })
                prof = {k: full.get(k) for k in
                        ("name", "field", "institution", "techniques", "equipment",
                         "can_offer", "interests") if full.get(k)}
                return agents.talk(msg, prof, shelf, hist)

            return self.json({"job": submit(go)})

        if p == "/api/schedule":
            if "on" in b:
                SCHED["on"] = bool(b["on"])
                if SCHED["on"]:
                    SCHED["last"] = 0        # run on the next sweep, not in 3 minutes
            if "every" in b:
                SCHED["every"] = max(30, min(3600, int(b["every"] or 180)))
            return self.json({"schedule": dict(SCHED)})

        if p == "/api/profile":
            # The confirm step has to be correctable in place; a name the model
            # could not find is the common case and it should not need a redo.
            fields = {k: v for k, v in b.items()
                      if k in ("name", "field", "institution", "lab")
                      and isinstance(v, str) and v.strip()}
            for k in ("techniques", "equipment", "can_offer", "adjacent_fields"):
                if isinstance(b.get(k), list):
                    fields[k] = [str(x)[:120] for x in b[k]][:30]
            if not fields:
                return self.json({"error": "nothing to set"}, 400)
            return self.json({"scientist": agent_card(
                store.patch("scientists", me["id"], **fields))})

        if p == "/api/result/set":
            # Widening is deliberate and it is the owner's call, never the agent's.
            pr = store.get("problems", b.get("id") or "")
            if not pr:
                return self.json({"error": "not found"}, 404)
            if pr["scientist_id"] != me["id"] and not pr.get("unclaimed"):
                return self.json({"error": "not yours to change"}, 403)
            fields = {}
            if "visibility" in b:
                if b["visibility"] not in store.VISIBILITY:
                    return self.json({"error": "unknown visibility"}, 400)
                fields["visibility"] = b["visibility"]
            if "confidence" in b:
                try:
                    fields["confidence"] = max(0, min(100, int(b["confidence"])))
                except (TypeError, ValueError):
                    return self.json({"error": "confidence must be 0-100"}, 400)
            if not fields:
                return self.json({"error": "nothing to set"}, 400)
            return self.json({"problem": store.patch("problems", pr["id"], **fields)})

        if p == "/api/result/claim":
            # A mined result becomes someone's when they take it on.
            pr = store.get("problems", b.get("id") or "")
            if not pr or not pr.get("unclaimed"):
                return self.json({"error": "not claimable"}, 400)
            store.event(me["id"], "note", "You picked this up",
                        pr["card"].get("title", ""), problem_id=pr["id"])
            return self.json({"problem": store.patch(
                "problems", pr["id"], unclaimed=False, scientist_id=me["id"])})

        if p == "/api/result/cosign":
            # One other person willing to put their name to it. This is the whole
            # quality mechanism: cheap for them, and it is what keeps the shelf
            # from filling with things nobody would defend.
            pr = store.get("problems", b.get("id") or "")
            if not pr:
                return self.json({"error": "not found"}, 404)
            if pr["scientist_id"] == me["id"]:
                return self.json({"error": "you cannot co-sign your own"}, 400)
            signs = list(pr.get("cosigns") or [])
            if any(c.get("scientist_id") == me["id"] for c in signs):
                return self.json({"problem": pr})
            signs.append({"scientist_id": me["id"], "name": me["name"],
                          "note": (b.get("note") or "").strip()[:300],
                          "created": store.now()})
            store.event(pr["scientist_id"], "note", f"{me['name']} co-signed your result",
                        pr["card"].get("title", ""), problem_id=pr["id"])
            return self.json({"problem": store.patch("problems", pr["id"], cosigns=signs)})

        if p == "/api/handoff":
            # The event the whole lab-private tier exists for: somebody who
            # will not run the experiment hands it to somebody who will. The
            # handover is written at the same moment, because a handoff
            # without one is just an email that says "look at this".
            pr = store.get("problems", b.get("id") or "")
            to = store.get("scientists", b.get("to") or "")
            if not pr or not to:
                return self.json({"error": "not found"}, 404)
            note = (b.get("note") or "").strip()[:500]
            store.patch("problems", pr["id"],
                        assigned_to=to["id"], assigned_to_name=to["name"],
                        assigned_by=me["name"], assigned_note=note)
            store.event(to["id"], "note", f"{me['name']} handed you a result",
                        note or pr["card"].get("title", ""),
                        problem_id=pr["id"], actionable=True)

            def go():
                fresh = store.get("problems", pr["id"]) or pr
                if fresh.get("pickup"):
                    return {"ok": True, "pickup": fresh["pickup"]}
                br = store.get("briefs", fresh["brief_id"]) if fresh.get("brief_id") else None
                an = (br or {}).get("analysis") or {}
                card = fresh["card"]
                newer = [x for x in ((br or {}).get("papers") or [])
                         if (x.get("year") or 0) > (card.get("year") or 9999)]
                newer += ((br or {}).get("since") or {}).get("papers") or []
                ms = []
                for m in store.where("matches", problem_id=fresh["id"]):
                    if not m.get("can_help"):
                        continue
                    who = store.get("scientists", m["responder_id"]) or {}
                    ms.append({"name": who.get("name"), "field": who.get("field"),
                               "offered": (m.get("response") or {}).get("specifically")})
                out = agents.pickup(card, an, matches=ms, newer=newer[:10])
                store.patch("problems", fresh["id"], pickup=out)
                return {"ok": True, "pickup": out}

            return self.json({"job": submit(go)})

        if p == "/api/pickup":
            pr = store.get("problems", b.get("id") or "")
            if not pr:
                return self.json({"error": "not found"}, 404)

            def go():
                br = store.get("briefs", pr["brief_id"]) if pr.get("brief_id") else None
                an = (br or {}).get("analysis") or {}
                card = pr["card"]
                newer = [x for x in ((br or {}).get("papers") or [])
                         if (x.get("year") or 0) > (card.get("year") or 9999)]
                ms = []
                for m in store.where("matches", problem_id=pr["id"]):
                    if not m.get("can_help"):
                        continue
                    who = store.get("scientists", m["responder_id"]) or {}
                    ms.append({"name": who.get("name"), "field": who.get("field"),
                               "offered": (m.get("response") or {}).get("specifically")})
                out = agents.pickup(card, an, matches=ms, newer=newer[:8])
                store.patch("problems", pr["id"], pickup=out)
                return {"pickup": out}

            return self.json({"job": submit(go)})

        if p == "/api/mine":
            # The supply side: agents reading papers for nulls nobody logged.
            try:
                import mine as mine_mod
            except ImportError:
                return self.json({"error": "mining is not wired up yet"}, 501)
            topic = (b.get("topic") or "").strip()

            def go(**kw):
                say = kw.get("on_progress")
                res = (mine_mod.mine(topic, on_progress=say) if topic
                       else mine_mod.mine_for_scientist(me["id"], on_progress=say))
                cards = res if isinstance(res, list) else res.get("cards", [])
                made = []
                for c in cards:
                    card = dict(c)
                    paper = card.pop("source_paper", None)
                    card.pop("unclaimed", None)
                    card.pop("source", None)
                    pr = store.problem(me["id"], card, origin="literature",
                                       unclaimed=True, source_paper=paper,
                                       visibility="public")
                    made.append({"id": pr["id"], "title": card.get("title")})
                if made:
                    store.event(me["id"], "note",
                                f"Your agent found {len(made)} shelved result"
                                f"{'' if len(made) == 1 else 's'} in the literature",
                                "Nobody logged these. They were buried in published papers.")
                return {"found": made,
                        "topic": topic or (res.get("topic") if isinstance(res, dict) else ""),
                        "n_papers": (res.get("n_papers") if isinstance(res, dict) else None),
                        "n_refused": (res.get("n_refused") if isinstance(res, dict) else None)}

            return self.json({"job": submit(go, _wants_progress=True)})

        if p == "/api/tick":
            rounds = int(b.get("rounds") or 1)
            if b.get("mine_only", True):
                return self.json({"job": submit(agentd.work_for, me["id"],
                                                rounds=rounds, _wants_progress=True)})
            return self.json({"job": submit(agentd.world_tick, rounds=rounds,
                                            _wants_progress=True)})

        if p == "/api/event/read":
            store.patch("events", b.get("id"), read=True)
            return self.json({"ok": True})

        if p == "/api/event/read-all":
            for e in store.where("events", scientist_id=me["id"]):
                if not e.get("read"):
                    store.patch("events", e["id"], read=True)
            return self.json({"ok": True})

        return self.json({"error": "not found"}, 404)


if __name__ == "__main__":
    print(f"nullspace on http://localhost:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
