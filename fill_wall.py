"""Mine more published nulls, then give every dated one a state.

    python3 fill_wall.py --per-topic 18

Two passes, because they cost very different amounts. Mining reads abstracts
and refuses most of them. The sweep then asks one question per null — has the
field moved under this since it was shelved — which is one search and one model
call, rather than the two calls a full scout costs. The wall only needs the
sweep; a result somebody actually owns still gets the full treatment.

Every card's colour ends up backed by papers the search really returned.
"""

import argparse
import time

import agentd
import mine
import store

AS_OF = 2021

# Nulls old enough that the field has had a decade or more to answer them.
# A 2021 null has had four years, which is rarely enough for anything to be
# settled; these are from before the methods that answered them existed, which
# is why they are the ones that go green. Each topic is an area where the
# answer arrived from a new technique rather than from more of the same work.
OLD_AS_OF = 2010
OLD_TOPICS = [
    ("Rask Lab", "membrane protein crystallisation failed diffraction structure determination"),
    ("Rask Lab", "protein structure prediction homology modelling accuracy limitation"),
    ("Okonjo Lab", "protein engineering rational design failed to improve activity"),
    ("Okonjo Lab", "enzyme mechanism disputed inconclusive kinetics"),
    ("Dufort Lab", "plant cytochrome P450 heterologous expression inactive E. coli"),
    ("Dufort Lab", "biosynthetic gene cluster silent no product detected"),
    ("Isaacs Lab", "unculturable bacteria could not be grown in pure culture"),
    ("Isaacs Lab", "gene therapy vector immune response unexplained"),
    ("Vanchev Lab", "ribosome structure heterogeneity could not be resolved"),
    ("Beisel Lab", "genotype phenotype correlation absent unexplained variability"),
]

# Deliberately spread across fields. A wall where every null is from one
# subfield would show that this works for synthetic biology, not that it works.
TOPICS = [
    ("Isaacs Lab", "bacterial gene expression inducible promoter orthogonal polymerase"),
    ("Isaacs Lab", "genome engineering recoded organism non-standard amino acid"),
    ("Dufort Lab", "plant natural product pathway reconstitution heterologous host"),
    ("Dufort Lab", "terpenoid alkaloid biosynthesis enzyme characterisation"),
    ("Rask Lab", "proteomics low abundance detection sample preparation"),
    ("Rask Lab", "mass spectrometry quantification biomarker validation"),
    ("Okonjo Lab", "directed evolution enzyme engineering screening library"),
    ("Okonjo Lab", "protein stability rational design mutation"),
    ("Vanchev Lab", "ribosome translation frameshifting readthrough reporter"),
    ("Beisel Lab", "nonsense variant readthrough patient phenotype severity"),
]


def owner_for(lab):
    people = [s for s in store.all_of("scientists") if s.get("lab") == lab]
    return next((s for s in people if s.get("role") == "senior"), people[0] if people else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-topic", type=int, default=16)
    ap.add_argument("--sweep-only", action="store_true")
    ap.add_argument("--old", action="store_true",
                    help="mine pre-2010 nulls, which are the ones that have gone green")
    ap.add_argument("--sweep-limit", type=int, default=60)
    a = ap.parse_args()

    t0 = time.time()
    filed = 0

    topics = OLD_TOPICS if a.old else TOPICS
    as_of = OLD_AS_OF if a.old else AS_OF

    if not a.sweep_only:
        for lab, topic in topics:
            owner = owner_for(lab)
            if not owner:
                print(f"skipping {lab}: nobody in it")
                continue
            print(f"\n=== {lab}: {topic}", flush=True)
            try:
                cards = mine.mine(topic, n_papers=a.per_topic, to_year=as_of,
                                  on_progress=lambda m, data=None: print(f"  {str(m)[:130]}",
                                                                         flush=True))
            except Exception as exc:  # noqa: BLE001 - one bad topic must not end the run
                print(f"  topic failed: {exc}", flush=True)
                continue
            for c in cards:
                card = dict(c)
                paper = card.pop("source_paper", None)
                card.pop("unclaimed", None)
                card.pop("source", None)
                year = (paper or {}).get("year") or card.get("year") or as_of
                card["year"] = year
                store.problem(owner["id"], card, origin="literature", unclaimed=True,
                              source_paper=paper, visibility="public", as_of=year)
                filed += 1
                print(f"  FILED {year} {(card.get('title') or '')[:70]}", flush=True)

    print(f"\n{filed} filed in {(time.time()-t0)/60:.1f} min. Sweeping.", flush=True)
    n = agentd.sweep(limit=a.sweep_limit,
                     on_progress=lambda m, data=None: print(f"  {str(m)[:130]}", flush=True))
    print(f"\nswept {n}. total {(time.time()-t0)/60:.1f} min", flush=True)

    probs = store.all_of("problems")
    states = {}
    for p in probs:
        b = store.get("briefs", p["brief_id"]) if p.get("brief_id") else None
        o = ((b or {}).get("since") or {}).get("overall") or "not swept"
        states[o] = states.get(o, 0) + 1
    print("results:", len(probs), states)


if __name__ == "__main__":
    main()
