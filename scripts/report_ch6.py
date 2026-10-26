"""Chapters 6-9 of the project report: evaluation, results, testing and deployment, conclusion."""

from __future__ import annotations

BLOCKS: list = []
add = BLOCKS.append

# ======================================================================
# CHAPTER 6 - EXPERIMENTAL SETUP
# ======================================================================
add(("h1", "Experimental Setup and Dataset"))

add(("h2", "Evaluation Goals"))
add(("p",
     "For each stage we wrote down one question it should be able to answer and one way to "
     "measure the answer ({tab:goals}). The questions are modest on purpose. There is no public "
     "benchmark for \"how related are these two machine learning papers\", and no labelled set of "
     "real contradictions between papers. So we built the evaluation around ground truth that "
     "holds by construction, not around a number we could compare with someone else's."))
add(("tab", {
    "key": "goals",
    "caption": "Evaluation questions and the measurement used for each.",
    "headers": ["Stage", "Question", "Measurement"],
    "widths": [1.5, 3.4, 2.5],
    "rows": [
        ["Segmentation", "Does every paper yield its sections?", "Papers segmented from headings; expected sections recovered"],
        ["Scoring", "Do related papers outrank unrelated ones?", "Precision at rank k; mean score within and across clusters"],
        ["Contradictions", "Are confirmed findings real, and are real ones found?", "False positives on real papers; recall on planted ones"],
        ["Gaps", "Is the list short enough to read, and is each item checkable?", "Count returned; evidence present on each"],
        ["System", "Is it fast and stable enough to use?", "Run time; automated test results"],
    ],
}))

add(("h2", "Why a Clustered Corpus"))
add(("p",
     'Picking papers at random would leave us with nothing to test. A contradiction only exists where two papers report the same quantity on the same benchmark, and a ranking only means something if the collection contains pairs that should score high and pairs that should score low. A random set of thirty would share almost no benchmarks and contain no pair we know to be unrelated, and a scorer that called every pair related would get away with it.'))
add(("p",
     'We therefore chose the thirty papers on purpose, in four groups ({tab:corpus}). Group A is convolutional image classification around residual networks ([[he2016]]). Group B is pretrained language models, built on the Transformer ([[vaswani2017]]) and BERT ([[devlin2019]]). Group C is vision transformers and self-supervised vision, including momentum contrast ([[he2020]]). Group D mixes retrieval, information extraction and knowledge graphs, with retrieval-augmented generation ([[lewis2020]]) among them. The group a paper belongs to is the ground truth. Papers in one group tackle the same problem on overlapping benchmarks, so they should rank as related. Groups A and D have almost nothing in common and act as the negative control. A and C both use ImageNet but differ in approach, so they show whether the score can tell a shared benchmark from a shared method.'))
add(("tab", {
    "key": "corpus",
    "caption": "The thirty-paper evaluation corpus.",
    "size": 10,
    "headers": ["Cluster", "Theme", "Papers", "Role in the evaluation"],
    "widths": [0.9, 2.3, 0.8, 3.4],
    "rows": [
        ["A", "Convolutional image classification", "8", "Dense cross-citation; the same architectures reported with differing baselines"],
        ["B", "Pretrained language models", "8", "Shared GLUE and SQuAD benchmarks"],
        ["C", "Vision transformers and self-supervised vision", "8", "Shares ImageNet with A but not the method"],
        ["D", "Retrieval, extraction, knowledge graphs", "6", "Negative control against cluster A"],
    ],
}))
add(("p",
     "{tab:papers} names the papers. They are downloaded from arXiv when needed and are not "
     "stored in the repository, because they belong to their authors and redistributing them "
     "is not ours to do. The download identifies itself to arXiv and pauses between requests, "
     "as arXiv asks of automated clients."))
add(("tab", {
    "key": "papers",
    "caption": "Papers in the evaluation corpus, by cluster.",
    "size": 9.5,
    "headers": ["Cluster", "Papers"],
    "widths": [0.9, 6.6],
    "rows": [
        ["A", "Batch Normalization; DenseNet; EfficientNet; MobileNets; ResNet; Squeeze-and-Excitation Networks; VGG (very deep convolutional networks); Wide Residual Networks"],
        ["B", "ALBERT; Attention Is All You Need; BERT; DistilBERT; ELECTRA; RoBERTa; T5; XLNet"],
        ["C", "BYOL; CLIP; DeiT; Masked Autoencoders; MoCo; SimCLR; Swin Transformer; Vision Transformer (ViT)"],
        ["D", "DocRED; Dense Passage Retrieval; A Survey on Knowledge Graphs; Retrieval-Augmented Generation; SciBERT; SPECTER"],
    ],
}))

add(("h2", "Synthetic Corpus with Planted Contradictions"))
add(("p",
     "Real papers cannot show that the contradiction detector still works after we made it "
     "strict. For that we generate a second corpus of six papers as PDF files with a script. Two "
     "contradictions are planted in it on purpose: papers that give clearly different values "
     "for one metric on one dataset, one for a residual network on CIFAR-10 and one for BERT "
     "on SQuAD. The automated tests require both to be found and confirmed. This is a check on "
     "recall, not a benchmark."))

add(("h2", "Environment and Procedure"))
add(("p",
     "Everything ran on a laptop with a four-core CPU, no GPU, and no network once the models "
     "and papers were cached. The pipeline used the configuration in Appendix 1 with two "
     "settings fixed by the evaluation scripts: rule-based extraction (so no language model "
     "was involved) and, on the thirty real papers, the natural language inference model switched "
     "off. Contradictions on the real corpus therefore come from the numeric detector alone. The "
     "inference model was run separately on the six-paper labelled corpus, where its effect can "
     "be scored, and not on the real corpus, where there are no labels and the run was still going after "
     "fifteen minutes on this CPU when we stopped it. The default weights of {fig:weights} were used throughout, and "
     "no weight was tuned against the evaluation corpus."))
add(("p",
     "The pipeline was run once on the thirty papers, and every number in Chapter 7 is computed "
     "from that run by a script, so each can be regenerated. The ranking figures reproduce the "
     "score matrix used in our conference paper exactly (maximum difference 0.0). Where a "
     "number depends on random choices, such as tie-breaking, bootstrap resampling or random "
     "weights, the script fixes the random seed."))

add(("h2", ("Evaluation Metrics", "metrics")))
add(("p",
     "We use two families of metric: ranking metrics for the relationship score, and "
     "classification metrics for contradiction detection and segmentation. Each is defined here, "
     "together with how zero denominators and ties are handled, so that no number in Chapter 7 "
     "depends on an unstated convention."))
add(("h3", "Ranking metrics"))
add(("p",
     "A pair of papers is relevant when both belong to the same cluster of the evaluation corpus. "
     "That gives 99 relevant pairs out of 435. The scores can be read in two ways, and we use "
     "both. In the global reading, all 435 pairs are ranked by score in one list. In the "
     "per-paper reading, each of the 30 papers acts as a query and ranks the other 29 papers, "
     "and a paper is relevant to the query if it is in the query's cluster."))
add(("bul", [
    "Precision at k, P@k, is the number of relevant pairs among the k highest-scoring pairs, "
    "divided by k. We report P@10, P@20 and P@30 on the global list.",
    "Recall at k, R@k, is the number of relevant pairs among the top k divided by the total number "
    "of relevant pairs, here 99. R@30 therefore cannot exceed 30/99 = 0.30.",
    "Average precision for one query is the mean, over the relevant papers, of the precision at "
    "the rank where each one appears. Mean average precision, MAP, is its mean over the 30 queries.",
    "nDCG@10 is the discounted cumulative gain of the top ten results, "
    "the sum of rel_i / log2(i + 1) for i = 1 to 10, divided by the same sum for the ideal ranking. "
    "Relevance is binary here, so the gain is 1 for a relevant paper and 0 otherwise. It is "
    "averaged over the 30 queries.",
    "AUC is the ROC variant: the probability that a randomly chosen relevant pair scores higher "
    "than a randomly chosen non-relevant pair, with ties counted as one half. It uses the global list.",
]))
add(("p",
     "Tied scores are broken at random and every figure is averaged over repeated random "
     "tie-breaks, so a method with many ties, such as dataset overlap, is neither flattered nor "
     "punished by the order in which pairs happen to be stored. Confidence intervals are "
     "percentile bootstrap intervals at 95%: the 30 queries are resampled 2,000 times for MAP and "
     "nDCG@10, and the pairs are resampled 400 times for P@k and AUC. For the random baseline we "
     "give the mean and the 2.5th to 97.5th percentile over 500 random rankings."))
add(("h3", "Classification metrics"))
add(("p",
     "Precision is TP / (TP + FP): of the findings the system reports, the share that are real. "
     "Recall is TP / (TP + FN): of the real findings, the share the system reports. F1 is "
     "2PR / (P + R). For contradictions the unit is a document pair, and a positive is a planted "
     "contradiction. A confirmed finding on a planted pair is a true positive. A confirmed "
     "finding on any other pair is a false positive. A planted pair with no confirmed finding is "
     "a false negative. For segmentation, recall is the number of expected sections found divided "
     "by the number expected, 215 / 240."))
add(("p",
     "When a denominator is zero we say so and do not substitute a value: precision is reported "
     "as n/a when a configuration produces no findings at all, and F1 is n/a whenever either "
     "precision or recall is. Two limits apply. The real corpus has no labelled contradictions, so "
     "no precision or recall is computed for it; we report counts, and treat every finding as a "
     "candidate until a person has checked it. And the relevance labels for ranking come from "
     "the clusters we assigned when we built the corpus, not from independent human judgements."))

add(("h2", "Baselines"))
add(("p",
     "The proposed score is compared with seven alternatives ({tab:baselines}). Random ranking "
     "orders the pairs at random. TF-IDF (full text) is the cosine similarity of TF-IDF vectors "
     "([[salton1988]]) built from the whole text of each paper, with English stop words removed "
     "and sublinear term frequency. SBERT (abstract) is the cosine similarity of all-MiniLM-L6-v2 "
     "embeddings ([[reimers2019]]) of each paper's abstract. Bibliographic similarity is the "
     "citation component alone ([[kessler1963]]). Methodology only, dataset only and "
     "results/metrics only are the corresponding components of our score taken singly. The last "
     "row is the full weighted score. The two text baselines see the raw text of the papers; "
     "the component baselines see only the entities we extracted from them."))

# ======================================================================
add(("h2", ("Thresholds and Their Justification", "thresholds")))
add(("p",
     'The system has a handful of thresholds, and how each was chosen matters for how far the results can be trusted. {tab:thresholds} lists them. We describe what happened, not what might ideally have happened. We never searched a grid of values against labelled data, because we had none. Some values were fixed at design time from the project requirements. Others came from running the pipeline on the development papers, reading the output and adjusting until it was usable.'))
add(("tab", {
    "key": "thresholds",
    "caption": "Thresholds, their values, and how each was set.",
    "size": 9.5,
    "headers": ["Threshold", "Value", "How it was set"],
    "widths": [2.3, 0.9, 4.6],
    "rows": [
        ["Methodology similarity to confirm a contradiction", "0.30", "Fixed at design time by requirement R7; a deliberately low bar meaning \"not unrelated\". Not tuned."],
        ["Confidence to confirm a contradiction", "0.60", "Fixed at design time. For inference findings it is the model's probability; the numeric detector's confidence was set so that any finding passing the materiality test clears it."],
        ["Numeric materiality", "5%", "Chosen by us as the smallest relative difference we would call a disagreement and not rounding or seed noise. Not swept."],
        ["Numeric confidence floor and saturation", "0.62, 30%", "Set after an early version scored a real 7.5% disagreement at 0.575, below the 0.60 bar. Scaling only."],
        ["Candidate-pair score", "0.35", "Chosen to bound the number of claim pairs compared. Swept; see {tab:candsweep}."],
        ["Weak-connection score (gaps)", "0.20", "Set in the configuration file by inspection of the development corpus."],
        ["Absent-pairing relatedness, minimum support", "0.40, 3 papers", "Set by inspection, to stop the absent-pairing detector from proposing combinations that nobody should try."],
        ["Gap importance floor and cap", "0.60, 5 gaps", "Set by inspection: the first version returned about sixty gaps, and these values bring that to a list a person reads."],
        ["Heading size margin, length limits", "0.4 pt, 90 characters, 10 words", "Set while debugging the papers that produced 0 sections and 186 sections."],
        ["Scoring weights", "0.25, 0.25, 0.20, 0.20, 0.10", "A stated prior ({sec:scoring}). Their influence is measured by the ablation in Chapter 7."],
    ],
}))
add(("p",
     'Two things follow. First, the values set by inspection were set while we were looking at the very papers we later evaluated on, so results there are not held-out and may look better than they are; a fresh corpus is the proper test. Second, because nothing was tuned for a metric, the useful question is how far the results move when a value moves, not whether the value is optimal. Chapter 7 measures that for the confirmation and candidate thresholds.'))

