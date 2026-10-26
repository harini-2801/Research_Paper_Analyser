"""Chapter 8 of the project report: discussion of strengths and weaknesses."""

from __future__ import annotations

import eval_tables as T

D = T.DATA
R = D["ranking"]
FULL = R["Full weighted score (proposed)"]
TF = R["TF-IDF (full text)"]
RW = D["random_weights"]
PROV = D["provenance"]
CON = D["contradictions"]


def n(x, d=2):
    return f"{x:.{d}f}"


BLOCKS: list = []
add = BLOCKS.append

add(("h1", "Discussion"))

add(("h2", "What the Results Show"))
add(("p",
     "The project does what it set out to do. Give it a folder of PDFs and it returns scores, a "
     "graph, contradictions and gaps, each with a sentence behind it. How good the individual "
     "answers are is a more mixed story. The score picks out related papers well above chance, "
     "yet a plain text baseline does at least as well. The contradiction stage is so strict that "
     "it reports nothing on real papers, and we can only check that against false alarms, not "
     "against misses. The graph does have structure, though a rough one. In this chapter we put "
     "the good and the bad next to each other and say which claims the evidence will carry."))

add(("h2", "Strengths"))
add(("bul", [
    "Traceability survived a test. In the automatic check, every evidence record named a real "
    "document, a section that contains the quoted sentence, and a quotation present in the PDF. "
    "The ten records for the planted contradictions passed every check.",
    "Each score can be explained. We keep the five components of every score, so the ablation "
    "can show which ones matter (methodology most, citations least), and a reader can open any "
    "pair to see how its number was built. A TF-IDF or embedding score gives no such view.",
    "The parts complement each other. The combined score beats every single dimension on AUC, "
    "MAP and nDCG@10, and all of them except bibliographic similarity are clearly better than "
    "chance.",
    f"The gates do real work. With none of them, {CON['gates_real'][0]['findings']:,} pairs of "
    f"claims on the real corpus look like contradictions. With all of them, none do. On the "
    f"labelled corpus the numeric detector finds both planted contradictions and raises no "
    f"false alarm.",
    "Segmentation held up. All thirty papers were split into sections, and the fallback means "
    "a paper can never be lost.",
    "It is light. The analysis needs only rules and two small pretrained encoders, takes about "
    "half a minute on a laptop, and calls no outside service.",
]))

add(("h2", "Weaknesses"))
add(("p", "Each of these comes with the measurement that shows it."))
add(("bul", [
    f"It is not the best ranker. Full-text TF-IDF gets a P@10 of {n(TF['P@10'])} and a MAP of "
    f"{n(TF['MAP'])}; we get {n(FULL['P@10'])} and {n(FULL['MAP'])}. On AUC the two are level "
    f"({n(TF['AUC'])} against {n(FULL['AUC'])}).",
    f"The weights could be better. About {n(100 * RW['share_beating_default_nDCG'], 0)}% of random "
    f"weightings beat ours on nDCG@10, and leaving out the dataset dimension helps, because "
    f"clusters that share ImageNet then stop looking related.",
    "Extraction is the weakest layer. We pulled out 1,037 entities but only about 100 "
    "relations, and our word lists only know machine learning. Everything built on entities "
    "inherits that limit.",
    f"The graph structure is rough. On the full paper network Louvain finds two communities, "
    f"vision and language, with a modularity of only "
    f"{n(D['paper_network']['full_weighted']['modularity'], 2)}. Some bridge concepts are too "
    f"generic to help: \"accuracy\" appears in 28 of the 30 papers.",
    f"The inference model makes things worse. On the labelled corpus it drops precision from "
    f"1.00 to {n(CON['detectors']['synthetic_numeric_nli']['precision'])}, and no threshold we "
    f"tried removes its false alarms.",
    "We cannot score the contradiction result on real papers. Nobody has labelled real "
    "contradictions in this corpus, so zero findings tells us there were no false alarms, not "
    "that nothing was missed. The labelled corpus is too easy to separate the later gates.",
    f"One provenance field is wrong. In {PROV['gaps']['trails'] - PROV['gaps']['page']} of the "
    f"{PROV['gaps']['trails']} gap records the page number is one page early.",
    "Two of the five gaps are weak, and two others repeat the same statement.",
]))

add(("h2", "Weaknesses of the Evaluation Itself"))
add(("bul", [
    "The labels are ours. Two papers count as related when they sit in a cluster we picked, "
    "which is not independent human judgement. Pairs that really are related across clusters, "
    "such as MoCo and ResNet, are scored as mistakes.",
    "We set the thresholds while looking at the same thirty papers that we later evaluated on "
    "({sec:thresholds}). The results are therefore not held-out and may be too good. The "
    "sensitivity analysis shows how much they move, not how they would turn out elsewhere.",
    "Every paper is about machine learning, and our word lists were written for that field.",
    "Thirty papers and thirty queries are not many. The confidence intervals are wide enough "
    "that several differences between methods sit inside them.",
    "The pipeline is deterministic, so there is no variance across runs to report, only "
    "bootstrap intervals over papers and pairs.",
]))

add(("h2", "What We Claim and What We Do Not"))
add(("p", "Putting the two lists together, this is what we are willing to say."))
add(("bul", [
    "The five-dimension score ranks related papers far above chance, its parts complement each "
    "other, and nearly every output can be traced to a source sentence.",
    "The gates remove essentially all spurious numeric disagreements on the real corpus, and the "
    "numeric detector keeps recall on the labelled corpus.",
    "We do not say the score beats simple text similarity. On this corpus it does not.",
    "We do not say the weights or any threshold are the best choice.",
    "We do not say we found a true contradiction between two real papers. None was confirmed.",
    "We say nothing about the optional language-model backend, which we did not evaluate.",
]))
add(("p",
     "In short, the value of this system is in explanation and provenance, not in ranking "
     "accuracy. Someone who just wants the papers most similar to a given one is better served "
     "by TF-IDF. Someone who wants to know why two papers are related, and where to read about "
     "it, is who the system is for."))
