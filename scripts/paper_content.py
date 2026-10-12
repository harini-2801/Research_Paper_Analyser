"""
The conference paper's text, held apart from the two templates that render it.

The same manuscript is submitted to two venues with incompatible house styles
(AIP Conference Proceedings numbers nothing and centres its headings in capitals;
Springer LNCS numbers everything and puts table captions above the table). Keeping
the prose here, and the formatting in the renderers, means a correction to the text
lands in both files instead of in whichever one was edited last.

Blocks are ``(kind, payload)``. The renderers map *kind* onto whatever paragraph
style the template of the moment happens to call it.
"""

from __future__ import annotations

TITLE = (
    "A Multi-Dimensional Knowledge Graph Framework for Relationship Analysis, "
    "Contradiction Detection and Research Gap Discovery in Scientific Literature"
)

SHORT_TITLE = "A Knowledge Graph Framework for Scientific Literature Analysis"

AUTHORS = [
    {"name": "Harini Sriram", "affil": 1, "email": "a", "orcid": ""},
    {"name": "Anjaneya Sahu", "affil": 2, "email": "b", "orcid": ""},
    {"name": "Khushi Kumari", "affil": 3, "email": "c", "orcid": ""},
]

# All three authors are at the same institution but in different departments,
# so the affiliation cannot be collapsed to one entry; each is numbered.
AFFILIATIONS = [
    "Department of Computer Science and Engineering (Data Science), "
    "Vellore Institute of Technology, Chennai, 600127, India.",
    "Department of Computer Science and Engineering (Core), "
    "Vellore Institute of Technology, Chennai, 600127, India.",
    "Department of Computer Science and Engineering "
    "(Artificial Intelligence and Machine Learning), "
    "Vellore Institute of Technology, Chennai, 600127, India.",
]

EMAILS = [
    ("a", "Corresponding author: harini.sriram2023@vitstudent.ac.in"),
    ("b", "anjaneya.sahu2023@vitstudent.ac.in"),
    ("c", "khushi.kumari2023@vitstudent.ac.in"),
]

KEYWORDS = (
    "Knowledge graphs, Scientific literature mining, Information extraction, "
    "Contradiction detection, Research gap discovery, Document similarity"
)

ABSTRACT = (
    "Reading a new subfield means holding thirty papers in mind at once, and the "
    "things a researcher most needs to know are rarely stated in any one of them: "
    "which papers are really addressing the same question, where two groups report "
    "different numbers for what appears to be the same experiment, and what the "
    "collection as a whole has never examined. We present a pipeline that recovers "
    "these cross-document relationships automatically and, importantly, makes every "
    "answer traceable to the sentence that produced it. Papers are segmented by "
    "relative font size rather than by matching heading text, which survives the "
    "layout variation of real PDFs; typed entities are extracted by rule; and each "
    "pair of documents is scored on five interpretable dimensions whose weights sum "
    "to one, so a score can always be decomposed. Disagreements are found by "
    "comparing reported measurements and by natural language inference, and are "
    "confirmed only when the two papers are methodologically comparable. On a corpus "
    "of thirty arXiv papers arranged in four topical clusters, segmentation succeeded "
    "on all thirty documents and recovered 90% of expected sections; relationship "
    "ranking reached 80% precision@10 against a 23% random baseline. Contradiction "
    "detection returned no false positives on this corpus, though it also returned no "
    "confirmed contradictions, and we examine why. The system requires no language "
    "model API and runs offline."
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
        "Large language models answer all four fluently, but without provenance: a "
        "reviewer cannot check the answer, and a wrong one is indistinguishable in "
        "tone from a right one. We took the opposite approach. Every number here "
        "decomposes into named components, and every contradiction and gap carries the "
        "document, section, page and sentence that produced it. A language model "
        "appears only at the end, to phrase findings already established by other "
        "means."
    )),
    ("p", "Our contributions are as follows."),
    ("bullet", (
        "A segmentation method for research PDFs built on relative font size, with a "
        "guaranteed fallback, which recovered structure from all thirty documents in "
        "our evaluation corpus."
    )),
    ("bullet", (
        "A five-dimensional relationship score with weights constrained to sum to one, "
        "which keeps the composite interpretable and lets any ranking be re-derived "
        "under different assumptions."
    )),
    ("bullet", (
        "A two-detector approach to contradiction detection, combining numeric "
        "comparison of reported measurements with natural language inference, gated by "
        "a methodological comparability test."
    )),
    ("bullet", (
        "An evaluation corpus of thirty arXiv papers deliberately structured into four "
        "clusters so that both true positives and negative controls exist by "
        "construction, released with the system."
    )),

    # ------------------------------------------------------------------
    ("h1", "Related Work"),

    ("h2", "Document representation for scientific text"),
    ("p1", (
        "Sentence-BERT [1] made dense sentence embeddings cheap to compute over a whole "
        "corpus, and SciBERT [2] showed that pretraining on scientific text improves "
        "nearly every downstream task in this domain. SPECTER [3] is closest to our "
        "scoring component, learning document representations with the citation graph "
        "as training signal. All three produce a single vector per document, which is "
        "their strength for retrieval and their weakness here: one number for how "
        "close two papers are cannot say whether they are close on dataset, method or "
        "objective. We keep the dimensions separate for that reason."
    )),

    ("h2", "Information extraction from papers"),
    ("p1", (
        "SciERC [4] annotates abstracts with entities and relations, and DocRED [5] "
        "extends relation extraction to the document level. Both need supervision we "
        "do not have for our entity types, and both assume text someone has already "
        "segmented. That step, which these papers reasonably treat as solved, was the "
        "largest single source of failure in our own system."
    )),

    ("h2", "Claim verification and contradiction"),
    ("p1", (
        "FEVER [6] established claim verification against retrieved evidence and SciFact "
        "[7] adapted it to scientific abstracts, both as supervised tasks with "
        "annotated claim-evidence pairs. Our setting has no labels, but also does not "
        "need a claim verified against the world, only the observation that two papers "
        "cannot both be right. Models trained on MultiNLI [8] transfer reasonably, "
        "which is why DeBERTa [9] appears here, but on sentences dense with figures "
        "they are unreliable and numeric comparison is cheaper and more trustworthy."
    )),

    ("h2", "Citation analysis"),
    ("p1", (
        "Bibliographic coupling [10] and co-citation [11] predate all of the above by "
        "decades and remain useful: two papers citing the same prior work are related "
        "even when they share no vocabulary, which is exactly the signal "
        "embedding similarity misses. We keep it as one of the five dimensions, at a "
        "lower weight."
    )),

    # ------------------------------------------------------------------
    ("h1", "Method"),

    ("p1", (
        "The pipeline runs eleven stages in a fixed order, shown in Figure 1. The ordering is forced by "
        "data dependency rather than chosen: three of the five scoring dimensions are "
        "cosine similarities between entity vectors, so embedding has to complete "
        "before scoring begins. We learned this the hard way. In an early version the "
        "embedding stage silently failed, and because a missing vector yields a "
        "similarity of zero rather than an error, the composite score quietly collapsed "
        "to its dataset-overlap term while continuing to produce plausible-looking "
        "output."
    )),

    ("pipeline", None),

    ("h2", "Recovering document structure"),
    ("p1", (
        "A PDF stores positioned glyphs and nothing about sections. Recovering the "
        "structure turned out to be the hardest part of this work, and it is worth "
        "describing the attempts that failed, since the obvious approaches all do."
    )),
    ("p", (
        "Matching heading text against a list of section names fails because authors "
        "do not agree on the names: Background, Prior Work, Literature Review and "
        "Related Literature all denote the same section. Looking for bold text fails "
        "because headings in many templates are not bold. Looking for short lines fails "
        "badly in two-column layouts, where every line is short. Our first working "
        "version combined these heuristics and produced zero sections on one paper in "
        "the corpus and one hundred and eighty-six on another, from identical code."
    )),
    ("p", (
        "What does work is relative font size. We take the body size for each document "
        "as the character-weighted mode of font sizes on the page, 10.0pt for most of "
        "our corpus, and treat any noticeably larger line, typically 12.0pt, as a "
        "heading candidate. Being relative to the document rather than absolute, the "
        "threshold transfers across house styles. Candidates are matched against "
        "anchored patterns covering the synonym sets, after repairing an extraction "
        "artefact that renders small-capital headings with a space after the first "
        "letter, so I NTRODUCTION reads as INTRODUCTION."
    )),
    ("p", (
        "No document is discarded. If heading detection finds nothing, the paper is "
        "divided into three-page chunks marked as unstructured and continues through "
        "every later stage. The route taken is recorded on the document, so a degraded "
        "result is visible rather than silent."
    )),

    ("h2", "Entity extraction and the missing-section problem"),
    ("p1", (
        "Entities are extracted by rule: gazetteers for datasets, metrics and model "
        "names, cue-phrase patterns for objectives, limitations and stated gaps, and a "
        "metric mention beside a number for a quantitative result. This needs no "
        "training data and no API key, a design requirement rather than a convenience, "
        "since the system must run on manuscripts that cannot be sent to a third party."
    )),
    ("p", (
        "The section a sentence comes from is evidence about what it contains. An "
        "objective is overwhelmingly likely to appear in an abstract, introduction or "
        "conclusion, and we use that: each entity type carries an affinity set of "
        "sections it may be drawn from. This raises an obvious problem for documents "
        "that could not be segmented, where positional evidence does not exist. Our "
        "answer is to suspend the restriction entirely for unstructured segments. The "
        "trade is deliberate and asymmetric. Such a document loses precision, because "
        "its entities are no longer corroborated by position, but it keeps recall and "
        "still contributes objectives, methods and results to the analysis."
    )),
    ("p", (
        "A third case remains, where a paper genuinely contains no methodology: an "
        "editorial, a position piece, an extended abstract. Here there is nothing to "
        "recover and we do not pretend otherwise. The methodology dimension evaluates "
        "to zero and the weights are not renormalised over the surviving dimensions. "
        "Renormalising is tempting and we rejected it, because it would make a paper "
        "matching on a single dimension indistinguishable in score from one matching on "
        "all five. The per-dimension scores accompany every composite, so a reader can "
        "see which evidence actually existed."
    )),

    ("h2", "Five-dimensional relationship scoring"),
    ("p1", (
        "Every pair of documents is scored, giving 435 pairs for a thirty-paper corpus. "
        "Each pair is measured on five dimensions that each return a value in [0, 1], "
        "combined by a weighted sum as shown in Table 1."
    )),
    ("table1", None),
    ("p1", (
        "The three semantic dimensions compare mean entity embeddings by cosine "
        "similarity. The dataset dimension does not: dataset names are exact tokens, so "
        "a set-overlap measure is more appropriate than a distributional one, and we "
        "use the Jaccard index. Citation overlap is bibliographic coupling over parsed "
        "reference lists, with a direct citation between the two documents treated as "
        "maximal."
    )),
    ("p", (
        "The weights are a stated prior, not a learned parameter, and we want to be "
        "explicit about that. They encode three judgements: that what a paper is "
        "trying to do and how it does it jointly make it that paper, hence half the "
        "mass; that datasets and metrics are concrete, checkable common ground, hence "
        "0.40; and that shared citations are genuine but lagging evidence, since a "
        "paper cannot cite work published after it. Two properties keep this from "
        "being arbitrary. The configuration is validated at startup to sum to exactly "
        "1.0, and the system refuses to run otherwise, so the composite stays in "
        "[0, 1] and comparable across runs; and the weights are adjustable at runtime, "
        "so any ranking can be recomputed under a different prior."
    )),
    ("p", (
        "One implementation detail cost us several days and is worth recording. Cosine "
        "similarity ranges over [-1, 1], but relatedness does not; two documents "
        "pointing in opposite directions in vector space are unrelated rather than "
        "negatively related. Before we clamped the value, negative similarities were "
        "rejected by the data model's range constraint, and 203 of 435 pairs were being "
        "dropped from the results without any error being raised. The fix is a single "
        "line. Finding it required counting the output rather than reading the code."
    )),

    ("h2", "Contradiction detection"),
    ("p1", (
        "Two detectors run and their verdicts are merged, because they fail in "
        "different places. The numeric detector parses the values two papers report, "
        "verifies that they measure the same metric on the same dataset under "
        "conditions that do not conflict, and flags a material difference. It uses no "
        "model at all. The inference detector presents two claim sentences to a "
        "cross-encoder as a genuine sentence pair and reads off the stance."
    )),
    ("p", (
        "Flagging is cheap and being right is not, so confirmation requires four "
        "conditions to hold at once: the stance is contradiction, confidence is at "
        "least 0.60, the two papers share a dataset or have comparable metrics, and "
        "their methodology similarity is at least 0.30. Everything else is reported as "
        "unconfirmed rather than suppressed. The methodology condition is what "
        "eliminates the dominant false positive, in which two papers report different "
        "numbers for the straightforward reason that they measured different things."
    )),
    ("p", (
        "Documents, entities and bridge concepts are held in a directed multigraph built "
        "with NetworkX [18]. Candidate pairs are restricted to documents sharing a bridge "
        "concept or score above a relatedness threshold. Unrelated papers cannot "
        "contradict one another, and the restriction keeps this stage from becoming "
        "quadratic in corpus size."
    )),

    ("h2", "Research gap discovery"),
    ("p1", (
        "Three kinds of absence are detected and they are not treated as equally "
        "credible. A stated gap is one an author declares outright, and phrases such as "
        "\"to the best of our knowledge\" or \"remains unexplored\" score above a vague "
        "gesture toward future work. A weak-connection gap arises where several papers "
        "share a specific concept yet score poorly against one another otherwise, "
        "suggesting a subject approached from disconnected directions. An absent "
        "pairing is a combination of two concepts that no paper in the corpus has made."
    )),
    ("p", (
        "Absent pairings are much the weakest evidence, since most pairs of concepts "
        "have never been combined and most never should be. We require both concept "
        "communities to hold at least three papers, not to overlap already, and to be "
        "related to each other: if the papers using X have nothing to do with those "
        "using Y, nobody combining them carries no information. At most one such gap "
        "reaches the final list."
    )),
    ("p", (
        "An early version of this stage returned around sixty gaps. That is not a "
        "findings list but a haystack, and a reader skims it and trusts none of it. "
        "Ranking candidates by importance and returning at most five above a high floor "
        "produced output that a person will actually read, which we regard as the more "
        "useful behaviour even though it lowers recall."
    )),

    # ------------------------------------------------------------------
    ("p", (
        "Findings are presented in a browser interface, shown in Figure 2, which "
        "is how a reader actually works with them: the graph can be explored, a "
        "selected paper dims everything outside its neighbourhood, and every pair "
        "score can be opened to see the five dimensions it was built from."
    )),
    ("workspace", None),

    ("h1", "Evaluation Corpus"),

    ("p1", (
        "A randomly drawn corpus cannot evaluate this system. Contradiction detection "
        "fires only when two papers report the same metric on the same dataset, and a "
        "relationship score can be judged only if the corpus holds both pairs that "
        "ought to rank highly and pairs that ought not. Thirty random papers supply "
        "almost no shared benchmarks and no negative control, against which a scorer "
        "calling every pair related would appear to do well."
    )),
    ("p", (
        "We therefore built the corpus as four deliberate clusters of real arXiv "
        "papers, shown in Table 2. Cluster A is built around residual and convolutional "
        "architectures [14], cluster B around the Transformer [12] and the masked "
        "language models that followed it [13], and cluster D around retrieval and "
        "knowledge-graph work [16, 17]. Cluster membership is the ground truth: same-cluster "
        "papers address the same problem on overlapping benchmarks and should score as "
        "related, while cluster A against cluster D shares virtually nothing and serves "
        "as the negative control. Clusters A and C overlap on dataset but differ on "
        "method, testing whether the score separates \"same benchmark\" from \"same "
        "approach\". These papers cite one another densely and several report differing "
        "values for identical baselines."
    )),
    ("table2", None),

    # ------------------------------------------------------------------
    ("h1", "Results"),

    ("h2", "Segmentation"),
    ("p1", (
        "All thirty documents were segmented using detected headings, with none falling "
        "back to page chunking. Across the eight expected section types, 215 of 240 were "
        "recovered, a recall of 90%; Figure 3 shows the view in which this is inspected per paper. Recovery was perfect for introductions and "
        "reference lists and weakest for results sections at 21 of 30, which is "
        "unsurprising: results are frequently folded into a section headed Experiments, "
        "or distributed across several subsections with names like Ablations and "
        "Comparison that our patterns map elsewhere."
    )),

    ("documents", None),

    ("h2", "Relationship ranking"),
    ("p1", (
        "Of the 435 scored pairs, 99 fall within a cluster and 336 across clusters, so "
        "a system ranking pairs at random would be correct 23% of the time. Table 3 "
        "reports precision at several cut-offs, and Figure 4 shows the full "
        "score matrix ordered by cluster, in which the within-cluster blocks "
        "and the pale cluster A against cluster D region are both visible "
        "directly."
    )),
    ("table3", None),
    ("heatmap", None),
    ("p1", (
        "Mean within-cluster score was 0.463 against 0.331 across clusters, a separation "
        "of 0.132. The separation matters more than the precision figures, because it "
        "indicates that the score is discriminative rather than merely correctly "
        "ordered at the top."
    )),
    ("p", (
        "The two errors in the top ten are instructive rather than embarrassing. Both "
        "pair a self-supervised vision paper from cluster C with a convolutional "
        "architecture paper from cluster A, and both are arguably correct: MoCo [15] "
        "and ResNet [14] genuinely are closely related, since MoCo evaluates its representations "
        "on ImageNet using a ResNet backbone. Our cluster assignment treats them as "
        "different because one studies architecture and the other studies pretraining. "
        "The score is picking up a real relationship that our ground truth, by design, "
        "calls a miss."
    )),

    ("h2", "Contradictions and gaps"),
    ("p1", (
        "On the arXiv corpus the system confirmed no contradictions. It also produced "
        "no false positives. We report both halves of that result because the second is "
        "meaningful only alongside the first, and because an earlier configuration "
        "confirmed 1,454 contradictions on the same corpus, essentially all of them "
        "spurious. The successive gates described in Section 3.4 brought that figure to "
        "79, then to 10, then to zero as each gate was added."
    )),
    ("p", (
        "Whether zero is the right answer we cannot say from this corpus alone. To "
        "check that recall had not simply been destroyed, we constructed a six-paper "
        "synthetic corpus containing two deliberately planted contradictions, each a "
        "pair of papers reporting materially different values for the same metric on "
        "the same dataset. Both are detected and confirmed, and this is asserted by the "
        "automated test suite. The honest reading is that the confirmation rule is "
        "calibrated conservatively, and that real cross-paper numeric disagreement in "
        "this particular literature is usually accompanied by differences in "
        "experimental condition that the detector correctly declines to call a "
        "contradiction."
    )),
    ("p", (
        "Figure 5 shows a gap as reported, with the trail that makes it "
        "checkable."
    )),
    ("evidence", None),
    ("p", (
        "Gap discovery returned five gaps from 1,037 extracted entities and 92 bridge "
        "concepts. The resulting knowledge graph contains 1,159 nodes and 2,047 edges. "
        "We do not report precision for gaps, because no ground truth exists and "
        "constructing one would require an expert to label thousands of candidate "
        "pairings. Reporting an unvalidated number would be worse than reporting none, "
        "so the gaps are presented with their evidence trails for human judgement."
    )),

    ("h2", "Runtime"),
    ("p1", (
        "A full analysis of thirty papers takes about 33 seconds on a four-core CPU "
        "with no GPU and no network, once the embedding model is resident; embedding "
        "is roughly half of that. The inference-based detector raises it sharply, and "
        "its calls had to be batched with a capped batch size: one model call per "
        "claim pair exhausted CPU memory."
    )),

    # ------------------------------------------------------------------
    ("h1", "Limitations"),

    ("p1", (
        "The weights are asserted rather than learned. Learning them needs a labelled "
        "relatedness dataset for this corpus, which does not exist; we regard the "
        "scheme's interpretability as partial compensation, not a full answer."
    )),
    ("p", (
        "Extraction is rule-based and English-only. Gazetteers transfer poorly to "
        "fields whose dataset and metric names we have not enumerated, and a paper in "
        "another language would segment correctly while yielding almost no entities. "
        "Scanned PDFs yield no text; these are reported as ingestion errors rather "
        "than skipped, but no OCR is attempted."
    )),
    ("p", (
        "Pair scoring is quadratic. That is irrelevant at thirty papers and tractable at "
        "a few hundred, but tens of thousands would need approximate "
        "nearest-neighbour retrieval to prune candidates first."
    )),
    ("p", (
        "Finally, the contradiction result is one data point from one corpus in one "
        "field. The gates preserve recall on planted contradictions, but we cannot "
        "say what their recall is on real ones without a labelled set of real ones."
    )),

    # ------------------------------------------------------------------
    ("h1", "Conclusion"),

    ("p1", (
        "We have described a system that reads a folder of papers and reports how they "
        "relate, where they disagree and what they omit, with every claim traceable to "
        "a sentence on a page. Segmentation by relative font size handled all thirty "
        "documents and recovered 90% of expected sections; the five-dimensional score "
        "reached 80% precision@10 against a 23% baseline while remaining decomposable. "
        "Contradiction detection produced no false positives, and also no confirmed "
        "findings on real papers."
    )),
    ("p", (
        "The commitment throughout was that an answer a reader cannot verify is not "
        "worth giving. That ruled out several easier architectures and cost accuracy "
        "in places, which we think is the right trade for a tool used on literature a "
        "researcher will then go and read. The implementation, the corpus and the "
        "evaluation scripts are available so the figures above can be reproduced."
    )),
]

TABLE1 = {
    "caption": "The five scoring dimensions, their weights, and the measure used for each.",
    "headers": ["Dimension", "Wt.", "Measure", "Compares"],
    "rows": [
        ["Objective", "0.25", "Cosine", "Mean embedding of objective statements"],
        ["Methodology", "0.25", "Cosine", "Mean embedding of method entities"],
        ["Dataset", "0.20", "Jaccard", "Sets of dataset names"],
        ["Results and metrics", "0.20", "Cosine", "Reported results and evaluation metrics"],
        ["Citation", "0.10", "Jaccard", "Reference lists (bibliographic coupling)"],
    ],
    "widths": [0.22, 0.10, 0.13, 0.55],
}

TABLE2 = {
    "caption": "The evaluation corpus. Cluster membership is the ground truth for relationship ranking.",
    "headers": ["Cluster", "Theme", "n", "Role in the evaluation"],
    "rows": [
        ["A", "Convolutional image classification", "8",
         "Dense cross-citation; same architectures reported with differing baselines"],
        ["B", "Pretrained language models", "8",
         "Shared GLUE and SQuAD benchmarks"],
        ["C", "Vision transformers and self-supervised vision", "8",
         "Shares ImageNet with A but not method"],
        ["D", "Retrieval, information extraction, knowledge graphs", "6",
         "Negative control against cluster A"],
    ],
    "widths": [0.11, 0.30, 0.07, 0.52],
}

TABLE3 = {
    "caption": "Relationship ranking precision at increasing cut-offs. A random ranking scores 23%.",
    "headers": ["Cut-off", "Correct", "Precision"],
    "rows": [
        ["precision@5", "3 / 5", "60%"],
        ["precision@10", "8 / 10", "80%"],
        ["precision@20", "17 / 20", "85%"],
        ["precision@30", "23 / 30", "77%"],
        ["Random baseline", "—", "23%"],
    ],
    "widths": [0.30, 0.25, 0.25],
}

TABLES = {"table1": TABLE1, "table2": TABLE2, "table3": TABLE3}

FIGURES = {
    "pipeline": {
        "file": "paper/figures/fig1_pipeline.png", "max_in": 5.5,
        "caption": "The eleven pipeline stages. Ordering is forced by data "
                   "dependency: three of the five scoring dimensions are cosine "
                   "similarities over entity vectors, so embedding must precede "
                   "scoring.",
    },
    "workspace": {
        "file": "paper/figures/fig2_workspace.png", "width_in": 5.2,
        "caption": "The analysis workspace. Above, the headline counts, the "
                   "knowledge graph with one paper selected - selection dims "
                   "everything outside its neighbourhood - and the inspector. "
                   "Below, the composite score for every pair of papers, which "
                   "the reader can sort and inspect cell by cell.",
    },
    "documents": {
        "file": "paper/figures/fig3_documents.png", "width_in": 5.2,
        "caption": "The per-document view, where segmentation becomes visible: "
                   "for each paper the assigned category and its confidence, the "
                   "page count, the sections actually recovered, and the number "
                   "of references parsed.",
    },
    "heatmap": {
        "file": "paper/figures/fig2_heatmap.png", "max_in": 3.0,
        "caption": "Composite relationship score for all 435 document pairs, "
                   "ordered by topical cluster. Blocks on the diagonal are "
                   "within-cluster pairs. The pale lower-left region is cluster A "
                   "against cluster D, the negative control. The diagonal itself "
                   "is masked; a document is not scored against itself.",
    },
    "evidence": {
        "file": "paper/figures/fig5_evidence.png", "width_in": 5.2,
        "caption": "A reported gap with its evidence trail: the finding, the "
                   "paper supporting it, the verbatim sentence, and the "
                   "provenance - document, section, page - that makes it "
                   "checkable against the source.",
    },
}


REFERENCES = [
    "Reimers, N., Gurevych, I.: Sentence-BERT: Sentence Embeddings using Siamese "
    "BERT-Networks. In: Proceedings of EMNLP-IJCNLP, pp. 3982–3992 (2019).",

    "Beltagy, I., Lo, K., Cohan, A.: SciBERT: A Pretrained Language Model for "
    "Scientific Text. In: Proceedings of EMNLP-IJCNLP, pp. 3615–3620 (2019).",

    "Cohan, A., Feldman, S., Beltagy, I., Downey, D., Weld, D.S.: SPECTER: "
    "Document-level Representation Learning using Citation-informed Transformers. "
    "In: Proceedings of ACL, pp. 2270–2282 (2020).",

    "Luan, Y., He, L., Ostendorf, M., Hajishirzi, H.: Multi-Task Identification of "
    "Entities, Relations, and Coreference for Scientific Knowledge Graph "
    "Construction. In: Proceedings of EMNLP, pp. 3219–3232 (2018).",

    "Yao, Y., Ye, D., Li, P., Han, X., Lin, Y., Liu, Z., Sun, M.: DocRED: A "
    "Large-Scale Document-Level Relation Extraction Dataset. In: Proceedings of ACL, "
    "pp. 764–777 (2019).",

    "Thorne, J., Vlachos, A., Christodoulopoulos, C., Mittal, A.: FEVER: a "
    "Large-scale Dataset for Fact Extraction and VERification. In: Proceedings of "
    "NAACL-HLT, pp. 809–819 (2018).",

    "Wadden, D., Lin, S., Lo, K., Wang, L.L., van Zuylen, M., Cohan, A., Hajishirzi, "
    "H.: Fact or Fiction: Verifying Scientific Claims. In: Proceedings of EMNLP, "
    "pp. 7534–7550 (2020).",

    "Williams, A., Nangia, N., Bowman, S.: A Broad-Coverage Challenge Corpus for "
    "Sentence Understanding through Inference. In: Proceedings of NAACL-HLT, "
    "pp. 1112–1122 (2018).",

    "He, P., Liu, X., Gao, J., Chen, W.: DeBERTa: Decoding-enhanced BERT with "
    "Disentangled Attention. In: Proceedings of ICLR (2021).",

    "Kessler, M.M.: Bibliographic coupling between scientific papers. American "
    "Documentation 14(1), 10–25 (1963).",

    "Small, H.: Co-citation in the scientific literature: A new measure of the "
    "relationship between two documents. Journal of the American Society for "
    "Information Science 24(4), 265–269 (1973).",

    "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A.N., "
    "Kaiser, Ł., Polosukhin, I.: Attention Is All You Need. In: Advances in Neural "
    "Information Processing Systems 30, pp. 5998–6008 (2017).",

    "Devlin, J., Chang, M.-W., Lee, K., Toutanova, K.: BERT: Pre-training of Deep "
    "Bidirectional Transformers for Language Understanding. In: Proceedings of "
    "NAACL-HLT, pp. 4171–4186 (2019).",

    "He, K., Zhang, X., Ren, S., Sun, J.: Deep Residual Learning for Image "
    "Recognition. In: Proceedings of CVPR, pp. 770–778 (2016).",

    "He, K., Fan, H., Wu, Y., Xie, S., Girshick, R.: Momentum Contrast for "
    "Unsupervised Visual Representation Learning. In: Proceedings of CVPR, "
    "pp. 9729–9738 (2020).",

    "Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., "
    "Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., Kiela, D.: "
    "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. In: Advances "
    "in Neural Information Processing Systems 33, pp. 9459–9474 (2020).",

    "Ji, S., Pan, S., Cambria, E., Marttinen, P., Yu, P.S.: A Survey on Knowledge "
    "Graphs: Representation, Acquisition, and Applications. IEEE Transactions on "
    "Neural Networks and Learning Systems 33(2), 494–514 (2022).",

    "Hagberg, A.A., Schult, D.A., Swart, P.J.: Exploring Network Structure, "
    "Dynamics, and Function using NetworkX. In: Proceedings of the 7th Python in "
    "Science Conference, pp. 11–15 (2008).",
]
