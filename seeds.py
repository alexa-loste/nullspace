"""Seed cases, drawn from real work.

Each case has a `card` (what the scientist would have said, WITHOUT the answer)
and, where we know how it turned out, a `truth` block used to score the agent.
The truth block is never shown to the agent during analysis.

Source: A. Loste, "Characterizing RNA Polymerases for Multiplexed Expression of
Synthetic Genetic Elements", Yale MCDB thesis, 2024 (Isaacs lab); and the Summer
2022 Dean's Research Fellowship report (same author).
"""

T3_FRAMESHIFT = {
    "id": "t3-frameshift-activity",
    "case_kind": "cross_field",
    "source": "Loste 2024 thesis, Isaacs lab, Yale MCDB",
    "card": {
        "title": "T3 RNA polymerase variants with single-nucleotide deletions keep inducible transcriptional activity despite premature stop codons",
        "field": "synthetic biology / bacterial gene expression",
        "adjacent_fields": [
            "protein engineering",
            "structural biology",
            "translational control",
        ],
        "year": 2024,
        "expectation": (
            "A single-base deletion early in the T3 RNA polymerase coding sequence "
            "shifts the reading frame and generates a premature stop codon, so only "
            "the first 22-25% of the 855-residue polypeptide should be translated. A "
            "truncated fragment of a single-subunit polymerase was expected to be "
            "catalytically dead, giving no reporter expression."
        ),
        "observation": (
            "Two independent deletion variants stayed inducible and titratable. "
            "T3-del1 (deletion at nt 572 of 2655, stop at residue 217 of 855) drove GFP "
            "up to 226-fold over its uninduced state; T3-del2 (deletion at nt 567, stop "
            "at residue 191) drove up to 145-fold. Absolute output was lower than "
            "full-length T3 RNAP (4x background vs 6.3x background), but the off state "
            "was tighter: no GFP above background when uninduced, whereas full-length "
            "T3 RNAP was leaky at 3.4x background."
        ),
        "methods": (
            "Plasmid-borne T3 RNAP under Tet-On control (tetR / pLtetO, induced with "
            "anhydrotetracycline at 1-100 ng/mL); superfolder GFP under the T3 cognate "
            "promoter on the same plasmid; pSC101 origin, KanR. Fluorescence and OD read "
            "on a plate reader over 24 h, GFP normalized to OD at each strain's OD "
            "maximum, background subtracted using a backbone-only negative control strain. "
            "Deletions confirmed by sequencing. Promoter orthogonality checked with "
            "constructs lacking the RNAP coding sequence: those showed no signal above "
            "background, so the signal requires the RNAP coding sequence and is not host "
            "polymerase reading the cognate promoter."
        ),
        "ruled_out": [
            "E. coli host RNA polymerase driving GFP from the T3 cognate promoter: "
            "constructs retaining the promoter but lacking the RNAP coding sequence gave "
            "no signal above background",
            "A sequencing error in the deletion call: both variants were sequence confirmed",
            "Carry-over of a full-length T3 RNAP plasmid: the variants were isolated clones",
        ],
        "scientist_hypothesis": None,
        "scientist_confidence": 85,
        "result_type": "unresolved",
        "quality_flags": [
            "Mechanism untested: protein-level evidence (size, abundance) was never collected",
            "Single plate-reader assay format; no orthogonal readout of polymerase activity",
        ],
        "open_questions": [
            "What protein species are actually present in the deletion variants?",
            "Why is the off state tighter than full-length T3 RNAP?",
            "Is the residual activity useful, i.e. reproducible and titratable enough to build on?",
        ],
        "keywords": [
            "T3 RNA polymerase",
            "frameshift mutation",
            "premature stop codon",
            "single-subunit RNA polymerase",
            "heterologous gene expression",
            "Escherichia coli",
            "inducible promoter",
            "fold induction",
        ],
    },
    # Never shown to the agent during analysis. Used only for scoring.
    "truth": {
        "mechanism": (
            "The downstream fragment is translated from an internal methionine and the "
            "two polypeptides spontaneously reassemble into a partially active "
            "polymerase, i.e. the frameshift effectively produces a split polymerase."
        ),
        "key_evidence": (
            "T7 RNA polymerase tolerates bisection into fragments that spontaneously "
            "assemble into an active enzyme, and one tolerant seam sits near residue 200, "
            "a region enriched for functional bisection variants. T3 RNAP is in the "
            "T7-like phage cluster and shares 82% amino acid identity with T7 RNAP. The "
            "predicted stops at residues 191 and 217 fall in that same region."
        ),
        "key_paper": (
            "Segall-Shapiro et al. 2014, 'A resource allocator for transcription based on "
            "a highly fragmented T7 RNA polymerase', Molecular Systems Biology"
        ),
        "proposed_experiments": [
            "Tag both termini of the variant and run a Western blot to see whether two "
            "smaller fragments are present rather than one full-length protein",
            "Express the two putative fragments from separate promoters and test whether "
            "activity is reconstituted",
        ],
        "status": "Hypothesis proposed in the 2024 thesis; not yet experimentally tested.",
    },
}


STRICTOSIDINE = {
    "id": "strictosidine-yeast-undetected",
    "case_kind": "temporal",
    "source": "Loste 2022 Dean's Research Fellowship report, Yale",
    "card": {
        "title": "Strictosidine not detected by LC-MS in S. cerevisiae carrying a 13-gene camptothecin precursor pathway",
        "field": "metabolic engineering / plant natural product biosynthesis",
        "adjacent_fields": [
            "analytical chemistry",
            "yeast cell biology",
            "plant biochemistry",
        ],
        "year": 2022,
        "expectation": (
            "Heterologous expression of the strictosidine pathway in S. cerevisiae should "
            "yield detectable strictosidine, the penultimate camptothecin precursor, "
            "following a published optimization of this pathway in yeast."
        ),
        "observation": (
            "No peak at the m/z for strictosidine, and none for its immediate precursors, "
            "in either intracellular or extracellular fractions. After feeding the "
            "geraniol precursor to the strain carrying the 13-gene essential-pathway "
            "vector, compounds did elute at m/z values matching some pathway "
            "intermediates, but their identity could not be confirmed."
        ),
        "methods": (
            "Four vectors: P (13 essential pathway genes, 25 kb, built by "
            "transformation-assisted recombination in yeast after screening 200+ "
            "colonies), R (4 plant-specific enzymes), A (3 yield-enhancing enzymes), T "
            "(TDC). Nonsense mutations in P and A were repaired by site-directed "
            "mutagenesis. LC-MS on intracellular and extracellular fractions, several "
            "extraction methods tested. Geraniol feeding used to probe which enzymes were "
            "functional."
        ),
        "ruled_out": [
            "Coding-sequence mutations in vectors P and A: repaired and sequence confirmed",
            "Incomplete assembly of vector P: the clone used carried all 13 intended parts",
            "A single extraction method failing: several were tested on both fractions",
        ],
        "scientist_hypothesis": (
            "One or more pathway enzymes may be non-functional in yeast, but with no "
            "analytical standard the negative detection cannot be separated from a "
            "method problem."
        ),
        "scientist_confidence": 40,
        "result_type": "unresolved",
        "quality_flags": [
            "No authentic analytical standard, so no positive control for detection: a "
            "true negative cannot be distinguished from a detection failure",
            "m/z alone; no MS/MS fragmentation to confirm intermediate identity",
            "Vector A acquired a severe growth defect after repair, so expression level is unknown",
        ],
        "open_questions": [
            "Is strictosidine absent, or present below the detection limit of this method?",
            "Which of the 17 pathway enzymes are actually functional in yeast?",
            "Does the growth defect in vector A indicate toxicity that caps flux?",
        ],
        "keywords": [
            "strictosidine",
            "camptothecin biosynthesis",
            "Saccharomyces cerevisiae",
            "monoterpene indole alkaloid",
            "heterologous pathway expression",
            "LC-MS detection",
            "geraniol feeding",
            "secologanin",
        ],
    },
    "truth": None,
}


CASES = {c["id"]: c for c in (T3_FRAMESHIFT, STRICTOSIDINE)}
