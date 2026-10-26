"""
Abstract, body and result tables of the conference paper.

Every number that comes from the extended evaluation is read from
paper/extended_eval.json through eval_tables, so the text cannot drift away from
the measurements.
"""

from __future__ import annotations

import eval_tables as T

D = T.DATA
R = D["ranking"]
FULL = R["Full weighted score (proposed)"]
TF = R["TF-IDF (full text)"]
SB = R["SBERT (abstract)"]
RND = R["Random ranking"]
BIB = R["Bibliographic similarity"]
METH = R["Methodology only"]
AB = {a["config"]: a for a in D["ablation"]}
RW = D["random_weights"]
NET = D["paper_network"]
G = D["graph"]
BR = D["bridges"]
CON = D["contradictions"]
DET = CON["detectors"]
GR = CON["gates_real"]
PROV = D["provenance"]


def n(x, d=2):
    return f"{x:.{d}f}"


ABSTRACT = (
    "Reading a new subfield means holding thirty papers in mind at once, and what a "
    "researcher most needs to know is rarely stated in any one of them: which papers "
    "address the same question, where two report different numbers for the same "
    "experiment, and what the collection has never examined. We present a pipeline that "
    "recovers these cross-document relationships from a folder of PDFs and makes every "
    "answer traceable to the sentence that produced it. Papers are segmented by relative "
    "font size, typed entities are extracted by rule, each pair of papers is scored on "
    "five interpretable dimensions whose weights sum to one, and numeric disagreements "
    "are confirmed only when the two papers are comparable. On thirty arXiv papers in "
    "four clusters, segmentation succeeded on every paper (215 of 240 sections). The "
    f"score ranked related papers well above chance (AUC {n(FULL['AUC'])}, MAP "
    f"{n(FULL['MAP'])}, against {n(RND['AUC'])} and {n(RND['MAP'])}) and above each of its "
    f"parts, but did not beat full-text TF-IDF (AUC {n(TF['AUC'])}, MAP {n(TF['MAP'])}), so "
    "its contribution is explanation, not accuracy. The numeric detector found both "
    "planted contradictions with no false positive and confirmed none on real papers. "
    "Community analysis of the paper network recovered a coarse split into image and "
    "language papers. The pipeline runs offline."
)

BODY = [
    # ------------------------------------------------------------------
    ("h1", "Introduction"),

    ("p1", (
        "A researcher entering an unfamiliar subfield reads somewhere between twenty "
        "and forty papers before its structure becomes clear to them. Much of what "
        "they learn along the way is not written down in any of those papers. It "
        "exists only in the relationships between them."
    )),
    ("p", (
        "Four of these matter more than the rest. The first is relatedness, which is "
        "harder than keyword overlap suggests: two groups can attack an identical "
        "problem in vocabulary that shares almost nothing. The second is "
        "disagreement. When one paper reports 76.4% top-1 accuracy for a baseline "
        "and another reports 71.1% for what appears to be the same architecture on "
        "the same dataset, that is a fact about the literature, invisible unless "
        "both numbers are in view at once. The third is absence: a gap is defined by "
        "what is missing, so the whole collection must be surveyed before the hole "
        "appears. The fourth is structure, the map an experienced reader carries, "
        "which is a graph whether or not anyone draws it."
    )),
    ("p", (
        "Large language models can answer questions like these fluently, but without "
        "provenance: a reviewer cannot check the answer, and a wrong one reads exactly "
        "like a right one. We took a different route. The system described here "
        "contains no generative language model. Extraction is rule-based, and the only "
        "learned components are two small pretrained encoders used as published: MiniLM "
        "for sentence embeddings and a DeBERTa cross-encoder for natural language "
        "inference. Every number decomposes into named components, and every "
        "contradiction and gap carries the document, section, page and sentence that "
        "produced it. The code also has an optional OpenAI backend for extraction and "
        "for phrasing explanations. It is off by default and was not used in any "
        "experiment reported here."
    )),
    ("p", "Our contributions are as follows."),
    ("bullet", (
        "A segmentation method for research PDFs built on relative font size, with a "
        "guaranteed fallback, which recovered structure from all thirty documents in "
        "our evaluation corpus."
    )),
    ("bullet", (
        "A five-dimensional relationship score with weights constrained to sum to one, "
        "evaluated against seven baselines and a weight ablation, which shows where the "
        "score helps and where plain text similarity is better."
    )),
    ("bullet", (
        "Contradiction detection by numeric comparison, with an optional inference model, "
        "gated by comparability, with the gates, thresholds and false positives measured."
    )),
    ("bullet", (
        "A graph-level analysis, including community structure, over a corpus of thirty "
        "arXiv papers in four clusters and a six-paper corpus with planted contradictions."
    )),

    # ------------------------------------------------------------------
    ("h1", "Related Work"),

    ("p1", (
        "Sentence-BERT [1] made dense sentence embeddings cheap to compute over a whole "
        "corpus, SciBERT [2] adapted pretraining to scientific text, and SPECTER [3] "
        "learns document vectors with the citation graph as a training signal. All three "
        "give one vector per document, which suits retrieval but cannot say whether two "
        "papers are close in dataset, method or objective. We keep the dimensions "
        "separate for that reason."
    )),
    ("p", (
        "SciERC [4] annotates entities and relations in abstracts and DocRED [5] moves "
        "relation extraction to whole documents. Both need supervision we do not have and "
        "assume text that has already been segmented, which was the largest single source "
        "of failure in our own system. FEVER [6] and SciFact [7] verify a claim against "
        "retrieved evidence with supervised data; our setting has no labels and needs "
        "only the observation that two papers cannot both be right. Models trained on "
        "MultiNLI [8] transfer reasonably, hence DeBERTa [9] here, but on sentences "
        "dense with figures they are unreliable and numeric comparison is more "
        "trustworthy."
    )),
    ("p", (
        "Bibliographic coupling [10] and co-citation [11] predate neural methods and "
        "remain useful: two papers citing the same prior work are related even when they "
        "share no vocabulary. We keep it as one of the five dimensions."
    )),

    # ------------------------------------------------------------------
    ("h1", "Method"),

    ("p1", (
        "The pipeline runs eleven stages in a fixed order, shown in Figure 1. The order is "
        "forced by data dependency: three of the five scoring dimensions are cosine "
        "similarities between entity vectors, so embedding has to finish before scoring "
        "begins. In an early version the embedding stage silently failed, and because a "
        "missing vector yields a similarity of zero and not an error, the composite "
        "score collapsed to its dataset term while still looking plausible."
    )),
    ("pipeline", None),

    ("h2", "Recovering document structure"),
    ("p1", (
        "A PDF stores positioned glyphs and nothing about sections. Matching heading text "
        "against a list of names fails because authors disagree on names, looking for "
        "bold fails because many templates do not bold headings, and looking for short "
        "lines fails on two-column pages. Our first version produced zero sections for "
        "one paper and 186 for another. What works is relative font size: we take the "
        "character-weighted mode of font sizes as the body size and treat any short, "
        "noticeably larger line as a heading candidate, matched against anchored patterns "
        "after repairing small-capital artefacts such as I NTRODUCTION. No document is "
        "discarded: if no heading is found, the paper is cut into three-page chunks and "
        "marked unstructured."
    )),

    ("h2", "Entity extraction"),
    ("p1", (
        "Entities are extracted by rule: word lists for datasets, metrics and model names, "
        "cue phrases for objectives, limitations and stated gaps, and a metric beside a "
        "number for a quantitative result. This needs no training data and no language "
        "model. Each entity type is accepted only from sections where it plausibly "
        "appears; that restriction is suspended for unstructured documents, trading "
        "precision for recall. A paper with no methodology section scores zero on that "
        "dimension and the weights are not renormalised, because renormalising would make "
        "a paper matching on one dimension look like one matching on all five."
    )),

    ("h2", "Five-dimensional relationship scoring"),
    ("p1", (
        "Each of the 435 pairs of documents is scored on five dimensions in [0, 1] and "
        "combined by a weighted sum (Table 1). The three semantic dimensions are cosine "
        "similarities of mean entity embeddings; dataset overlap uses the Jaccard index "
        "because dataset names are exact tokens; citation overlap is bibliographic "
        "coupling [10], with a direct citation counted as maximal."
    )),
    ("table1", None),
    ("p", (
        "The weights are a stated prior that we chose, not a fitted parameter. They are "
        "validated at start-up to sum to exactly 1.0 and can be changed at run time. "
        "Cosine similarity is clamped to [0, 1], since opposite vectors mean unrelated "
        "and not anti-related. Before we did this, negative similarities were rejected by "
        "the data model and 203 of 435 pairs were dropped without any error."
    )),

    ("h2", "Contradiction detection"),
    ("p1", (
        "A numeric detector compares the values two papers report for the same metric on "
        "the same dataset and flags a relative difference above 5%. An optional "
        "inference detector passes two claim sentences to a cross-encoder as a pair. Before "
        "any number is compared, the claim is analysed: a delta is not a level, a figure "
        "quoted from another paper is not the paper's own, and top-1 is not top-5. A "
        "finding is confirmed only if the stance is contradiction, confidence is at least "
        "0.60, the papers share a dataset or comparable metric, and their methodology "
        "similarity is at least 0.30. Findings that fail are kept as unconfirmed."
    )),

    ("h2", "Research gap discovery"),
    ("p1", (
        "Three kinds of absence are detected: gaps the authors state outright, gaps where "
        "papers share a concept but are otherwise dissimilar, and pairings of a method "
        "and a dataset that never occur together. Candidates are ranked by importance and "
        "at most five are returned. An early version returned about sixty."
    )),

    ("h2", "Thresholds"),
    ("p1", (
        "We state how each threshold was set. The methodology similarity (0.30) and the "
        "confidence (0.60) needed to confirm a contradiction were fixed at design time "
        "from the requirements. The 5% materiality threshold and the candidate-pair score "
        "(0.35) were chosen by us a priori. The gap thresholds and the heading margin were "
        "set by running the pipeline on the development papers and adjusting until the "
        "output was usable. None was fitted by search against labels, because there were "
        "none. Two consequences follow. The thresholds set by inspection were set while "
        "looking at the papers we evaluate on, so results on that corpus are not held-out. "
        "And the useful question is how far results move when a threshold moves, which "
        "the sensitivity analysis below measures."
    )),
    ("workspace", None),

    # ------------------------------------------------------------------
    ("h1", "Evaluation Corpus and Protocol"),

    ("p1", (
        "A random sample cannot evaluate this system: contradictions need two papers that "
        "measure one quantity on one benchmark, and a ranking needs some pairs that should "
        "come out high and others low. We built the corpus as four clusters of real arXiv "
        "papers: A, eight convolutional image classifiers around residual networks [14]; "
        "B, eight pretrained language models around the Transformer [12] and BERT [13]; "
        "C, eight vision transformers and self-supervised methods including MoCo [15]; "
        "and D, six papers on retrieval, extraction and knowledge graphs [16, 17]. A pair is "
        "relevant when both papers share a cluster, giving 99 relevant pairs out of 435. "
        "A and D barely touch and are the negative control; A and C share ImageNet but not "
        "method. The relevance labels are ours, not independent judgements. A second, "
        "six-paper corpus has two planted contradictions, so that precision and recall can "
        "be computed for contradiction detection."
    )),
    ("p", (
        "We use P@k, the share of relevant pairs among the k highest-scoring, and R@k, the "
        "share of all relevant pairs found in the top k, on the global ranking of 435 "
        "pairs; ROC-AUC, the probability that a relevant pair outscores a non-relevant "
        "one; and, treating each paper as a query over the other 29, average precision "
        "(MAP is its mean) and nDCG@10 with binary gain. For contradictions, precision is "
        "TP / (TP + FP) and recall is TP / (TP + FN) at the level of document pairs, with "
        "F1 their harmonic mean; a planted pair with a confirmed finding is a true "
        "positive. Ties are broken at random and averaged, and a zero denominator is "
        "reported as n/a, not as a value. Intervals are 95% percentile bootstrap "
        "intervals over papers or pairs. The baselines are random ranking, TF-IDF over "
        "the full text [19], SBERT on the abstract [1], bibliographic similarity alone, "
        "each of methodology, dataset and results alone, and the full weighted score."
    )),

    # ------------------------------------------------------------------
    ("h1", "Results"),

    ("h2", "Segmentation"),
    ("p1", (
        "All thirty documents were segmented from detected headings and none fell back to "
        "page chunks. Recall was 215 of 240 expected sections (90%): perfect for "
        "introductions and reference lists, weakest for results at 21 of 30, because "
        "results are often folded into a section called Experiments."
    )),

    ("h2", "Relationship ranking"),
    ("p1", (
        "Table 2 compares the proposed score with the baselines. The score is far above "
        f"chance (P@10 {n(FULL['P@10'])}, MAP {n(FULL['MAP'])}, nDCG@10 {n(FULL['nDCG@10'])}, "
        f"AUC {n(FULL['AUC'])}, against {n(RND['P@10'])}, {n(RND['MAP'])}, {n(RND['nDCG@10'])} "
        f"and {n(RND['AUC'])}) and better than each of its parts: the best single dimension, "
        f"methodology, reaches an AUC of {n(METH['AUC'])}, and bibliographic similarity alone "
        f"only {n(BIB['AUC'])}. But full-text TF-IDF is better on every measure (P@10 "
        f"{n(TF['P@10'])}, MAP {n(TF['MAP'])}, nDCG@10 {n(TF['nDCG@10'])}, AUC {n(TF['AUC'])}). "
        f"On AUC the two cannot be told apart, with the same interval "
        f"({n(FULL['AUC_ci'][0])} to {n(FULL['AUC_ci'][1])}); on MAP the intervals overlap "
        f"({n(TF['MAP_ci'][0])} to {n(TF['MAP_ci'][1])} against {n(FULL['MAP_ci'][0])} to "
        f"{n(FULL['MAP_ci'][1])}). SBERT on abstracts matches our MAP ({n(SB['MAP'])}) with a "
        f"lower AUC ({n(SB['AUC'])}). We therefore do not claim that the weighted score "
        f"finds related papers better than simple text similarity."
    )),
    ("table3", None),
    ("p", (
        "Removing one dimension at a time shows methodology matters most and citation "
        f"least. Removing the dataset dimension improves nDCG@10 from {n(AB['Full weighted score']['nDCG@10'], 3)} "
        f"to {n(AB['Drop dataset']['nDCG@10'], 3)}, because clusters A and C share ImageNet. "
        f"Our weights are not optimal: {n(100 * RW['share_beating_default_nDCG'], 0)}% of "
        f"{RW['trials']} random weightings beat them on nDCG@10. We kept them because they "
        "were fixed before evaluation, and tuning on the same thirty papers would make the "
        "numbers optimistic. Both errors in the top ten pair MoCo or BYOL with a "
        "convolutional paper, a relationship that is real and that our labels count as a miss. "
        "Figure 3 shows all 435 scores ordered by cluster."
    )),
    ("heatmap", None),

    ("h2", "Graph-level analysis"),
    ("p1", (
        f"The graph, built with NetworkX [18], has {G['nodes']:,} nodes ({G['node_types']['document']} papers, "
        f"{G['node_types']['entity']:,} entities, {G['node_types']['bridge_entity']} bridge "
        f"concepts) and {G['edges']:,} edges, one connected component, density "
        f"{n(G['density_undirected'], 4)}, and only about 100 extracted relations beside the "
        f"structural edges. Louvain community detection [20] on the whole graph finds "
        f"{G['kg_communities']} communities (modularity {n(G['kg_modularity'])}), nearly pure "
        f"with respect to clusters (purity {n(G['kg_purity'])}) but fragmenting each cluster "
        f"(adjusted Rand index {n(G['kg_ARI'])}). On the 435-edge paper network Louvain finds just "
        f"two communities, clusters A with C (image) and B with D (language and retrieval), "
        f"with modularity {n(NET['full_weighted']['modularity'], 2)}, ARI "
        f"{n(NET['full_weighted']['ARI'])} and NMI {n(NET['full_weighted']['NMI'])}: a sensible "
        f"split, coarser than our four clusters, because the mean score between A and C "
        f"({n(D['cluster_means']['A-C'], 2)}) is almost that within A ({n(D['cluster_means']['A-A'], 2)}). "
        f"Keeping only edges of at least 0.50 leaves 49 of 435, {n(100 * NET['tau_0.50']['within_cluster_edge_share'], 0)}% within a cluster, "
        f"and communities that are pure except for the A and C mix, at the cost of seven isolated "
        f"papers (Figure 4). The {BR['count']} bridge concepts span {n(BR['mean_spread'], 1)} papers on "
        f"average and {n(100 * BR['cross_cluster_share'], 0)}% cross clusters, but the widest, "
        f"\"accuracy\" ({BR['top_concepts'][0][1]} papers), is generic."
    )),
    ("communities", None),

    ("h2", "Contradictions and gaps"),
    ("p1", (
        f"On the real corpus the detector compares {CON['real_claim_pairs']:,} claim pairs from "
        f"{CON['real_candidate_pairs']} candidate document pairs. Table 3 adds the gates in the "
        f"order the code applies them. With none, {GR[0]['findings']:,} claim pairs look like "
        f"disagreements, simply because two sentences contain different numbers; the comparability "
        f"check G5 takes {GR[4]['findings']} to {GR[5]['findings']}, and the final result is "
        f"{GR[-1]['findings']} findings. There are no labels on the real corpus, so we report counts, "
        f"not precision. On the labelled corpus the first gate alone brings precision from "
        f"{n(CON['gates_synth'][0]['precision'])} to 1.00 with recall 1.00, but the corpus is too "
        f"simple to tell the later gates apart."
    )),
    ("table4", None),
    ("p", (
        f"At the default thresholds the numeric detector finds both planted contradictions and "
        f"nothing else (precision, recall and F1 all 1.00). Adding the inference model keeps "
        f"recall at 1.00 but confirms {DET['synthetic_numeric_nli']['confirmed_pairs']} document "
        f"pairs, {DET['synthetic_numeric_nli']['FP']} wrong, so precision falls to "
        f"{n(DET['synthetic_numeric_nli']['precision'])} (F1 {n(DET['synthetic_numeric_nli']['F1'])}). "
        "Sweeping the methodology similarity from 0.1 to 0.5 and the confidence from 0.4 to 0.9, "
        "the numeric detector is stable (both found, none false) up to a confidence of 0.7 and "
        "loses both at 0.8; the inference model's false positives survive every confidence "
        "threshold up to 0.8, and a higher similarity threshold removes some (eight false "
        "positives at 0.1, three at 0.5) without losing a true one. Moving the candidate-pair "
        "threshold from 0.2 to 0.6 changes nothing. Gap discovery returned five gaps from 1,037 "
        "entities and 92 bridge concepts; all are stated gaps or limitations, three are genuine "
        "open problems in the authors' words, two describe weaknesses of other methods, and two "
        "are duplicates of one statement."
    )),
    ("p", (
        f"An automatic provenance check found every document, section and quotation correct for "
        f"all {PROV['gaps']['trails']} gap records and all {PROV['planted_contradictions']['trails']} "
        f"records of the planted contradictions, but the page number was one page early in "
        f"{PROV['gaps']['trails'] - PROV['gaps']['page']} of the {PROV['gaps']['trails']} gap "
        "records. A full analysis of thirty papers takes about 33 seconds on a four-core CPU "
        "with the inference model off; with it on, the claim comparison over the real corpus "
        "was still running after fifteen minutes."
    )),

    # ------------------------------------------------------------------
    ("h1", "Discussion"),

    ("p1", (
        "Strengths. The score can be taken apart: its five components are stored, the "
        "ablation shows which carry weight, and the dimensions are complementary, since the "
        "combination beats every single one. Traceability held up under the automatic "
        "check. The gates remove essentially every spurious numeric disagreement on the real "
        "corpus, and the numeric detector keeps recall on the labelled one. The system is "
        "small, offline, and contains no generative language model."
    )),
    ("p", (
        "Weaknesses. The score does not beat plain full-text TF-IDF, and the dataset dimension "
        "hurts on this corpus. Extraction is the thin layer: the graph has 1,037 entities "
        "but only about 100 relations, and the word lists are specific to machine learning. "
        "The community structure is coarse, with modularity 0.08 on the full network, and "
        "generic bridge concepts link nothing in particular. The inference model costs "
        "precision. The contradiction result on real papers cannot be scored, so zero "
        "findings shows no false positives, not that nothing was missed. Two of five gaps are "
        "weak and one page number is wrong in two of five records."
    )),
    ("p", (
        "Threats to validity. The relevance labels are our cluster assignments, not "
        "independent judgements, and cross-cluster pairs that are really related count as "
        "misses. The thresholds set by inspection were set on the papers we evaluate on, so "
        "the results are not held-out. All thirty papers are machine learning papers, and "
        "with thirty queries several differences between methods fall inside the intervals. "
        "The main value of the system is explanation and provenance, not ranking accuracy; "
        "a reader who only wants the most similar papers should use TF-IDF."
    )),

    # ------------------------------------------------------------------
    ("h1", "Conclusion"),

    ("p1", (
        "We have described a pipeline that reads a folder of papers and reports how they "
        "relate, where they disagree and what they omit, with every claim traceable to a "
        "sentence on a page and without a generative language model. Measured against seven "
        "baselines it ranks related papers far above chance and above each of its own "
        "dimensions, but not above full-text TF-IDF; its numeric detector finds planted "
        "contradictions without false positives; and its graph has real but coarse community "
        "structure. Future work is a held-out corpus with hand-labelled real contradictions, "
        "learned weights, richer relation extraction and incremental updates. The "
        "implementation, the corpus and the evaluation scripts are available so the figures "
        "above can be reproduced."
    )),
]

TABLE3 = {
    "caption": "Ranking quality of the proposed score and seven baselines. P@k and AUC use the "
               "global ranking of 435 pairs; MAP and nDCG@10 use 30 per-paper queries. "
               "Random ranking is the mean of 500 trials.",
    "headers": ["Method", "P@10", "P@20", "P@30", "MAP", "nDCG@10", "AUC"],
    "rows": [[r[0].replace(" (proposed)", " (ours)")] + [c.replace("**", "") for c in r[1:7]]
             for r in T.baseline_rows(with_ci=False, bold_best=False)],
    "widths": [0.34, 0.10, 0.10, 0.10, 0.10, 0.13, 0.13],
}

_gate_names = ["No gates", "G1 shared term", "G2 same dataset", "G3 same system",
               "G4 asserts a result", "G5 comparable", "G6 gap of 5% or more",
               "G7 shared dataset/metric", "G8 similarity and confidence"]
TABLE4 = {
    "caption": "Contradiction gates, cumulative, in the order the code applies them. Real: claim "
               "pairs still flagged on the 30-paper corpus (no labels). Labelled: true/false "
               "positive document pairs on the six-paper corpus (two planted).",
    "headers": ["Gate", "Real", "Labelled TP/FP"],
    "rows": [[name, f"{r['findings']:,}", f"{s['TP']}/{s['FP']}"]
             for name, r, s in zip(_gate_names, CON["gates_real"], CON["gates_synth"])],
    "widths": [0.50, 0.22, 0.28],
}
