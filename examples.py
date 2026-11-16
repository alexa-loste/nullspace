"""Example negative results, so the product can be walked through without typing.

Each example carries the rough text a scientist would actually paste (a lab
notebook entry, a slide caption, a message to a PI) plus `material`: everything
the agent is allowed to know when answering interview questions on their behalf.

The material is deliberately incomplete. A real scientist does not have every
control, and the honest answer to some questions is that nobody checked.
"""

EXAMPLES = [
    {
        "id": "crispr-no-phenotype",
        "label": "A knockout with no phenotype",
        "field": "cell biology",
        "paste": """Notebook, 14 Mar — KO line still looks WT.

Third attempt at the TMEM181 knockout in HEK293T. Sanger confirms a 4 bp
deletion in exon 2 on both alleles, frameshift, PTC at codon 61 of 402. Clone
2B and clone 7F, independent guides.

Ran the migration assay again (n=3, both clones). No difference from parental.
Scratch closure 18.2 h vs 17.9 h WT. We expected a strong migration defect —
the siRNA knockdown gave 40% slower closure, twice, last year.

Western with the N-term antibody: nothing. So the protein is gone, or at least
the epitope is. Don't have a C-term antibody.

Three months on this. Moving to the other target unless someone has an idea.""",
        "material": {
            "target": "TMEM181, a transmembrane protein, 402 residues",
            "system": "HEK293T cells",
            "edit": "4 bp deletion in exon 2, biallelic, confirmed by Sanger sequencing; "
                    "frameshift producing a premature termination codon at codon 61 of 402",
            "clones": "two independent clones, 2B and 7F, from different guide RNAs",
            "expected": "a migration defect, because siRNA knockdown of the same gene "
                        "slowed scratch closure by about 40%, reproduced twice the previous year",
            "observed": "no difference from parental cells. Scratch closure 18.2 h in the "
                        "knockout versus 17.9 h in wild type, n=3 biological replicates per clone",
            "protein_evidence": "Western blot with an N-terminal antibody shows no band. "
                                "No C-terminal antibody available, so a truncated or "
                                "internally-initiated product would not be detected.",
            "controls_run": "parental HEK293T as the wild-type control in every assay; "
                            "two independent clones to control for off-target effects",
            "not_checked": [
                "mRNA level of the target in the knockout, so nonsense-mediated decay was never confirmed",
                "whether any protein product exists at all beyond the missing N-terminal epitope",
                "whether a related family member is compensating",
                "whether the siRNA knockdown phenotype was itself an off-target effect",
                "any assay other than scratch closure",
            ],
            "time_invested": "about three months",
            "confidence": "fairly confident the editing is real and the assay works; "
                          "not confident about what the cells actually express",
        },
    },
    {
        "id": "inhibitor-no-effect",
        "label": "An inhibitor that stopped working",
        "field": "chemical biology",
        "paste": """Slide for group meeting: "Compound 14 — no effect in cells"

Biochemical IC50 is critically 38 nM against the purified kinase, clean curve,
triplicate. In cells we see nothing up to 10 uM — no change in substrate
phosphorylation by Western, no viability effect in two lines.

Checked compound integrity by LC-MS after 24 h in media, looks intact.

Either it isn't getting in, or the target isn't doing what we think it does in
cells. We've been assuming the former for about six months.""",
        "material": {
            "compound": "compound 14, a small-molecule kinase inhibitor from an in-house series",
            "biochemical_result": "IC50 of 38 nM against the purified kinase, clean dose-response "
                                  "curve, measured in triplicate",
            "cellular_result": "no detectable effect up to 10 uM: no change in substrate "
                               "phosphorylation by Western blot, no viability effect in two cell lines",
            "stability": "compound integrity confirmed intact by LC-MS after 24 h in culture media",
            "working_assumption": "poor cell permeability, assumed for about six months",
            "not_checked": [
                "intracellular concentration of the compound was never measured",
                "target engagement in cells was never measured, for example by CETSA or a NanoBRET assay",
                "whether the cell lines used actually depend on this kinase",
                "whether efflux transporters are removing the compound",
                "whether the substrate antibody reports on this kinase specifically",
            ],
            "confidence": "confident in the biochemical potency; no independent evidence about "
                          "what happens to the compound inside a cell",
        },
    },
    {
        "id": "strain-wont-grow",
        "label": "An organism that would not culture",
        "field": "environmental microbiology",
        "paste": """From my thesis draft, the chapter that didn't work.

The target is at 6-8% relative abundance in 16S from all three sediment cores,
reproducibly. Twelve weeks of anaerobic enrichment, lactate + sulfate, and the
community just converts to the usual Desulfovibrio.

Tracked the target by qPCR with a specific primer set — it declines to below
detection by week 4 in every bottle.

We think it needs a syntrophic partner but we have no evidence for that.""",
        "material": {
            "target": "an uncultured sulfate-reducing lineage at 6-8% relative abundance in 16S "
                      "amplicon data, reproducible across three estuary sediment cores",
            "approach": "anaerobic batch enrichment on lactate plus sulfate, twelve weeks",
            "observed": "the enrichment community converts to Desulfovibrio; the target declines "
                        "below qPCR detection by week 4 in every bottle",
            "readout": "specific qPCR primer set for the target lineage, so its abundance was "
                       "actually tracked rather than inferred from bulk growth",
            "hypothesis": "the organism may require a syntrophic partner, but there is no evidence",
            "not_checked": [
                "whether the target's genome encodes the sulfate reduction pathway, "
                "because no MAG was recovered at sufficient quality",
                "alternative electron donors or acceptors",
                "whether the 16S signal comes from living cells or relic DNA",
                "lower-dilution or continuous culture rather than batch enrichment",
            ],
            "confidence": "confident the organism is present and that it disappears under these "
                          "conditions; no idea what it actually needs",
        },
    },
]

BY_ID = {e["id"]: e for e in EXAMPLES}
