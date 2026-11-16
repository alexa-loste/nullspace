"""Run a negative-result card through the pipeline.

    python3 pipeline.py t3-frameshift-activity
    python3 pipeline.py t3-frameshift-activity --as-of 2013   # retrodiction
    python3 pipeline.py strictosidine-yeast-undetected --as-of 2022

Writes data/<id>[_asof<year>].json and prints a readable summary.
"""

import argparse
import json
import pathlib
import sys
import time

import agents
import litsearch
import seeds

DATA = pathlib.Path(__file__).parent / "data"


def log(msg):
    print(f"  {msg}", file=sys.stderr, flush=True)


def resolve_refs(analysis, papers):
    """Drop citations that do not point at a retrieved paper, and attach the real ones."""
    dropped = 0
    for h in analysis.get("hypotheses", []):
        good = []
        for i in h.get("paper_refs", []) or []:
            if isinstance(i, int) and 0 <= i < len(papers):
                good.append(i)
            else:
                dropped += 1
        h["paper_refs"] = good
        h["papers"] = [
            {
                "title": papers[i]["title"],
                "year": papers[i].get("year"),
                "venue": papers[i].get("venue"),
                "url": papers[i].get("url"),
                "doi": papers[i].get("doi"),
                "cited_by_count": papers[i].get("cited_by_count"),
                "found_by": papers[i].get("found_by"),
            }
            for i in good
        ]
    analysis["_dropped_citations"] = dropped
    return analysis


def verify_contacts(contacts, papers):
    """Keep only people who really appear in the cited paper's author list."""
    names = {
        a["name"].lower()
        for p in papers
        for a in p.get("authors", [])
    }
    kept, rejected = [], []
    for c in contacts:
        if c.get("name", "").lower() in names:
            ref = c.get("paper_ref")
            if isinstance(ref, int) and 0 <= ref < len(papers):
                c["paper"] = {
                    "title": papers[ref]["title"],
                    "year": papers[ref].get("year"),
                    "url": papers[ref].get("url"),
                }
            kept.append(c)
        else:
            rejected.append(c.get("name"))
    return kept, rejected


def run(case_id, as_of=None, per_query=6, cap=28):
    case = seeds.CASES.get(case_id)
    if not case:
        sys.exit(f"unknown case {case_id!r}; have: {', '.join(seeds.CASES)}")
    card = case["card"]
    t0 = time.time()

    log("1/4 proposing literature searches")
    qout = agents.queries(card)
    qs = qout.get("queries", [])
    for q in qs:
        log(f"      [{q.get('kind')}] {q.get('q')}")

    log(f"2/4 searching OpenAlex{f' (capped at {as_of})' if as_of else ''}")
    papers = litsearch.multi_search(
        [q["q"] for q in qs if q.get("q")],
        to_year=as_of,
        per_query=per_query,
        cap=cap,
    )
    log(f"      {len(papers)} unique papers")

    log("3/4 re-contextualizing")
    analysis = agents.recontextualize(card, papers, as_of=as_of)
    analysis = resolve_refs(analysis, papers)
    if analysis["_dropped_citations"]:
        log(f"      dropped {analysis['_dropped_citations']} invalid citation(s)")

    log("4/4 finding people")
    cout = agents.connect(card, analysis, papers)
    contacts, rejected = verify_contacts(cout.get("contacts", []), papers)
    if rejected:
        log(f"      rejected unverifiable name(s): {rejected}")

    result = {
        "case_id": case_id,
        "case_kind": case.get("case_kind"),
        "source": case.get("source"),
        "as_of": as_of,
        "card": card,
        "queries": qs,
        "papers": papers,
        "analysis": analysis,
        "contacts": contacts,
        "rejected_contacts": rejected,
        "elapsed_s": round(time.time() - t0, 1),
    }

    if case.get("truth"):
        log("scoring against what the scientist actually concluded")
        result["score"] = agents.score_against_truth(analysis, case["truth"])
        result["truth"] = case["truth"]

    DATA.mkdir(exist_ok=True)
    name = f"{case_id}{f'_asof{as_of}' if as_of else ''}.json"
    out = DATA / name
    out.write_text(json.dumps(result, indent=2))
    log(f"wrote {out.name} in {result['elapsed_s']}s")
    return result


def summarize(r):
    w = print
    w("")
    w("=" * 78)
    w(r["card"]["title"])
    w("=" * 78)
    w(f"source: {r['source']}")
    w(f"{len(r['papers'])} papers retrieved" + (f", literature capped at {r['as_of']}" if r["as_of"] else ""))
    w("")
    w(f"VERDICT: {r['analysis'].get('verdict')}")
    w("")
    for n, h in enumerate(r["analysis"].get("hypotheses", []), 1):
        w(f"[{n}] ({h.get('kind')}, confidence {h.get('confidence')}) {h.get('claim')}")
        w(f"    {h.get('reasoning')}")
        w(f"    evidence: {h.get('evidence')}")
        for p in h.get("papers", []):
            w(f"      - {p['title']} ({p.get('year')}, {p.get('venue')})")
        w(f"    if true: {h.get('would_change_the_result')}")
        w(f"    test: {h.get('test')}")
        w("")
    w(f"not retrieved: {r['analysis'].get('what_was_not_retrieved')}")
    w("")
    w("PEOPLE WHO COULD HELP")
    for c in r["contacts"]:
        inst = ", ".join(c.get("institutions") or []) or "institution not in record"
        w(f"  {c['name']} ({c.get('role')}, {inst})")
        w(f"    why: {c.get('why')}")
        w(f"    ask: {c.get('ask')}")
    if r.get("rejected_contacts"):
        w(f"  (rejected, not in any retrieved author list: {r['rejected_contacts']})")
    if r.get("score"):
        s = r["score"]
        w("")
        w("SCORED AGAINST THE SCIENTIST'S OWN CONCLUSION")
        w(f"  grade: {s.get('grade')}")
        w(f"  found the mechanism: {s.get('found_mechanism')} (rank {s.get('mechanism_rank')})")
        w(f"  found the key paper: {s.get('found_key_paper')}")
        w(f"  proposed a matching experiment: {s.get('proposed_matching_experiment')}")
        w(f"  {s.get('notes')}")
    w("")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("case", nargs="?", default="t3-frameshift-activity")
    ap.add_argument("--as-of", type=int, default=None,
                    help="cap literature at this year (retrodiction test)")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, v in seeds.CASES.items():
            print(f"{k}  [{v['case_kind']}]  {v['card']['title'][:70]}")
        sys.exit()
    summarize(run(a.case, as_of=a.as_of))
