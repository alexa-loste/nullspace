"""Mine the published literature for negative results nobody logged.

The shelf only fills when a human sits down and logs a failure. Most negative
results were never logged at all: they are a sub-experiment inside a paper
whose headline is a success, a control that did not work, an approach
abandoned in paragraph four. This reads abstracts and lifts those out as
unclaimed cards in the shape an interview produces.

    python3 mine.py "yeast metabolic engineering" --papers 6

Nothing here writes to the store; the caller decides what to keep.
"""

import argparse
import json
import re
import sys

import agents
import litsearch
import llm
import store

JSON = llm.JSON_RULE
SCIENTIST = agents.SCIENTIST

BATCH = 5             # papers per model call: enough to compare against, short enough to stay strict
MIN_OVERLAP = 0.45    # how much of a quote's vocabulary must appear in the abstract


# ---------------------------------------------------------------- queries

def _plan_queries(topic, n=6, say=None):
    say = say or (lambda *a, **k: None)
    prompt = f"""Propose {n} literature search queries over titles and abstracts.

AREA: {topic}

We are looking for papers whose abstract mentions something that did not work: \
an experiment with no detectable effect, a step that could not be reproduced, a \
construct that gave no activity, an approach the authors dropped.

Build the set this way:
- {n - 2} queries pair the area's own technical vocabulary with the wording \
authors use for an absent result (not detected, no significant difference, \
failed to reconstitute, remained undetectable, was not observed). One wording \
per query, not several stacked together: a query stuffed with failure words \
just returns the area's most popular papers.
- 2 queries are plain topical queries in the area with no such wording, so the \
set is not only papers that describe themselves as failures.
- Each query is 5 to 12 words, no boolean operators, no quotation marks.

Return JSON:
{{"queries": [{{"q": "<query>", "rationale": "<what it is looking for, 12 words max>", \
"kind": "failure_phrasing" | "topical"}}]}}"""
    qs = []
    # One retry: the CLI occasionally hands back an error envelope instead of
    # the query set, and a second ask usually gets it.
    for _ in range(2):
        try:
            out = llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")
            qs = [q for q in (out.get("queries") or []) if q.get("q")]
        except (llm.LLMError, AttributeError):
            qs = []
        if qs:
            break
    # A retrieval step that returns nothing is worse than a crude one, so fall
    # back to queries built straight from the topic.
    if not qs:
        say("    could not plan searches, falling back to queries built from the topic")
        qs = [
            {"q": f"{topic} {phrase}", "kind": "failure_phrasing"}
            for phrase in ("not detected", "no significant difference",
                           "failed to reconstitute", "was not observed")
        ] + [{"q": topic, "kind": "topical"}]
    return qs[:7]


# ---------------------------------------------------------------- extraction

def _judge(papers, topic):
    """Ask for a verdict on each paper in a batch. Papers are cited by index only."""
    listing = "\n\n".join(
        f"[{i}] {p['title']} ({p.get('year')}, {p.get('venue') or 'unknown venue'})\n"
        f"    abstract: {(p.get('abstract') or '(none)')[:1600]}"
        for i, p in enumerate(papers)
    )
    prompt = f"""Decide, for each paper below, whether its abstract reports a \
negative result worth putting on a shelf of negative results, and if so extract it.

AREA BEING MINED: {topic}

PAPERS
{listing}

Keep a paper only if the abstract itself states an experiment, sub-experiment \
or control that did not work, an approach the authors tried and abandoned, an \
effect that was looked for and not found, or a whole result that is a null: no \
difference, no detection, no reconstitution.

Refuse a paper when the abstract reports only success, when it is a review or a \
method description with no result, when the null is about someone else's work \
rather than the authors' own, or when the abstract is too thin to tell what was \
measured. Most papers do not qualify. Refusing is the right answer far more \
often than keeping, and a weak keep is worse than a refusal.

For every paper you keep, "quote" is the sentence from THAT abstract the \
extraction rests on, copied or tightened but not invented, under 40 words. If \
you cannot point at such a sentence, refuse the paper.

Fill the card only from the abstract. Any field it does not support is null or \
an empty list; a thin card is correct when the abstract is thin. Do not supply \
numbers, controls or replicates that are not stated.

Return JSON:
{{"verdicts": [
  {{"index": <index above>,
    "keep": true | false,
    "why_refused": "<one short sentence, when keep is false>",
    "quote": "<the sentence from that abstract, when keep is true>",
    "card": {{
      "title": "<one line stating the negative result, not the paper's headline>",
      "project": "<the larger aim this served, under 8 words, or null>",
      "project_context": "<2-3 sentences another field could read to see what was being attempted and why, or null>",
      "field": "<the subfield>",
      "adjacent_fields": ["<fields whose literature might bear on this>"],
      "expectation": "<what was expected and the reasoning behind it, or null>",
      "observation": "<what was seen, with numbers and units where the abstract gives them>",
      "methods": "<assay, readout, controls, replicates, as far as the abstract says>",
      "ruled_out": ["<what the authors state they excluded>"],
      "scientist_hypothesis": "<the authors' own explanation, or null>",
      "result_type": "informative_null" | "unresolved",
      "quality_flags": ["<anything making this uninformative: no positive control, at detection limit, n unstated>"],
      "open_questions": ["<what would have to be known to resolve this>"],
      "keywords": ["<6-10 technical terms for literature search>"]
    }}}}
]}}

Give exactly one verdict per paper, including the ones you refuse.

result_type is "informative_null" when the work was controlled well enough that \
the absence is itself a finding; "unresolved" when something did not work and \
the reason is unknown."""
    return llm.call_json(prompt, system=f"{SCIENTIST}\n\n{JSON}")


def _grounded(quote, abstract):
    """Is this quote traceable to the abstract we actually retrieved?

    We do not demand a verbatim substring — the model is allowed to tighten a
    sentence — but a quote sharing little vocabulary with the abstract is a
    fabrication, and gets dropped the way pipeline.resolve_refs drops a citation
    that points at no retrieved paper.
    """
    want = set(re.findall(r"[a-z0-9]{4,}", (quote or "").lower()))
    if len(want) < 3:
        return False
    have = set(re.findall(r"[a-z0-9]{4,}", (abstract or "").lower()))
    return len(want & have) / len(want) >= MIN_OVERLAP


def _build(verdict, paper, topic):
    """Turn one kept verdict into a card, or return None if it cannot be trusted."""
    card = verdict.get("card")
    if not isinstance(card, dict):
        return None
    if not (card.get("title") and card.get("observation")):
        return None
    quote = (verdict.get("quote") or "").strip()
    if not _grounded(quote, paper.get("abstract")):
        return None
    card = dict(card)
    card["year"] = paper.get("year")
    card["field"] = card.get("field") or topic
    # We are reading the authors, not interviewing them, so we cannot speak to
    # how confident they are that the effect is real.
    card["scientist_confidence"] = None
    card["source"] = "literature"
    card["unclaimed"] = True
    card["provenance"] = quote
    card["source_paper"] = {
        "title": paper["title"],
        "year": paper.get("year"),
        "venue": paper.get("venue"),
        "doi": paper.get("doi"),
        "url": paper.get("url"),
        "openalex_id": paper.get("openalex_id"),
        "authors": [a["name"] for a in paper.get("authors", [])[:8]],
        "cited_by_count": paper.get("cited_by_count"),
        "found_by": paper.get("found_by"),
        "quote": quote,
    }
    return card


# ---------------------------------------------------------------- mining

def _mine(topic, n_papers, say, to_year=None):
    say(f"planning searches for “{topic}”")
    qs = _plan_queries(topic, say=say)
    for q in qs:
        say(f"    [{q.get('kind', '?')}] {q.get('q', '')}", data={"query": q})

    say("searching OpenAlex" + (f", nothing after {to_year}" if to_year else ""))
    # Spread the budget over the queries rather than letting the first one
    # fill it, so a small run still mixes failure phrasing with plain topic.
    per_query = max(2, -(-n_papers // max(1, len(qs))))
    papers = litsearch.multi_search([q["q"] for q in qs], per_query=per_query,
                                    cap=n_papers, to_year=to_year)
    # No abstract means nothing to judge; such a paper would only cost a call.
    papers = [p for p in papers if p.get("abstract")]
    say(f"{len(papers)} papers with abstracts to read")
    for p in papers[:12]:
        say(f"    {p.get('year')} · {(p.get('title') or '')[:70]}", data={"paper": p})

    cards, refused, unjudged = [], 0, 0
    for start in range(0, len(papers), BATCH):
        batch = papers[start:start + BATCH]
        say(f"reading abstracts {start + 1}-{start + len(batch)} of {len(papers)}")
        verdicts = []
        # One retry, as with the planner. A batch that comes back empty is not
        # a batch of refusals: those papers were never read, and saying they
        # were refused would overstate how hard the filter is working.
        for _ in range(2):
            try:
                out = _judge(batch, topic)
            except llm.LLMError as exc:
                say(f"    could not read this batch: {exc}")
                out = {}
            verdicts = (out.get("verdicts") if isinstance(out, dict) else out) or []
            if verdicts:
                break
        if not verdicts:
            unjudged += len(batch)
            say(f"    no verdicts came back; leaving these {len(batch)} unjudged")
            continue
        for v in verdicts:
            i = v.get("index")
            if not isinstance(i, int) or not 0 <= i < len(batch):
                continue    # a verdict on a paper we never retrieved is not a verdict
            paper = batch[i]
            if not v.get("keep"):
                refused += 1
                say(f"    refused · {(paper.get('title') or '')[:60]} — {(v.get('why_refused') or '')[:70]}")
                continue
            card = _build(v, paper, topic)
            if not card:
                refused += 1
                say(f"    dropped · {(paper.get('title') or '')[:60]} — provenance did not hold up")
                continue
            cards.append(card)
            say(f"    kept · {card['title'][:80]}", data={"card": card})

    say(f"{len(cards)} negative results extracted, {refused} papers refused"
        + (f", {unjudged} never read" if unjudged else ""))
    return cards, len(papers), refused


def mine(field_or_topic, n_papers=25, on_progress=None, to_year=None):
    """Extract unclaimed negative-result cards from the literature on a topic.

    `to_year` caps publication date. Mining only old papers is how the shelf
    gets nulls whose fate is already known: the field has had years to answer
    them, so an agent's explanation can be checked rather than just admired.
    """
    say = on_progress or (lambda *a, **k: None)
    return _mine(field_or_topic, n_papers, say, to_year=to_year)[0]


def _topic_for(sci, problems):
    """Their field, narrowed by what they are actually stuck on.

    A model call could choose a topic, but the scientist already stated their
    field and logged their problems. Using those costs nothing and is easier to
    explain when a mined card turns out to be beside the point.
    """
    field = (sci.get("field") or "").strip()
    terms = []
    for p in problems:
        if p.get("status") not in (None, "open"):
            continue
        card = p.get("card") or {}
        terms += (card.get("keywords") or [])[:3]
        if card.get("field") and card["field"] != field:
            terms.append(card["field"])
    picked, seen = [], {field.lower()}
    for t in terms:
        t = (t or "").strip()
        if t and t.lower() not in seen:
            seen.add(t.lower())
            picked.append(t)
        if len(picked) == 3:
            break
    return ", ".join([x for x in [field] + picked if x]) or "unspecified field"


def mine_for_scientist(scientist_id, on_progress=None, to_year=None):
    say = on_progress or (lambda *a, **k: None)
    sci = store.get("scientists", scientist_id)
    if not sci:
        raise ValueError(f"no scientist {scientist_id!r}")
    topic = _topic_for(sci, store.where("problems", scientist_id=scientist_id))
    say(f"mining the literature around {topic}")
    cards, n_papers, n_refused = _mine(topic, 25, say, to_year=to_year)
    return {"topic": topic, "cards": cards, "n_papers": n_papers, "n_refused": n_refused}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("topic", nargs="?", default="synthetic biology")
    # A real run costs a model call per batch, so the CLI stays small by default.
    ap.add_argument("--papers", type=int, default=6)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    found = mine(a.topic, n_papers=a.papers,
                 on_progress=lambda m, data=None: print(f"  {m}", file=sys.stderr, flush=True))
    if a.json:
        print(json.dumps(found, indent=2))
        sys.exit()
    for c in found:
        p = c["source_paper"]
        print("\n" + "=" * 78 + f"\n{c['title']}")
        print(f"  field:     {c.get('field')} · {c.get('result_type')}")
        print(f"  expected:  {c.get('expectation')}")
        print(f"  observed:  {c.get('observation')}")
        print(f"  methods:   {c.get('methods')}")
        print(f"  flags:     {'; '.join(c.get('quality_flags') or []) or '(none)'}")
        print(f"  open:      {'; '.join(c.get('open_questions') or []) or '(none)'}")
        print(f"  from:      {p['title']} ({p.get('year')}, {p.get('venue')})")
        print(f"             {p.get('url') or p.get('doi')}")
        print(f"  rests on:  “{c['provenance']}”")
    print(f"\n{len(found)} unclaimed card(s) from “{a.topic}”")
