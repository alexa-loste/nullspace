"""Extra shelved results so the lab repository looks like a repository.

These are DEMO PERSONAS inside a demo lab. The point is the view a student
inheriting a project sees: several years of dead ends, on one shelf.
"""
import store

LAB = "Isaacs Lab"

MEMBERS = [
    dict(name="Wei Chen", field="synthetic biology / genome engineering",
         institution="Yale, Isaacs lab", demo_persona=True, seeded=True, lab=LAB,
         agent_name="Wei's agent",
         adjacent_fields=["protein engineering", "microbiology"],
         techniques=["MAGE", "recombineering", "genome-scale oligo design"],
         equipment=["plate reader", "electroporator"],
         can_offer=["multiplex genome editing in E. coli", "recoded strain construction"],
         interests=["genetic code expansion"]),
    dict(name="Sofia Marchetti", field="microbial natural products",
         institution="Yale, Isaacs lab", demo_persona=True, seeded=True, lab=LAB,
         agent_name="Sofia's agent",
         adjacent_fields=["analytical chemistry", "microbiology"],
         techniques=["BGC refactoring", "heterologous expression screening", "bioactivity assays"],
         equipment=["LC-MS", "anaerobic chamber"],
         can_offer=["screening orphan BGCs across host chassis", "bioactivity-guided fractionation"],
         interests=["silent gene clusters"]),
    dict(name="Jonah Reyes", field="bacterial physiology",
         institution="Yale, Isaacs lab", demo_persona=True, seeded=True, lab=LAB,
         agent_name="Jonah's agent",
         adjacent_fields=["systems biology", "biophysics"],
         techniques=["growth-rate measurement", "proteomics sample prep", "flow cytometry"],
         equipment=["flow cytometer", "bioreactor"],
         can_offer=["measuring fitness cost of a heterologous construct",
                    "single-cell expression distributions"],
         interests=["burden of synthetic constructs"]),
]

PROBLEMS = {
    "Wei Chen": dict(
        title="Recoded strain loses the non-standard amino acid dependency after ~40 generations without selection",
        field="genome engineering", year=2025,
        adjacent_fields=["evolutionary biology", "protein engineering"],
        expectation="A strain dependent on a non-standard amino acid for an essential protein should stay dependent, because escape requires several simultaneous changes.",
        observation="Escape mutants appear in 4 of 6 lineages by generation 40 without selection, at frequencies around 1e-6 to 1e-5. Sequencing shows no single consistent escape route.",
        methods="Serial passage in permissive medium, plating on non-permissive medium to count escapees, whole-genome sequencing of 12 escapees.",
        ruled_out=["Contamination with the parental strain", "Reversion at the engineered codon itself"],
        scientist_hypothesis="Something is suppressing the dependency indirectly, but the escape routes look different every time.",
        scientist_confidence=80, result_type="unresolved",
        quality_flags=["Only 12 escapees sequenced", "No fitness measurement of escapees"],
        open_questions=["Is there a common upstream mechanism behind different escape genotypes?"],
        keywords=["genetic code expansion", "biocontainment", "escape frequency",
                  "non-standard amino acid", "recoded organism", "suppressor mutation"]),
    "Sofia Marchetti": dict(
        title="Refactored biosynthetic gene cluster expresses every enzyme but makes no detectable product in three hosts",
        field="microbial natural products", year=2024,
        adjacent_fields=["enzymology", "metabolic engineering", "analytical chemistry"],
        expectation="A refactored cluster with all enzymes expressed under constitutive promoters should produce the predicted metabolite in at least one host.",
        observation="Proteomics confirms all 9 enzymes present in E. coli, P. putida and B. subtilis. No new peak in any host by LC-MS over 7 days.",
        methods="Refactored cluster with synthetic promoters and RBSs, proteomics for expression, untargeted LC-MS comparison against empty-vector controls.",
        ruled_out=["Enzymes not being expressed", "A single host being unsuitable"],
        scientist_hypothesis="A precursor may be missing, or the product may be modified beyond recognition.",
        scientist_confidence=55, result_type="unresolved",
        quality_flags=["No authentic standard for the predicted product",
                       "Untargeted analysis only; no isotope labelling to track precursors"],
        open_questions=["Is the precursor supply absent, or is the product being consumed?"],
        keywords=["biosynthetic gene cluster", "refactoring", "heterologous expression",
                  "silent cluster", "precursor supply", "untargeted metabolomics"]),
    "Jonah Reyes": dict(
        title="Fitness cost of an inducible construct does not scale with expression level",
        field="bacterial physiology", year=2023,
        adjacent_fields=["systems biology", "synthetic biology"],
        expectation="Growth rate should fall monotonically as inducer concentration, and therefore protein burden, increases.",
        observation="Growth rate drops sharply between 0 and low induction, then flattens; a tenfold further increase in expression costs almost nothing more.",
        methods="Growth curves across an eight-point inducer titration, three biological replicates, expression confirmed by fluorescence.",
        ruled_out=["Inducer toxicity, tested with an empty-vector strain",
                   "Plate-position effects, controlled by randomised layout"],
        scientist_hypothesis="Some resource saturates early, so beyond a point more protein is free.",
        scientist_confidence=70, result_type="informative_null",
        quality_flags=["Single construct and single reporter; generality untested"],
        open_questions=["Which resource saturates, and does the threshold move with growth medium?"],
        keywords=["proteome allocation", "burden", "heterologous expression", "growth rate",
                  "resource competition", "ribosome allocation"]),
}

def run():
    # Put Alexa in the lab too.
    for s in store.all_of("scientists"):
        if s["name"] == "Alexa Loste":
            store.patch("scientists", s["id"], lab=LAB)
    made = []
    for m in MEMBERS:
        if any(s["name"] == m["name"] for s in store.all_of("scientists")):
            continue
        s = store.scientist(onboarded=True, **m)
        store.problem(s["id"], PROBLEMS[m["name"]], source=f"{LAB}, shelved")
        made.append(s["name"])
        print(f"  {s['name']:18} {PROBLEMS[m['name']]['title'][:58]}")
    return made

if __name__ == "__main__":
    run()
    print(f"\nlab members: {sum(1 for s in store.all_of('scientists') if s.get('lab')==LAB)}")
