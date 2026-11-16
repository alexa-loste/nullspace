"""Build the demo world: scientists, their agents, and their open problems.

    python3 seed_world.py            # build the world, agents idle
    python3 seed_world.py --ticks 12 # build it and let the agents work

Every profile except Alexa's is a SYNTHETIC DEMO PERSONA. The people are
invented and marked `demo_persona: true`, so the UI can say so. What stays real
is everything the agents retrieve: the literature comes from OpenAlex and the
people an agent suggests contacting are real authors of real retrieved papers.

The two problems belonging to Alexa are real, from her own work in the Isaacs
lab at Yale.
"""

import argparse
import seeds
import store

PERSONAS = [
    dict(
        name="Alexa Loste", field="synthetic biology / bacterial gene expression",
        institution="Yale, Isaacs lab", demo_persona=False,
        agent_name="Alexa's agent",
        adjacent_fields=["protein engineering", "natural product biosynthesis",
                         "structural biology"],
        techniques=["plasmid assembly", "transformation-assisted recombination cloning",
                    "plate-reader fluorescence assays", "Tet-On inducible systems",
                    "E. coli and S. cerevisiae strain engineering"],
        equipment=["plate reader", "LC-MS access", "standard molecular biology bench"],
        can_offer=["building and testing inducible expression constructs in E. coli",
                   "characterising orthogonal phage RNA polymerases",
                   "large multi-gene pathway assembly in yeast"],
        interests=["multiplexed expression of synthetic genetic elements",
                   "biosynthetic gene cluster characterisation"],
    ),
    dict(
        name="Mirela Vanchev", field="translational control and ribosome biochemistry",
        institution="Demo persona", demo_persona=True,
        agent_name="Vanchev lab agent",
        adjacent_fields=["bacterial genetics", "RNA biology", "synthetic biology"],
        techniques=["dual-luciferase frameshift reporter assays", "ribosome profiling",
                    "in vitro translation with reconstituted systems",
                    "slippery-site mutagenesis"],
        equipment=["luminometer", "sucrose gradient fractionation", "Illumina access"],
        can_offer=["measuring programmed ribosomal frameshifting efficiency in a construct",
                   "identifying slippery heptamer motifs in a coding sequence",
                   "distinguishing ribosomal frameshifting from transcriptional realignment"],
        interests=["recoding in bacteria", "how often indels are rescued by frameshifting"],
    ),
    dict(
        name="Tobias Rask", field="structural mass spectrometry and proteomics",
        institution="Demo persona", demo_persona=True,
        agent_name="Rask lab agent",
        adjacent_fields=["protein engineering", "analytical chemistry", "biochemistry"],
        techniques=["intact-mass LC-MS of purified proteins",
                    "bottom-up proteomics on low-abundance lysates",
                    "targeted PRM for a specific peptide", "terminal-tag Western blotting"],
        equipment=["Orbitrap", "nano-LC", "automated sample prep"],
        can_offer=["telling you what protein species are actually in a lysate",
                   "detecting a low-abundance truncated or full-length product",
                   "mapping tryptic peptides across a frameshift junction"],
        interests=["proteoform diversity", "what expression constructs actually make"],
    ),
    dict(
        name="Priya Anand", field="plant specialised metabolism",
        institution="Demo persona", demo_persona=True,
        agent_name="Anand lab agent",
        adjacent_fields=["metabolic engineering", "analytical chemistry", "yeast biology"],
        techniques=["monoterpene indole alkaloid pathway reconstitution",
                    "precursor feeding", "transporter identification",
                    "compartment-targeted enzyme expression"],
        equipment=["authentic MIA standards including strictosidine", "LC-MS/MS", "plant growth facility"],
        can_offer=["an authentic strictosidine standard to calibrate a detection method",
                   "advice on which step of the iridoid pathway limits flux in yeast",
                   "which MIA intermediates are consumed in vivo and never accumulate"],
        interests=["why reconstituted plant pathways underperform in microbial hosts"],
    ),
    dict(
        name="Daniel Okonjo", field="directed evolution and protein engineering",
        institution="Demo persona", demo_persona=True,
        agent_name="Okonjo lab agent",
        adjacent_fields=["synthetic biology", "structural biology", "enzymology"],
        techniques=["split-protein complementation assays", "domain bisection screens",
                    "deep mutational scanning", "FACS-based selection"],
        equipment=["cell sorter", "liquid handling robot", "sequencing access"],
        can_offer=["testing whether two protein fragments reconstitute activity",
                   "mapping which seams in an enzyme tolerate bisection",
                   "building a split-polymerase variant as a circuit part"],
        interests=["modularity of single-subunit enzymes", "orthogonal transcription parts"],
    ),
    dict(
        name="Hannah Beisel", field="clinical genetics of nonsense and frameshift variants",
        institution="Demo persona", demo_persona=True,
        agent_name="Beisel lab agent",
        adjacent_fields=["human genetics", "RNA biology", "translational control"],
        techniques=["nonsense-mediated decay assays", "variant interpretation",
                    "minigene splicing and reinitiation reporters"],
        equipment=["patient-derived cell lines", "long-read sequencing"],
        can_offer=["why a frameshift variant can retain partial function in patients",
                   "evidence that translation reinitiates downstream of a premature stop",
                   "how often a predicted null allele is not actually null"],
        interests=["why predicted loss-of-function variants are sometimes benign"],
    ),
]

# An open problem for each demo persona, so matching can run both ways.
DEMO_PROBLEMS = {
    "Mirela Vanchev": {
        "title": "Frameshift reporter efficiency in E. coli varies tenfold between constructs with the same slippery site",
        "field": "translational control",
        "adjacent_fields": ["synthetic biology", "RNA structure", "bacterial genetics"],
        "year": 2026,
        "expectation": "With the slippery heptamer and downstream stem-loop held constant, frameshifting efficiency should be roughly constant across reporter backbones.",
        "observation": "Efficiency ranges from 2% to about 20% across backbones carrying an identical frameshift cassette, with no obvious relationship to expression level.",
        "methods": "Dual-luciferase reporters, several plasmid backbones and origins, efficiency as the ratio of frameshift to in-frame product.",
        "ruled_out": ["Differences in the slippery heptamer itself", "Plasmid copy number as measured by qPCR"],
        "scientist_hypothesis": "Something about local mRNA context or translation initiation rate is changing the dwell time at the slippery site.",
        "scientist_confidence": 70,
        "result_type": "unresolved",
        "quality_flags": ["Backbones differ in more than one feature at a time"],
        "open_questions": ["What property of the backbone sets frameshifting efficiency?"],
        "keywords": ["programmed ribosomal frameshifting", "slippery sequence", "dual luciferase",
                     "E. coli", "mRNA secondary structure", "translation initiation rate"],
    },
    "Priya Anand": {
        "title": "Strictosidine accumulates in engineered yeast but the downstream enzyme produces nothing",
        "field": "plant specialised metabolism",
        "adjacent_fields": ["metabolic engineering", "enzymology", "yeast cell biology"],
        "year": 2026,
        "expectation": "With strictosidine supplied, the next enzyme in the pathway should convert it to the expected product.",
        "observation": "Strictosidine is clearly detected against an authentic standard, but no downstream product appears at any time point.",
        "methods": "LC-MS/MS against authentic standards, time course over 96 h, enzyme expression confirmed by Western.",
        "ruled_out": ["Absence of strictosidine", "Failure to express the downstream enzyme"],
        "scientist_hypothesis": "The enzyme may need a partner, a cofactor, or a compartment it does not have in yeast.",
        "scientist_confidence": 65,
        "result_type": "unresolved",
        "quality_flags": ["Enzyme activity never confirmed in vitro"],
        "open_questions": ["Is the enzyme inactive, mislocalised, or missing a partner?"],
        "keywords": ["strictosidine", "monoterpene indole alkaloid", "Saccharomyces cerevisiae",
                     "enzyme compartmentalisation", "deglycosylation", "pathway flux"],
    },
    "Daniel Okonjo": {
        "title": "Split enzyme fragments reconstitute in vitro but not when co-expressed in cells",
        "field": "protein engineering",
        "adjacent_fields": ["synthetic biology", "protein folding", "cell biology"],
        "year": 2026,
        "expectation": "Fragments that reassemble into an active enzyme when mixed as purified protein should also work when co-expressed in a cell.",
        "observation": "Purified fragments reconstitute roughly 60% of wild-type activity; co-expression of the same fragments gives almost none.",
        "methods": "Split-complementation with FACS readout, both fragments confirmed present by Western.",
        "ruled_out": ["One fragment not being expressed", "The reporter itself being broken"],
        "scientist_hypothesis": "Co-translational folding or proteolysis may be destroying one fragment before assembly.",
        "scientist_confidence": 75,
        "result_type": "unresolved",
        "quality_flags": ["Fragment stability in vivo never measured directly"],
        "open_questions": ["Does one fragment survive long enough in the cell to assemble?"],
        "keywords": ["split protein", "protein complementation", "co-expression",
                     "co-translational folding", "proteolysis", "fragment stability"],
    },
}


def build():
    store.reset_demo()
    by_name = {}
    for p in PERSONAS:
        s = store.scientist(onboarded=True, seeded=True, **p)
        by_name[s["name"]] = s
        print(f"  {s['name']:18} {s['agent_name']}")

    alexa = by_name["Alexa Loste"]
    for case in (seeds.T3_FRAMESHIFT, seeds.STRICTOSIDINE):
        store.problem(alexa["id"], case["card"], source=case["source"],
                      truth=case.get("truth"))
        print(f"  problem for Alexa: {case['card']['title'][:62]}")

    for name, card in DEMO_PROBLEMS.items():
        store.problem(by_name[name]["id"], card, source="demo persona")
        print(f"  problem for {name.split()[0]}: {card['title'][:56]}")

    print(f"\n{len(PERSONAS)} scientists, {len(store.all_of('problems'))} open problems.")
    print(f"Alexa's token: {alexa['token']}")
    return alexa


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=0,
                    help="let the agents work this many rounds after seeding")
    a = ap.parse_args()
    alexa = build()
    if a.ticks:
        import agentd
        print(f"\nticking the world {a.ticks} times\n")
        done = agentd.world_tick(rounds=a.ticks, on_progress=lambda m, data=None: print(m))
        print(f"\n{len(done)} agent actions")
