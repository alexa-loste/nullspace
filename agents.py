"""The four agents.

interview      - elicits a negative result from a scientist, one question at a time
structure      - turns the transcript into a negative-result card
queries        - proposes literature searches, including deliberately off-field ones
recontextualize- explains the result against retrieved papers, cited by index
connect        - names people who could unstick it, from those same papers

Citations are always indices into the paper list handed to the model, never free
text. Anything the model cites is resolved against the retrieved set, so a
fabricated reference cannot survive into the output.
"""

import json
import llm

JSON = llm.JSON_RULE

SCIENTIST = (
    "You are a careful research scientist. You distinguish what was observed from "
    "what it means. You never invent data, citations, numbers or mechanisms. When "
    "the evidence does not support a conclusion, you say so plainly."
)


# ---------------------------------------------------------------- interview

INTERVIEW_GOAL = """\
You are interviewing a scientist about a result that did not work out: a negative, \
null, or unexplained result. Your job is to elicit enough that another scientist in \
a different field could understand it and possibly explain it. Ask about, in rough \
order of importance:

1. What the project was trying to achieve, in the scientist's own words. A result means nothing on its own: another scientist has to know what was being attempted and why it mattered. Ask this first.
2. What was expected of this particular experiment, and the reasoning behind that expectation (the mental model).
3. What was actually observed, with numbers and units.
4. How it was measured, and what controls were run.
5. How many independent replicates, and the variability.
6. What has already been ruled out.
7. What the scientist thinks might be going on, and how confident they are.
8. Anything that would make this result uninformative rather than real \
(a failed positive control, a detection limit, a confound).

Ask ONE question at a time. Be specific and build on what they said; never ask \
something already answered. Do not pad: when you have enough for the eight points \
above, or the scientist has nothing more to add, stop. Aim for 4 to 6 questions \
total."""


def next_question(transcript, max_questions=9):
    """transcript: list of {"role": "agent"|"scientist", "text": ...}"""
    asked = sum(1 for t in transcript if t["role"] == "agent")
    convo = "\n\n".join(
        f"{'INTERVIEWER' if t['role'] == 'agent' else 'SCIENTIST'}: {t['text']}"
        for t in transcript
    ) or "(nothing yet - this is your first question)"
    prompt = f"""{INTERVIEW_GOAL}

You have asked {asked} of at most {max_questions} questions.

TRANSCRIPT SO FAR
{convo}

Return JSON:
{{"done": false, "question": "<your single next question>", "why": "<which of the seven points this is for, 8 words max>"}}
or, if you have enough:
{{"done": true, "question": null, "why": "<what you have, 12 words max>"}}

Set done to true if you have covered the seven points, or if the scientist is \
clearly out of information, or if you have asked {max_questions} questions."""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


# ---------------------------------------------------------------- structure

def structure(transcript, field_hint=""):
    convo = "\n\n".join(
        f"{'INTERVIEWER' if t['role'] == 'agent' else 'SCIENTIST'}: {t['text']}"
        for t in transcript
    )
    prompt = f"""Turn this interview into a structured negative-result card.

Use ONLY what the transcript states. Every field that the transcript does not \
support must be null or an empty list. Do not smooth over gaps: a thin card is \
correct if the interview was thin.

FIELD HINT: {field_hint or "(none given)"}

TRANSCRIPT
{convo}

Return JSON with exactly these keys:
{{
  "title": "<one line, states the result, not the project>",
  "project": "<the larger aim this experiment served, under 8 words, or null>",
  "project_context": "<2-3 sentences a scientist in another field could read to understand what was being attempted and why, or null>",
  "field": "<the subfield>",
  "adjacent_fields": ["<fields whose literature might bear on this>"],
  "year": <year the work was done, or null>,
  "expectation": "<what was expected and the reasoning behind it>",
  "observation": "<what was seen, with numbers and units>",
  "methods": "<assay, readout, controls, replicates>",
  "ruled_out": ["<already excluded>"],
  "scientist_hypothesis": "<their own guess, or null>",
  "scientist_confidence": <0-100: how confident THEY are the effect is real, or null>,
  "result_type": "informative_null" | "unresolved",
  "quality_flags": ["<anything that would make this uninformative: missing positive control, n=1, at detection limit>"],
  "open_questions": ["<what would have to be known to resolve this>"],
  "keywords": ["<6-10 technical terms for literature search>"]
}}

result_type is "informative_null" when the experiment was well controlled and the \
absence of an effect is itself a finding; "unresolved" when something did not work \
and the reason is unknown."""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


# ---------------------------------------------------------------- queries

def queries(card, n=7):
    prompt = f"""Propose {n} literature search queries that could explain or \
re-contextualize this negative result.

NEGATIVE RESULT CARD
{json.dumps(card, indent=2)}

Rules for the query set:
- At least 2 queries must leave this subfield entirely: look for the same \
phenomenon under a different name in another field (protein engineering, biophysics, \
clinical literature, ecology, materials, whatever genuinely applies).
- At least 1 must target the mechanism the scientist proposed, so it can be \
confirmed or killed.
- At least 1 must target a mundane technical explanation (artifact, detection \
limit, known assay failure mode).
- Queries are keyword phrases for a search engine over titles and abstracts, \
5-12 words, no boolean operators, no quotes.

Return JSON:
{{"queries": [{{"q": "<query>", "rationale": "<what it is looking for, 12 words max>", "kind": "same_field" | "adjacent_field" | "distant_field" | "mechanism" | "artifact"}}]}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


# ---------------------------------------------------------------- explain

def recontextualize(card, papers, as_of=None):
    listing = "\n\n".join(
        f"[{i}] {p['title']} ({p.get('year')}, {p.get('venue') or 'unknown venue'}, "
        f"cited {p.get('cited_by_count', 0)}x)\n"
        f"    authors: {', '.join(a['name'] for a in p.get('authors', [])[:6]) or 'unknown'}\n"
        f"    abstract: {(p.get('abstract') or '(no abstract retrieved)')[:900]}"
        for i, p in enumerate(papers)
    ) or "(no papers retrieved)"
    cutoff = (
        f"\nYou are reasoning as of {as_of}. The papers below are all published on or "
        f"before {as_of}. Do not use knowledge of work published after {as_of}."
        if as_of else ""
    )
    prompt = f"""Explain this negative result against the retrieved literature.{cutoff}

NEGATIVE RESULT CARD
{json.dumps(card, indent=2)}

RETRIEVED PAPERS
{listing}

Produce hypotheses that could explain the result. For each one:
- Cite papers ONLY by their [index] above, in "paper_refs". Never name a paper that \
is not in the list. If no retrieved paper supports a hypothesis, give it an empty \
paper_refs and say so in "evidence".
- "kind" says what sort of explanation it is: "mechanism" (a real effect with a \
cause), "artifact" (the result is not real), "scope" (real but narrower than \
assumed), "already_known" (someone has answered this).
- "would_change_the_result" states whether this, if true, means the result should be \
reinterpreted as positive, stays negative, or is uninformative.
- "test" is one concrete experiment that would discriminate this hypothesis from the \
others: the measurement, the expected outcome if true, and the expected outcome if false.
- "confidence" is 0-100 for how well the retrieved evidence supports it. Be hard on \
yourself; a hypothesis with no supporting paper rarely exceeds 30.

Rank hypotheses best first. Give 2 to 5. Also return "verdict": your one-sentence \
read on what this negative result most likely is.

Return JSON:
{{
  "verdict": "<one sentence>",
  "hypotheses": [
    {{"claim": "<one line>",
      "kind": "mechanism" | "artifact" | "scope" | "already_known",
      "reasoning": "<2-4 sentences tying the card to the cited papers>",
      "paper_refs": [<indices>],
      "evidence": "<what the cited papers actually show, or that nothing retrieved supports this>",
      "would_change_the_result": "<reinterpret as positive | stays negative | uninformative>",
      "test": "<one discriminating experiment>",
      "confidence": <0-100>}}
  ],
  "what_was_not_retrieved": "<what literature you would want but did not get, one sentence>"
}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


# ---------------------------------------------------------------- connect

def connect(card, analysis, papers):
    cited = sorted({
        i for h in analysis.get("hypotheses", [])
        for i in h.get("paper_refs", [])
        if isinstance(i, int) and 0 <= i < len(papers)
    })
    listing = "\n\n".join(
        f"[{i}] {papers[i]['title']} ({papers[i].get('year')})\n"
        f"    authors: "
        + "; ".join(
            f"{a['name']}"
            + (f" ({', '.join(a['institutions'][:2])})" if a.get("institutions") else "")
            + (" [last author]" if a.get("position") == "last" else "")
            + (" [first author]" if a.get("position") == "first" else "")
            for a in papers[i].get("authors", [])[:8]
        )
        for i in cited
    ) or "(no cited papers)"
    prompt = f"""Name the people best placed to unstick this negative result.

NEGATIVE RESULT CARD
{json.dumps(card, indent=2)}

THE ANALYSIS
{json.dumps(analysis, indent=2)}

PAPERS CITED IN THE ANALYSIS (the only people you may name)
{listing}

Rules:
- Name only people who appear in the author lists above. Never invent a person, an \
institution or an email address.
- Prefer last authors (likely lab heads) for collaboration, first authors for \
hands-on method questions. Say which you think it is.
- For each, say what they could specifically answer or do, tied to a hypothesis.
- "ask" is a 2-sentence opening message the scientist could send: concrete, \
states the result and the specific question, no flattery, no pitch.

Give 2 to 4 people, best first.

Return JSON:
{{"contacts": [
  {{"name": "<as written in the author list>",
    "institutions": ["<as written, or empty>"],
    "paper_ref": <index>,
    "role": "<last author / first author / co-author>",
    "why": "<what they could answer, tied to which hypothesis>",
    "ask": "<2-sentence opening message>"}}
]}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


# ---------------------------------------------------------------- scoring

def score_against_truth(analysis, truth):
    """Grade an analysis against what the scientist actually concluded.

    Used for the retrodiction test, where we know the answer.
    """
    prompt = f"""Grade this agent's analysis against what the scientist actually \
concluded. Be strict: credit only real matches of mechanism, not vague overlap.

THE AGENT'S ANALYSIS
{json.dumps(analysis, indent=2)}

WHAT THE SCIENTIST ACTUALLY CONCLUDED (ground truth)
{json.dumps(truth, indent=2)}

Return JSON:
{{
  "found_mechanism": true | false,
  "mechanism_rank": <1-based rank of the hypothesis matching the true mechanism, or null>,
  "found_key_paper": true | false,
  "proposed_matching_experiment": true | false,
  "notes": "<2-3 sentences: what it got, what it missed, what it added that the scientist did not have>",
  "grade": "<match | partial | miss>"
}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


# ================================================================ agent-to-agent
# The skills above work for one scientist. These let one scientist's agent
# reach another's: restating a problem so a different field recognizes it,
# broadcasting it, judging someone else's broadcast against what its own
# scientist can actually do, and introducing two people.

def broadcast(card, profile):
    """Restate a stuck result as a request other fields would recognize.

    This is the cross-field step. A keyword search cannot bridge "frameshift
    variant retains activity" and "ribosomal recoding"; a restatement can.
    """
    prompt = f"""Write a request for help, addressed to scientists OUTSIDE this \
person's field.

THEIR OPEN PROBLEM
{json.dumps(card, indent=2)}

THEIR OWN FIELD AND PROFILE
{json.dumps(profile, indent=2)}

Produce:
- "headline": one sentence another scientist would scan. State the phenomenon, \
not the system. Someone in a different field should be able to tell within a \
second whether this is near their work.
- "plain": 2-3 sentences with no jargon specific to this subfield. Describe what \
was expected, what happened, and what is unexplained. Someone two fields away \
must be able to follow it.
- "restatements": one per field listed below, each restating the SAME problem in \
that field's own vocabulary and framing. This is the point of the exercise: the \
phrasing a person in that field would use for this phenomenon. Give the field, \
the restatement, and the specific thing someone there might know.
- "asks": 2-4 concrete things that would actually help. Each is a technique, a \
measurement, a piece of equipment, or a judgement call. Not "collaborate on this" \
but "run a Western with terminal tags on a low-abundance bacterial lysate".
- "offers": what this scientist could give back, taken from their profile. Be \
honest; if the profile does not support an offer, return an empty list.

FIELDS TO RESTATE FOR
{json.dumps(card.get("adjacent_fields") or [], indent=2)}
plus two further fields of your own choosing that are genuinely further away and \
genuinely plausible. Do not pad with fields that have nothing to say.

Return JSON:
{{"headline": "...", "plain": "...",
  "restatements": [{{"field": "...", "as_they_would_say_it": "...", "what_they_might_know": "..."}}],
  "asks": [{{"ask": "...", "kind": "technique" | "measurement" | "equipment" | "judgement"}}],
  "offers": ["..."]}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


def respond(signal, profile, own_problems=None):
    """Judge another agent's broadcast against what MY scientist can actually do.

    The bar is deliberately high. If every broadcast matches every agent the
    whole mechanism is worthless, so this is written to say no by default.
    """
    prompt = f"""Another scientist's agent has broadcast a request for help. Decide \
whether YOUR scientist can genuinely help, and answer honestly.

THE BROADCAST
{json.dumps(signal, indent=2)}

YOUR SCIENTIST
{json.dumps(profile, indent=2)}

THEIR OWN OPEN PROBLEMS (a shared problem is a reason to connect too)
{json.dumps(own_problems or [], indent=2)}

Say yes ONLY if your scientist could do something specific and useful: a \
technique they actually list, equipment they actually have, a judgement their \
expertise actually covers, or a problem of their own that this bears on. \
Adjacency of field is NOT a match. Interest is NOT a match. Being able to read \
the paper is NOT a match.

Most broadcasts should get "can_help": false. A false answer is a good answer \
when it is true.

If yes, "specifically" must name the exact thing, drawn from their profile, and \
"confidence" reflects how sure you are it applies here.

Return JSON:
{{"can_help": true | false,
  "why_not": "<one sentence, when false>",
  "specifically": "<the exact thing they could do, when true>",
  "drawn_from": "<the profile entry this rests on, when true>",
  "direction": "i_can_help" | "we_share_a_problem" | "i_want_their_method",
  "confidence": <0-100>,
  "opening_line": "<one sentence your scientist could send, when true>"}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


def broker(signal, asker, responder, response):
    """Write the introduction, to both people, once two agents agree."""
    prompt = f"""Two agents have agreed their scientists should talk. Write the \
introduction.

THE REQUEST THAT STARTED IT
{json.dumps(signal, indent=2)}

WHO ASKED
{json.dumps(asker, indent=2)}

WHO ANSWERED
{json.dumps(responder, indent=2)}

WHAT THE ANSWERING AGENT SAID
{json.dumps(response, indent=2)}

Write:
- "why_this_works": 2 sentences on why these two specifically, naming the \
technique or knowledge that bridges them. No enthusiasm, no "exciting \
opportunity". A scientist should read it and think "yes, that follows".
- "to_asker" and "to_responder": a short message each could send the other. \
Under 70 words. State the result, the specific question, and what is on offer in \
return. No flattery, no pitch, no "I hope this finds you well".
- "first_step": the single concrete thing they would do first if they said yes. \
One sentence, something that could happen this month.
- "what_could_go_wrong": one honest sentence on why this might not pan out. Do \
not skip this.

Return JSON:
{{"why_this_works": "...", "to_asker": "...", "to_responder": "...",
  "first_step": "...", "what_could_go_wrong": "..."}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


def profile_from_text(text):
    """Turn whatever a new user types about themselves into a profile."""
    prompt = f"""Build a researcher profile from what this person wrote about \
themselves. Use only what they state or what follows necessarily from it. Leave a \
field empty rather than guessing.

WHAT THEY WROTE
{text}

Return JSON:
{{"name": "<or null>", "field": "<their subfield>", "institution": "<or null>",
  "adjacent_fields": ["<fields whose work bears on theirs>"],
  "techniques": ["<what they can actually do at the bench or on a machine>"],
  "equipment": ["<instruments or platforms they have access to>"],
  "can_offer": ["<specific help they could give another lab>"],
  "interests": ["<what they are trying to find out>"]}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


def answer_as_scientist(question, material, asked_before=None):
    """Answer an interview question from an example's source material.

    This exists so the product can be walked through without typing. It must be
    willing to say the scientist does not know: the material is deliberately
    incomplete, and a walkthrough where every control was run is a lie about
    what logging a real negative result is like.
    """
    prompt = f"""You are answering an interviewer's question as the scientist who \
did this work. Everything you know is below. 

WHAT YOU KNOW
{json.dumps(material, indent=2)}

ALREADY ASKED AND ANSWERED
{json.dumps(asked_before or [], indent=2)}

THE QUESTION
{question}

Answer in 1-3 sentences, first person, the way a scientist talks at the bench. \
Give numbers where the material has them.

If the material does not cover it — especially anything in "not_checked" — say \
you do not know or never checked, plainly and without apologising. Do not invent \
a measurement, a control or a number that is not above. A real scientist logging \
a real negative result does not have every answer, and pretending otherwise would \
misrepresent what this is like.

Return JSON: {{"answer": "<what you say>", "knew_it": true | false}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")



def talk(message, profile, shelf, history=None):
    """Answer the scientist, from what their agent already holds.

    This is the always-on side of the agent: it has read everything on the
    shelf, so it should answer from that rather than asking the scientist to
    go and look. It is allowed to say it does not know.
    """
    prompt = f"""You are this scientist's own research agent. You have already read
every result below and the literature behind them. Answer their message.

WHO YOU WORK FOR
{json.dumps(profile, indent=2)}

WHAT YOU HOLD FOR THEM (their lab's shelf, and what you concluded about each)
{json.dumps(shelf, indent=2)}

EARLIER IN THIS CONVERSATION
{json.dumps(history or [], indent=2)}

THEIR MESSAGE
{message}

How to answer:
- Answer from what you hold. Name the specific result, paper or person. If the
  answer is in a brief you already wrote, give it rather than telling them to go
  and read it.
- If you do not have it, say so plainly and say what you would have to do to find
  out. Never invent a paper, a person, a number or a result.
- Short. Two to five sentences unless they asked for a list. No preamble, no
  restating their question back at them.
- You are talking to the person you work for, not writing a report. Plain words.
- If something they said should change a result you hold, say which one and how.

If acting would answer them better than talking, name the action in "suggests":
"read" (read the literature on a result they have not had looked at),
"ask_fields" (put a result to other fields), "log" (they are describing a new
result that is not on the shelf yet), or null. Put the result's id in
"suggests_id" when the action is about one you already hold.

Return JSON:
{{"reply": "<what you say>", "suggests": "read" | "ask_fields" | "log" | null,
  "suggests_id": "<result id or null>", "suggests_label": "<the button's words, under 5 words, or null>"}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


# ---------------------------------------------------------------- pickup
# The lab-private payoff, and the one event that actually recurs: somebody
# inherits a project that stopped. They need where it stopped and what is
# cheapest to try, addressed to them rather than to the person who ran it.

def pickup(card, analysis, matches=None, newer=None):
    """Rewrite a shelved result for whoever picks it up next."""
    prompt = f"""A project stopped. Someone new is about to pick it up: a new student,
or the same lab coming back to it years later. They did not run the experiment and
they have no context beyond what is written here.

THE RESULT
{json.dumps(card, indent=2)}

WHAT THE AGENT CONCLUDED
{json.dumps(analysis or {}, indent=2)}

WORK PUBLISHED SINCE IT WAS SHELVED
{json.dumps(newer or [], indent=2)}

PEOPLE WHOSE AGENTS SAID THEY COULD HELP
{json.dumps(matches or [], indent=2)}

Write what this person needs, and nothing else. They are deciding whether to spend a
term on it, so be concrete about cost and about what would make them stop.

- "where_it_stopped": the last thing that was actually done, and why it stopped.
  One or two sentences, plain, no interpretation.
- "what_exists": what they would inherit that is physical or reusable - strains,
  plasmids, constructs, cell lines, data, code, protocols. Only what the material
  above actually mentions. Empty list if it mentions none; do not invent a freezer.
- "first_thing": the single cheapest experiment that would tell them whether this is
  worth continuing. Name the measurement and roughly what it costs in time.
- "would_make_me_stop": the result that should make them abandon it. Scientists are
  bad at this, so be specific and unsentimental.
- "read_first": up to three things to read, drawn ONLY from the papers in the
  material above, each with one line on why that one.
- "what_changed": if work published since changes the picture, say how, in one
  sentence. null if nothing above does.
- "honest_warning": the thing a departing student would say over coffee that is not
  in any writeup. If the material does not support one, null - do not invent it.

Return JSON:
{{"where_it_stopped": "<...>",
  "what_exists": ["<...>"],
  "first_thing": "<...>",
  "would_make_me_stop": "<...>",
  "read_first": [{{"title": "<...>", "why": "<...>"}}],
  "what_changed": "<... or null>",
  "honest_warning": "<... or null>"}}"""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


# ---------------------------------------------------------------- since
# The whole claim of this product is that a null often becomes explicable
# later. On a null old enough that the field has already moved, that claim is
# checkable: reason with only the literature of the time, then look at what
# came after and say plainly whether you were right.

def check_since(card, analysis, newer_papers, as_of=None):
    """Grade an as-of-date explanation against work published afterwards."""
    hyps = [{"rank": i + 1, "claim": h.get("claim"), "kind": h.get("kind"),
             "confidence": h.get("confidence"), "test": h.get("test")}
            for i, h in enumerate((analysis or {}).get("hypotheses") or [])]
    papers = [{"i": i, "title": p.get("title"), "year": p.get("year"),
               "venue": p.get("venue"), "abstract": (p.get("abstract") or "")[:900]}
              for i, p in enumerate(newer_papers or [])]
    prompt = f"""An agent explained a negative result using only literature published
on or before {as_of or 'the time of the experiment'}. Below is what the field
published AFTER that. Say what became of each explanation.

THE RESULT
{json.dumps(card, indent=2)}

WHAT THE AGENT CONCLUDED AT THE TIME
{json.dumps(hyps, indent=2)}

WHAT WAS PUBLISHED AFTERWARDS
{json.dumps(papers, indent=2)}

Grade honestly. The interesting outcome is not that the agent was right. An
explanation that later work contradicted is a more useful thing to show than one
nothing bears on, so do not inflate.

For each explanation, a verdict of:
- "supported": later work gives direct evidence for this mechanism in a comparable system.
- "contradicted": later work gives direct evidence against it.
- "superseded": later work explains the result by something the agent did not propose.
- "untouched": nothing retrieved bears on it either way. Use this freely; it is the
  commonest honest answer.

Cite papers ONLY by their "i" index. Never name a paper not in the list.

Then, overall:
- "resolved": the result is now explained by published work, whether or not the agent got it.
- "narrowed": some explanations are out, none is confirmed.
- "open": the field has not touched it.

Return JSON:
{{"verdicts": [{{"rank": <n>, "verdict": "supported"|"contradicted"|"superseded"|"untouched",
    "why": "<one or two sentences>", "papers": [<i>]}}],
  "overall": "resolved"|"narrowed"|"open",
  "what_the_field_did": "<two or three sentences: what actually happened to this question>",
  "agent_was_right": true | false | null,
  "best_missed": "<the explanation the agent should have proposed and did not, or null>",
  "someone_else_published_it": true | false,
  "changed_in": <the publication year of the earliest paper that changed this null's standing, or null>}}

"someone_else_published_it" is true only when later work reports the SAME
experiment succeeding, or otherwise closes the question the scientist was
asking. That is being scooped, and it is a different outcome from the question
being answered in a way they could still build on. Do not use it for work that
merely bears on the result."""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")
