"""Build the multi-lab repository from negative results that are already published.

    python3 seed_repo.py --dry-run        # show the plan, call no models
    python3 seed_repo.py                  # mine and file the nulls
    python3 seed_repo.py --work 20        # then let the agents work them

Why published nulls, and why old ones.

A repository of negative results seeded by hand proves nothing: the entries were
chosen by whoever wanted the demo to work. These are extracted from published
papers by `mine.py`, which refuses most of what it reads, and they are capped at
2021 so the field has had four years to answer them. That makes the central claim
checkable instead of merely plausible — the agent explains each null using only
the literature of its own time, and then goes back to see what was actually
published afterwards.

The scientists are invented. The nulls, the papers behind them, and everything
published since are real.
"""

import argparse
import json

import mine
import store

AS_OF = 2021

# Four labs, chosen so their fields are genuinely distant. A cross-field match
# between two synthetic-biology labs would prove nothing; the interesting case
# is a mass-spectrometry lab recognising a problem a plant chemist could not
# phrase. Each lab gets a PI and someone junior, because the handover from one
# to the other is the event this whole thing is built around.
LABS = [
    {
        "lab": "Isaacs Lab",
        "topic": "bacterial gene expression orthogonal RNA polymerase synthetic biology",
        "members": [
            dict(name="Alexa Loste", field="synthetic biology / bacterial gene expression",
                 institution="Yale, Isaacs lab", demo_persona=False, role="senior",
                 adjacent_fields=["protein engineering", "natural product biosynthesis"],
                 techniques=["plasmid assembly", "plate-reader fluorescence assays",
                             "Tet-On inducible systems", "E. coli strain engineering"],
                 equipment=["plate reader", "LC-MS access"],
                 can_offer=["building and testing inducible expression constructs in E. coli",
                            "characterising orthogonal phage RNA polymerases"],
                 interests=["multiplexed expression of synthetic genetic elements"]),
            dict(name="Theo Marchetti", field="synthetic biology, rotation student",
                 institution="Demo persona", demo_persona=True, role="junior",
                 adjacent_fields=["molecular biology"],
                 techniques=["cloning", "plate-reader assays", "flow cytometry"],
                 equipment=["plate reader", "flow cytometer"],
                 can_offer=["running a characterisation that somebody else designed"],
                 interests=["looking for a project that is already half-started"]),
        ],
    },
    {
        "lab": "Dufort Lab",
        "topic": "plant specialised metabolism monoterpene indole alkaloid pathway reconstitution",
        "members": [
            dict(name="Priya Anand", field="plant specialised metabolism",
                 institution="Demo persona", demo_persona=True, role="senior",
                 adjacent_fields=["natural product chemistry", "metabolic engineering"],
                 techniques=["LC-MS/MS of plant extracts", "authentic standard synthesis",
                             "transient expression in N. benthamiana"],
                 equipment=["triple-quadrupole LC-MS", "MIA standard collection"],
                 can_offer=["supplying authentic standards for alkaloid intermediates",
                            "telling you which pathway step limits flux in planta"],
                 interests=["camptothecin and vinblastine biosynthesis"]),
            dict(name="Lena Ostrowski", field="metabolic engineering, second-year PhD",
                 institution="Demo persona", demo_persona=True, role="junior",
                 adjacent_fields=["yeast genetics"],
                 techniques=["yeast transformation", "shake-flask fermentation", "GC-MS"],
                 equipment=["GC-MS", "fermenters"],
                 can_offer=["rebuilding a pathway in yeast with modern strain engineering"],
                 interests=["taking on a pathway somebody else could not get to flux"]),
        ],
    },
    {
        "lab": "Rask Lab",
        "topic": "structural mass spectrometry low abundance protein detection proteomics",
        "members": [
            dict(name="Tobias Rask", field="structural mass spectrometry and proteomics",
                 institution="Demo persona", demo_persona=True, role="senior",
                 adjacent_fields=["protein engineering", "analytical chemistry"],
                 techniques=["intact-mass LC-MS", "bottom-up proteomics",
                             "targeted PRM for a specific peptide"],
                 equipment=["Orbitrap", "nano-LC"],
                 can_offer=["telling you what protein species are actually in a lysate",
                            "detecting a low-abundance truncated or full-length product"],
                 interests=["what counts as absence in a mass spectrum"]),
        ],
    },
    # These two exist so that everyone in the world belongs to a lab and the
    # network is genuinely cross-institutional. They are not mined: four
    # topics is already more published nulls than a demo can show.
    {
        "lab": "Vanchev Lab",
        "topic": None,
        "members": [
            dict(name="Mirela Vanchev", field="translational control and ribosome biochemistry",
                 institution="Demo persona", demo_persona=True, role="senior",
                 adjacent_fields=["bacterial genetics", "RNA biology"],
                 techniques=["dual-luciferase frameshift reporter assays", "ribosome profiling",
                             "in vitro translation with reconstituted systems"],
                 equipment=["luminometer", "sucrose gradient fractionation"],
                 can_offer=["measuring programmed ribosomal frameshifting efficiency",
                            "distinguishing frameshifting from transcriptional realignment"],
                 interests=["recoding in bacteria"]),
        ],
    },
    {
        "lab": "Beisel Lab",
        "topic": None,
        "members": [
            dict(name="Hannah Beisel", field="clinical genetics of nonsense and frameshift variants",
                 institution="Demo persona", demo_persona=True, role="senior",
                 adjacent_fields=["human genetics", "translational control"],
                 techniques=["variant interpretation", "patient cohort phenotyping",
                             "readthrough quantification in patient cells"],
                 equipment=["clinical sequencing pipeline"],
                 can_offer=["saying whether a predicted-null allele behaves as one in patients"],
                 interests=["why some truncating variants are mild"]),
        ],
    },
    {
        "lab": "Okonjo Lab",
        "topic": "directed evolution protein engineering library screening",
        "members": [
            dict(name="Daniel Okonjo", field="directed evolution and protein engineering",
                 institution="Demo persona", demo_persona=True, role="senior",
                 adjacent_fields=["structural biology", "enzymology"],
                 techniques=["error-prone PCR libraries", "FACS-based selection",
                             "domain bisection screens"],
                 equipment=["FACS", "liquid handling robot"],
                 can_offer=["screening a library where a rational design failed",
                            "splitting a protein and finding where it tolerates it"],
                 interests=["why rational designs fail where selection succeeds"]),
        ],
    },
]


def build_people():
    made = {}
    for lab in LABS:
        for m in lab["members"]:
            spec = dict(m)
            role = spec.pop("role", "senior")
            existing = next((s for s in store.all_of("scientists")
                             if s["name"] == spec["name"]), None)
            if existing:
                s = store.patch("scientists", existing["id"], lab=lab["lab"], role=role)
            else:
                s = store.scientist(lab=lab["lab"], seeded=True, role=role, **spec)
            made.setdefault(lab["lab"], []).append(s)
            print(f"  {lab['lab']:14} {s['name']:20} {role}")
    return made


def file_nulls(people, per_lab, dry_run=False):
    """Mine each lab's field for published nulls and file them under its senior."""
    total = 0
    for lab in LABS:
        if not lab.get("topic"):
            continue
        owner = next(s for s in people[lab["lab"]] if s.get("role") == "senior")
        print(f"\n{lab['lab']} — mining “{lab['topic']}” capped at {AS_OF}")
        if dry_run:
            print("  (dry run, no model calls)")
            continue

        def say(msg, data=None):
            print(f"    {msg}"[:150])

        cards = mine.mine(lab["topic"], n_papers=per_lab, on_progress=say, to_year=AS_OF)
        for c in cards:
            card = dict(c)
            paper = card.pop("source_paper", None)
            card.pop("unclaimed", None)
            card.pop("source", None)
            # The null is as old as the paper it came out of, and that year is
            # what the agent will be held to when it reasons about it.
            year = (paper or {}).get("year") or card.get("year") or AS_OF
            card["year"] = year
            pr = store.problem(owner["id"], card, origin="literature",
                               unclaimed=True, source_paper=paper,
                               visibility="public", as_of=year)
            total += 1
            print(f"  filed  {year}  {(card.get('title') or '')[:72]}")
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-lab", type=int, default=14,
                    help="papers to read per lab (most get refused)")
    ap.add_argument("--work", type=int, default=0,
                    help="agent actions to run after seeding")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--reset", action="store_true",
                    help="wipe everything first")
    a = ap.parse_args()

    if a.reset and not a.dry_run:
        store.reset_demo()
        print("wiped\n")

    print("people")
    people = build_people()

    n = file_nulls(people, a.per_lab, dry_run=a.dry_run)
    print(f"\n{n} published nulls filed, all capped at {AS_OF}")

    if a.work and not a.dry_run:
        import agentd
        print(f"\nworking: up to {a.work} agent actions")
        agentd.world_tick(rounds=a.work,
                          on_progress=lambda m, data=None: print(f"  {m}"[:150]))

    probs = store.all_of("problems")
    print(f"\nrepository: {len(store.all_of('scientists'))} scientists, "
          f"{len(set(s.get('lab') for s in store.all_of('scientists')))} labs, "
          f"{len(probs)} results, "
          f"{sum(1 for p in probs if p.get('brief_id'))} read")


if __name__ == "__main__":
    main()
