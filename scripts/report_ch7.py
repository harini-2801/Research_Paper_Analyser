"""Chapter 7 of the project report: results. Every number comes from paper/extended_eval.json."""

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
DATASET = R["Dataset only"]
RES = R["Results/metrics only"]
AB = {a["config"]: a for a in D["ablation"]}
RW = D["random_weights"]
NET = D["paper_network"]
G = D["graph"]
BR = D["bridges"]
CON = D["contradictions"]
DET = CON["detectors"]
PROV = D["provenance"]


def n(x, d=2):
    return f"{x:.{d}f}"


def rng(pair, d=2):
    return f"{pair[0]:.{d}f} to {pair[1]:.{d}f}"


BLOCKS: list = []
add = BLOCKS.append

add(("h1", "Results"))

# ----------------------------------------------------------------------
add(("h2", "Segmentation"))
add(("p",
     "Every one of the thirty papers was segmented from its own headings, so the page-chunk "
     "fallback was never used. Of the 240 sections we expected (eight types in each of thirty "
     "papers), 215 were found. Recall is 215 / 240, which is 90% ({fig:seg}). Introductions and "
     "reference lists were found in all thirty. The weakest type was results, at 21 of 30. That is "
     "understandable. Many papers fold results into a section called Experiments, or spread them "
     "over subsections named Ablations or Comparison, which our patterns assign to other types. "
     "Methodology reached 23 of 30 for a similar reason, since authors call it Approach, Model, "
     "Architecture or Our Method."))
add(("fig", {"key": "seg", "file": "segmentation_recovery.png", "width_cm": 11.8,
             "caption": "Section recovery. Number of papers in which each expected section type was found."}))
add(("p",
     "{fig:docs} is the interface's document table, which lets you check recovery one paper at a "
     "time. A paper with no references, or with none of the expected sections, stands out at "
     "once."))
add(("fig", {"key": "docs", "file": "fig3_documents.png", "width_cm": 14.4,
             "caption": "The documents table. Category, confidence, pages, recovered sections and reference count for each paper."}))

# ----------------------------------------------------------------------
add(("h2", ("Relationship Ranking Against Baselines", "ranking")))
add(("p",
     f"{{tab:baselines}} sets the proposed score beside the seven baselines from Chapter 6. The "
     f"columns P@10, P@20, P@30 and AUC are read off one list of all 435 pairs. MAP and nDCG@10 "
     f"are averages over the 30 papers, each used once as a query (see {{sec:metrics}}). Bold "
     f"marks the best value in a column, and the last column is a 95% bootstrap interval around MAP."))
add(("tab", {
    "key": "baselines",
    "caption": "The proposed score against seven baselines. Of the 435 pairs, 99 are relevant because the two papers share a cluster. The random row averages 500 shuffles.",
    "size": 9,
    "headers": ["Method", "P@10", "P@20", "P@30", "MAP", "nDCG@10", "AUC", "MAP 95% CI"],
    "widths": [2.5, 0.8, 0.8, 0.8, 0.8, 1.25, 0.8, 1.4],
    "rows": T.baseline_rows(with_ci=True, bold_best=True),
}))
add(("p",
     f"Against random ranking the score does well. P@10 is {n(FULL['P@10'])} where chance gives "
     f"{n(RND['P@10'])}, MAP is {n(FULL['MAP'])} against {n(RND['MAP'])}, and AUC is "
     f"{n(FULL['AUC'])} against {n(RND['AUC'])}. It also holds its own against its parts. "
     f"Methodology alone is the strongest of them (AUC {n(METH['AUC'])}), dataset overlap and "
     f"results/metrics come next, and the citation measure comes last with an AUC of "
     f"{n(BIB['AUC'])}, close to a coin flip. Since the combination beats every piece, the five "
     f"dimensions are picking up different things."))
add(("p",
     f"Then the part we would rather not write. A plain TF-IDF comparison of the full texts wins "
     f"every column: P@10 {n(TF['P@10'])}, MAP {n(TF['MAP'])}, nDCG@10 {n(TF['nDCG@10'])} and AUC "
     f"{n(TF['AUC'])}. On AUC the two intervals are identical ({rng(TF['AUC_ci'])} and "
     f"{rng(FULL['AUC_ci'])}), which means 30 papers are too few to tell the methods apart there. "
     f"On MAP TF-IDF is higher, though the ranges still overlap ({rng(TF['MAP_ci'])} against "
     f"{rng(FULL['MAP_ci'])}). SBERT on the abstracts gets every one of its top ten right but "
     f"fades later (P@30 {n(SB['P@30'])} against our {n(FULL['P@30'])}). Its MAP of "
     f"{n(SB['MAP'])} equals ours and its AUC of {n(SB['AUC'])} is lower. So, on this corpus, the "
     f"weighted score does not find related papers better than ordinary text similarity, and we do "
     f"not claim that it does. What it offers is a score that can be taken apart, which is the "
     f"argument of Chapter 8."))
add(("p",
     f"Recall tells the same story. Only 99 pairs are relevant, so the top 30 can hold at most "
     f"30 / 99 = 0.30 of them. R@30 is {n(TF['R@30'])} for TF-IDF, {n(SB['R@30'])} for SBERT, "
     f"{n(FULL['R@30'])} for the proposed score and {n(RND['R@30'])} for random ranking."))

add(("p",
     "Pairs within a cluster averaged 0.463 and pairs across clusters 0.331, a gap of 0.132 "
     "({fig:dist}). Two distributions that are visibly apart show that the score itself carries "
     "signal. They still overlap in the middle, which is right, since some cross-cluster pairs "
     "really are related."))
add(("fig", {"key": "dist", "file": "score_distribution.png", "width_cm": 11.8,
             "caption": "Distribution of composite scores. Within-cluster pairs against across-cluster pairs."}))
add(("fig", {"key": "heat", "file": "fig2_heatmap.png", "width_cm": 8.6,
             "caption": "Composite score for all 435 pairs, ordered by cluster. The darker blocks along the diagonal are pairs inside a cluster; the palest area, lower left, is cluster A against cluster D, which share almost nothing."}))
add(("p",
     "{fig:heat} shows the whole matrix ordered by cluster, and {tab:top} lists the ten strongest "
     "pairs."))
add(("tab", {
    "key": "top",
    "caption": "The ten highest-scoring document pairs.",
    "headers": ["Rank", "Paper A", "Paper B", "Score", "Same cluster"],
    "widths": [0.7, 2.4, 2.4, 0.9, 1.1],
    "rows": [
        ["1", "Masked Autoencoders", "Swin Transformer", "0.635", "Yes"],
        ["2", "ALBERT", "RoBERTa", "0.628", "Yes"],
        ["3", "DistilBERT", "ELECTRA", "0.613", "Yes"],
        ["4", "MoCo", "ResNet", "0.597", "No"],
        ["5", "BYOL", "VGG", "0.594", "No"],
        ["6", "Squeeze-and-Excitation", "Wide ResNet", "0.590", "Yes"],
        ["7", "ResNet", "Wide ResNet", "0.588", "Yes"],
        ["8", "ResNet", "Squeeze-and-Excitation", "0.580", "Yes"],
        ["9", "MoCo", "SimCLR", "0.572", "Yes"],
        ["10", "Dense Passage Retrieval", "Retrieval-Augmented Generation", "0.571", "Yes"],
    ],
}))
add(("h3", "Error analysis"))
add(("p",
     "Both errors in the top ten pair a self-supervised vision paper from cluster C with a "
     "convolutional paper from cluster A: MoCo with ResNet, and BYOL with VGG. Neither is clearly "
     "wrong. MoCo measures its learned features on ImageNet through a ResNet backbone, so the two "
     "papers have a dataset, a model family and a metric in common. We put them in different "
     "clusters because one is about architecture and the other about pretraining. Here the score "
     "found a real relationship that our ground truth counts as a mistake."))

# ----------------------------------------------------------------------
add(("h2", ("Weight Ablation", "ablation")))
add(("p",
     f"{{tab:ablation}} shows what happens when each dimension is removed in turn, with the "
     f"remaining original weights rescaled to sum to one. P@10 is global; nDCG@10 is the "
     f"per-paper mean. The last row gives the mean and standard deviation over {RW['trials']} "
     f"random weightings drawn uniformly from the simplex."))
add(("tab", {
    "key": "ablation",
    "caption": "Weight ablation. Each row removes one dimension and rescales the rest; the last row is random weights.",
    "size": 9,
    "headers": ["Configuration", "Obj.", "Meth.", "Data", "Res.", "Cite", "P@10", "nDCG@10"],
    "widths": [2.5, 0.7, 0.7, 0.7, 0.7, 0.7, 1.3, 1.5],
    "rows": T.ablation_rows(),
}))
add(("p",
     f"Three things stand out. Removing methodology costs the most (nDCG@10 falls from "
     f"{n(AB['Full weighted score']['nDCG@10'], 3)} to {n(AB['Drop methodology']['nDCG@10'], 3)}), "
     f"which agrees with methodology being the strongest single dimension. Removing the citation "
     f"dimension changes almost nothing ({n(AB['Drop citation']['nDCG@10'], 3)}), consistent with "
     f"its weak showing alone. And removing the dataset dimension makes things better, not worse: "
     f"nDCG@10 rises to {n(AB['Drop dataset']['nDCG@10'], 3)} and P@10 to "
     f"{n(AB['Drop dataset']['P@10'])}. Dataset overlap hurts here because clusters A and C share "
     f"ImageNet, so it scores cross-cluster pairs highly."))
add(("p",
     f"Our weights are not optimal. Random weightings reach a mean nDCG@10 of "
     f"{n(RW['nDCG@10_mean'], 3)} with a standard deviation of {n(RW['nDCG@10_sd'], 3)}, and "
     f"{n(100 * RW['share_beating_default_nDCG'], 0)}% of them beat the default weights on that "
     f"measure (the best reaches {n(RW['nDCG@10_max'], 3)}). Equal weights give "
     f"{n(AB['Equal weights']['nDCG@10'], 3)}. The default is better than the average random "
     f"choice and worse than a quarter of them. We kept it because the weights were stated as a "
     f"prior before any evaluation, and tuning them on the same thirty papers would make the "
     f"reported numbers optimistic."))

# ----------------------------------------------------------------------
add(("h2", ("Graph-Level Analysis", "graphs")))
add(("h3", "Structure of the knowledge graph"))
add(("p",
     f"The graph built from the thirty papers has {G['nodes']:,} nodes and {G['edges']:,} edges: "
     f"{G['node_types']['document']} documents, {G['node_types']['entity']:,} entities and "
     f"{G['node_types']['bridge_entity']} bridge entities. Its edges are mostly structural: "
     f"{G['edge_types']['contains']:,} document-entity links, {G['edge_types']['has_bridge_entity']} "
     f"links from documents to bridge concepts, 435 relationship-score edges, and only "
     f"{G['edge_types']['uses'] + G['edge_types']['evaluates-on'] + G['edge_types']['outperforms'] + G['edge_types']['identifies-gap-in']} "
     f"extracted relations (uses, evaluates-on, outperforms, identifies-gap-in) plus "
     f"{G['edge_types']['cites']} citations between papers in the corpus. The undirected graph is "
     f"connected (one component) but sparse: density {n(G['density_undirected'], 4)} and mean degree "
     f"{n(G['mean_degree'], 1)}. Relation extraction is the thinnest part of the graph, a point we "
     f"return to in Chapter 8."))
add(("p",
     f"Community detection on the whole graph (Louvain, fixed seed) finds {G['kg_communities']} "
     f"communities with modularity {n(G['kg_modularity'])}. Judged against the topical clusters, "
     f"the purity of the document and entity nodes is {n(G['kg_purity'])}, but the adjusted Rand "
     f"index is only {n(G['kg_ARI'])}. Both are explained by the same fact: a community is "
     f"mostly one paper and its entities, so it is almost always inside one cluster (high "
     f"purity) while one cluster is split across many communities (low agreement)."))
add(("h3", "Communities in the paper network"))
add(("p",
     f"A more useful view joins the papers directly by their relationship score. On the full "
     f"weighted graph of 435 edges, Louvain finds exactly two communities, of 16 and 14 papers. "
     f"They are clusters A and C together (the two image-based clusters) and clusters B and D "
     f"together (language and retrieval). That is a sensible split, but a coarser one than our four "
     f"clusters, and it is only weakly modular (modularity {n(NET['full_weighted']['modularity'], 3)}), "
     f"because almost every pair of papers has some score. Against the four clusters it reaches an "
     f"adjusted Rand index of {n(NET['full_weighted']['ARI'])} and a normalised mutual information "
     f"of {n(NET['full_weighted']['NMI'])}. The mean score between clusters A and C is "
     f"{n(D['cluster_means']['A-C'], 3)}, almost as high as within cluster A "
     f"({n(D['cluster_means']['A-A'], 3)}), which is why the two merge."))
add(("p",
     "Thresholding the network sharpens the picture ({tab:netthr}). At a threshold of 0.50 the "
     "network keeps 49 of 435 edges, 73.5% of which join papers of the same cluster, and "
     "Louvain's communities are almost entirely pure, except that clusters A and C still mix "
     "(each of two mixed communities has equal numbers from both). The cost is fragmentation: "
     "seven papers are isolated and the network splits into ten components. Raising the "
     "threshold to 0.55 gives a purity of 0.93, but only because most communities are single "
     "papers."))
add(("tab", {
    "key": "netthr",
    "caption": "The paper network at increasing score thresholds, with Louvain communities. Edges are pairs with score at or above the threshold.",
    "size": 9,
    "headers": ["Threshold", "Edges", "Isolated", "Components", "Within-cluster edges", "Communities", "Modularity", "ARI"],
    "widths": [1.0, 0.8, 0.9, 1.4, 1.5, 1.3, 1.1, 0.7],
    "rows": [
        [f"{r['tau']:.2f}", str(r["edges"]), str(r["isolated"]), str(r["components"]),
         T.pct(r["within_cluster_edge_share"]), str(r.get("communities", "–")),
         T.f3(r.get("modularity"), 2), T.f3(r.get("ARI"), 2)]
        for k, r in NET.items() if k.startswith("tau_")
    ],
}))
add(("fig", {"key": "commfig", "file": "graph_communities.png", "width_cm": 12.0,
             "caption": "Paper network at threshold 0.50. Colour is the community found on the full weighted graph; shape is the assigned cluster."}))
add(("h3", "Bridge concepts"))
add(("p",
     f"The {BR['count']} bridge concepts appear in {n(BR['mean_spread'], 1)} papers on average, and "
     f"{n(100 * BR['cross_cluster_share'], 0)}% of them link papers from more than one cluster. The "
     f"most widely shared are generic: "
     + ", ".join(f"\"{c}\" ({k} papers)" for c, k in BR["top_concepts"][:5])
     + ". A concept such as accuracy appears in nearly every paper and says nothing about any "
     "particular pair, which is why the interface hides concepts that span more than four papers "
     "in its shared-concepts view. Papers with the highest total score to all others, the hubs "
     "of the network, are "
     + ", ".join(h[0].replace("_", " ") for h in D["hubs"][:3])
     + ": papers whose entities overlap with the widest range of other papers."))

# ----------------------------------------------------------------------
add(("h2", ("Contradiction Detection", "contradictions")))
add(("h3", "Gate by gate on the real corpus"))
add(("p",
     f"Across {CON['real_candidate_pairs']} candidate document pairs the detector looks at "
     f"{CON['real_claim_pairs']:,} pairs of claim sentences. {{tab:gates}} switches the gates on "
     f"one after another, in the order the code runs them. With no gate at all, "
     f"{CON['gates_real'][0]['findings']:,} pairs count as a disagreement, because two sentences "
     f"only need to contain different numbers. Each gate throws most of the rest away "
     f"({{fig:gates}}): a shared dataset or metric name leaves {CON['gates_real'][1]['findings']:,}, "
     f"a shared dataset leaves {CON['gates_real'][2]['findings']}, and the result-assertion check "
     f"leaves {CON['gates_real'][4]['findings']}. G5 does the real work. It asks whether the two "
     f"numbers measure the same thing (a level or a change, the paper's own result or a quoted "
     f"one, the same metric, variant and regime), and it cuts {CON['gates_real'][4]['findings']} "
     f"to {CON['gates_real'][5]['findings']}. G6 removes the last pair, so the final count is zero."))
gate_names = {
    "No gates": "Any two claims with different numbers",
    "G1": "Dataset or metric term named in both sentences",
    "+ G2": "Same dataset named on both sides",
    "+ G3": "Same system named on both sides",
    "+ G4": "Both assert a result; no cross-reference",
    "+ G5": "Comparable measurements",
    "+ G6": "Relative difference of at least 5%",
    "+ G7": "Papers share a dataset or metric",
    "+ G8 (all gates)": "Methodology similarity ≥ 0.30, confidence ≥ 0.60",
}
rows = []
for real, synth in zip(CON["gates_real"], CON["gates_synth"]):
    rows.append([real["config"], gate_names[real["config"]], f"{real['findings']:,}", str(real["doc_pairs"]),
                 str(synth["findings"]), f"{synth['TP']}/{synth['FP']}", T.f3(synth["precision"], 2),
                 T.f3(synth["recall"], 2), T.f3(synth["F1"], 2)])
add(("tab", {
    "key": "gates",
    "caption": "Contradiction gates in the order the code applies them. Gates are cumulative. The real corpus has no labels; the labelled corpus has two planted contradictions.",
    "size": 8.5,
    "headers": ["Gate", "Condition", "Real: findings", "Real: pairs", "Labelled: findings", "TP/FP", "P", "R", "F1"],
    "widths": [1.0, 2.6, 0.9, 0.7, 0.9, 0.7, 0.6, 0.6, 0.6],
    "rows": rows,
}))
add(("fig", {"key": "gates", "file": "contradiction_gates.png", "width_cm": 11.4,
             "caption": "Claim pairs still flagged after each gate. Cumulative counts on the real corpus."}))
add(("p",
     "These counts replace a figure we quoted earlier in the project, of 1,454 findings falling to "
     "zero. That number came from an earlier version of the code and cannot be reproduced, so we "
     "no longer use it as a result. The measured funnel above is for the final code."))
add(("h3", "Gates on the labelled corpus"))
add(("p",
     f"On the six-paper labelled corpus the unit of scoring is a document pair, and there are two "
     f"planted contradictions. With no gates, {CON['gates_synth'][0]['findings']} claim pairs are "
     f"flagged across {CON['gates_synth'][0]['doc_pairs']} document pairs; both planted pairs are "
     f"found (recall 1.00) but eleven other pairs are flagged too, so precision is "
     f"{n(CON['gates_synth'][0]['precision'])}. The first gate alone brings precision to 1.00. "
     f"After that the table cannot separate the gates: the synthetic papers are too simple for the "
     f"later gates to matter. That is a limit of this corpus. Only the real corpus exercises G2 to "
     f"G5, and it has no labels."))
add(("h3", "Numeric detector and inference model"))
add(("p",
     f"{{tab:detectors}} puts the two detector setups side by side at the default thresholds, "
     f"scored on the labelled corpus. The numeric detector alone finds both planted "
     f"contradictions and reports nothing else, so precision, recall and F1 are all 1.00. Adding "
     f"the inference model leaves recall at 1.00 but confirms "
     f"{DET['synthetic_numeric_nli']['confirmed_findings']} findings spread over "
     f"{DET['synthetic_numeric_nli']['confirmed_pairs']} document pairs, "
     f"{DET['synthetic_numeric_nli']['FP']} of which are wrong. Precision drops to "
     f"{n(DET['synthetic_numeric_nli']['precision'])} and F1 to {n(DET['synthetic_numeric_nli']['F1'])}. "
     f"In our setup the inference model is a net source of false alarms. That is part of why the "
     f"gates exist, and why it is optional and left off in the interface."))
add(("tab", {
    "key": "detectors",
    "caption": "Detector configurations at the default thresholds. Document-pair level. n/a means there is no label to score against.",
    "size": 9,
    "headers": ["Corpus", "Detector", "Findings", "Confirmed pairs", "TP", "FP", "FN", "P", "R", "F1"],
    "widths": [1.3, 1.6, 0.9, 1.0, 0.5, 0.5, 0.5, 0.6, 0.6, 0.6],
    "rows": [
        ["Real (30 papers)", "Numeric only", str(DET["real_numeric"]["findings"]),
         str(DET["real_numeric"]["confirmed_pairs"]), "n/a", "n/a", "n/a", "n/a", "n/a", "n/a"],
        ["Labelled (6 papers)", "Numeric only", str(DET["synthetic_numeric"]["findings"]),
         str(DET["synthetic_numeric"]["confirmed_pairs"]), "2", "0", "0", "1.00", "1.00", "1.00"],
        ["Labelled (6 papers)", "Numeric + inference", str(DET["synthetic_numeric_nli"]["findings"]),
         str(DET["synthetic_numeric_nli"]["confirmed_pairs"]), str(DET["synthetic_numeric_nli"]["TP"]),
         str(DET["synthetic_numeric_nli"]["FP"]), str(DET["synthetic_numeric_nli"]["FN"]),
         n(DET["synthetic_numeric_nli"]["precision"]), "1.00", n(DET["synthetic_numeric_nli"]["F1"])],
    ],
}))
add(("h3", "Sensitivity to the thresholds"))
add(("p",
     "{tab:sensnum} and {tab:sensnli} change the two confirmation thresholds on the labelled "
     "corpus. Rows are the methodology similarity required and columns the confidence required; "
     "each cell gives true and false positives, and the defaults are 0.30 and 0.60. The numeric "
     "detector barely notices. Both planted contradictions are found, with no false positive, for "
     "every similarity from 0.1 to 0.5 and every confidence up to 0.7, and both disappear at 0.8 "
     "because the planted gaps give confidences somewhere between 0.7 and 0.8. With the "
     "inference model it is different. The four false positives at the defaults survive every "
     "confidence threshold up to 0.8, and two are still there at 0.9 when the similarity is 0.5. "
     "A higher similarity threshold does help, cutting them from eight at 0.1 to three at 0.5 "
     "without losing a true positive. On the real corpus the numeric detector reports nothing at "
     "any of these settings."))
add(("tab", {
    "key": "sensnum",
    "caption": "Threshold sensitivity, numeric detector, labelled corpus. Cells show TP/FP.",
    "size": 9,
    "headers": T.sensitivity_headers(),
    "widths": [1.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
    "rows": T.sensitivity_matrix("synthetic_numeric", "tpfp"),
}))
add(("tab", {
    "key": "sensnli",
    "caption": "Threshold sensitivity, numeric detector plus inference model, labelled corpus. Cells show TP/FP.",
    "size": 9,
    "headers": T.sensitivity_headers(),
    "widths": [1.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
    "rows": T.sensitivity_matrix("synthetic_numeric_nli", "tpfp"),
}))
add(("p",
     "The candidate-pair threshold (default 0.35) matters even less ({tab:candsweep}). Moving it "
     "from 0.2 to 0.6 changes the number of candidate pairs on the real corpus only from 434 to "
     "422, because most pairs are selected by sharing a bridge concept in any case, and it changes "
     "neither the findings nor the labelled-corpus scores."))
add(("tab", {
    "key": "candsweep",
    "caption": "Candidate-pair threshold sweep, numeric detector.",
    "size": 9,
    "headers": ["Threshold", "Real: candidates", "Real: findings", "Real: confirmed", "Labelled: candidates", "TP", "FP", "P", "R"],
    "widths": [0.9, 1.1, 1.0, 1.1, 1.2, 0.5, 0.5, 0.6, 0.6],
    "rows": T.candidate_rows(),
}))
add(("p",
     "What we can conclude is modest. On the real corpus the detector reports nothing, and nothing "
     "it reported was wrong, but there are no labelled contradictions there to show that it missed "
     "none, so this is a statement about false positives only. The labelled corpus shows that the "
     "numeric detector keeps recall when the gates are applied. The real corpus is where the "
     "gates earn their keep, and the next step is to label a sample of the 4,867 ungated findings "
     "by hand."))

# ----------------------------------------------------------------------
add(("h2", "Research Gaps"))
add(("p",
     "The pipeline extracted 1,037 entities and found 92 bridge concepts, and gap discovery kept "
     "five gaps from them. {tab:gaplist} lists all five. All are stated gaps or limitations, and "
     "the weak-connection and absent-pairing detectors contributed nothing that survived ranking."))
add(("tab", {
    "key": "gaplist",
    "caption": "The five research gaps reported for the thirty-paper corpus.",
    "size": 10,
    "headers": ["#", "Novelty", "Source", "Kind", "Sentence (abridged)"],
    "widths": [0.4, 0.9, 1.7, 1.0, 3.6],
    "rows": [
        ["1", "0.91", "DocRED, abstract, p. 1", "Stated", "DocRED is challenging for existing methods; document-level relation extraction remains an open problem"],
        ["2", "0.91", "DocRED, introduction, p. 1", "Stated", "Performance of existing methods declines on DocRED; the task remains an open problem"],
        ["3", "0.91", "RAG, abstract, p. 1", "Stated", "Providing provenance for decisions and updating world knowledge remain open research problems"],
        ["4", "0.73", "BYOL, related work, p. 2", "Limitation", "Generative approaches are computationally expensive and may demand unnecessary detail"],
        ["5", "0.73", "CLIP, results, p. 8", "Limitation", "Context-less example-based learning leaves many hypotheses consistent with the data"],
    ],
}))
add(("p",
     "The first three are genuine open problems, in the authors' own words. The last two are less "
     "convincing. They are sentences where a paper describes a weakness of other approaches, which "
     "our limitation cue picks up although the papers do not present them as open problems of the "
     "field. Gaps one and two are also two statements of the same problem in one paper, a duplicate "
     "that the ranking does not yet merge. We do not report a precision figure for gaps: nothing "
     "defines the correct set, and building a reference would take an expert labelling thousands of "
     "candidate combinations. The list is short enough to read in a minute and every entry points to "
     "a sentence."))
add(("fig", {"key": "gap", "file": "fig5_evidence.png", "width_cm": 13.2,
             "caption": "A reported gap with its evidence trail. The finding, novelty score, supporting paper, verbatim sentence, section and page."}))

# ----------------------------------------------------------------------
add(("h2", ("Provenance Check", "provenance")))
add(("p",
     f"A claim that every finding can be traced to its source should be tested. We wrote an "
     f"automatic check, not a manual audit. For each evidence record it asks four things: does the "
     f"document exist, does the quoted sentence appear in the section recorded, does it appear on "
     f"the page recorded, and does it appear in the PDF at all. {{tab:prov}} gives the counts. Every "
     f"document, section and quotation is correct. The page number is wrong in "
     f"{PROV['gaps']['trails'] - PROV['gaps']['page']} of the {PROV['gaps']['trails']} gap records, "
     f"and in both cases the sentence is on the page after the one recorded. All ten evidence records "
     f"of the planted contradictions pass every check. The page error is a real defect: a reader "
     f"following a citation would open the wrong page, though the quotation is one page away. We "
     f"have not yet fixed it."))
add(("tab", {
    "key": "prov",
    "caption": "Automatic provenance check of evidence records. Counts of records that pass each check.",
    "size": 9.5,
    "headers": ["Output", "Records", "Document", "Section", "Page", "Quotation", "All four"],
    "widths": [2.5, 0.8, 0.9, 0.8, 0.7, 0.9, 0.8],
    "rows": [
        ["Research gaps (real corpus)", str(PROV["gaps"]["trails"]), str(PROV["gaps"]["document"]),
         str(PROV["gaps"]["section"]), str(PROV["gaps"]["page"]), str(PROV["gaps"]["quote"]),
         str(PROV["gaps"]["all_four"])],
        ["Planted contradictions (labelled corpus)", str(PROV["planted_contradictions"]["trails"]),
         str(PROV["planted_contradictions"]["document"]), str(PROV["planted_contradictions"]["section"]),
         str(PROV["planted_contradictions"]["page"]), str(PROV["planted_contradictions"]["quote"]),
         str(PROV["planted_contradictions"]["all_four"])],
    ],
}))
add(("p",
     "Relationship scores have no quotation, so they are not covered by this check; their "
     "traceability is the five stored components. A human audit of a sample would be a stronger "
     "test than this automatic one, and we have not done it."))

# ----------------------------------------------------------------------
add(("h2", "Runtime"))
add(("p",
     "On a four-core CPU, with no GPU and no network, analysing the thirty papers takes about 33 "
     "seconds once the embedding model is loaded, roughly half of it embedding. Switching the "
     "inference model on changes that completely: the claim comparison over the real corpus was "
     "still running after fifteen minutes when we stopped it, so the real-corpus runs in this "
     "report leave it off. The fourteen seconds of model loading happen at server start-up and "
     "not in the first request."))
