"""
A small, self-contained corpus of research papers.

The analyser needs papers to analyse, and a deployed instance starts with an
empty corpus directory - so "Run analysis" has nothing to work on and the
interface reports zero of everything. This module generates six PDFs on demand,
which is what the server seeds itself with on first start.

They are written rather than downloaded for three reasons: real papers are
third-party copyrighted works that should not be committed to this repository,
downloading them on every cold start would be slow and would hammer arXiv, and
generated papers can contain *known* answers. These six share datasets, cite one
another, state research gaps outright, and contain two planted contradictions
(ResNet-50 on CIFAR-10, and BERT on SQuAD), so every stage of the pipeline has
something to find and the result can be checked against what was planted.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

PAPERS: list[dict] = [
    {
        "id": "vision_deep_residual_2021",
        "title": "Revisiting Deep Residual Networks for Small-Scale Image Classification",
        "sections": {
            "Abstract": (
                "We propose a revised training schedule for deep residual networks on "
                "small-scale image classification benchmarks. Our method applies "
                "aggressive data augmentation and cosine learning rate scheduling to "
                "ResNet-50. On CIFAR-10 our approach reaches 94.2% accuracy, "
                "outperforming the standard training recipe by a clear margin. We also "
                "report results on CIFAR-100 and ImageNet."
            ),
            "1. Introduction": (
                "Image classification remains a central benchmark task in computer "
                "vision. This paper investigates whether careful optimisation alone can "
                "close the gap between small and large convolutional networks. We aim to "
                "isolate the contribution of the training schedule from that of the "
                "architecture. Prior work has largely focused on architectural novelty, "
                "and little research has been devoted to the training recipe itself."
            ),
            "2. Related Work": (
                "Residual connections were introduced to ease the optimisation of very "
                "deep networks. Subsequent work explored DenseNet and EfficientNet "
                "variants. Data augmentation has been studied extensively for CIFAR-10 "
                "and ImageNet."
            ),
            "3. Methodology": (
                "We use ResNet-50 as our backbone architecture. The model is trained "
                "using stochastic gradient descent with momentum. Our approach combines "
                "data augmentation, dropout and batch normalization. We employ transfer "
                "learning from an ImageNet-pretrained checkpoint. The proposed method is "
                "optimised with a cosine annealing schedule over 300 epochs."
            ),
            "4. Experiments": (
                "We evaluate on CIFAR-10, CIFAR-100 and ImageNet. All experiments use "
                "the standard train and test splits. We report top-1 accuracy and "
                "macro-F1. Each configuration is run with five random seeds."
            ),
            "5. Results": (
                "ResNet-50 trained with our schedule achieves 94.2% accuracy on "
                "CIFAR-10, compared to 91.8% for the baseline recipe. On CIFAR-100 the "
                "model reaches 76.3% accuracy. Our method outperforms the baseline on "
                "every dataset considered. The top-5 accuracy on ImageNet is 92.1%."
            ),
            "6. Conclusion": (
                "We have shown that training schedule alone accounts for a substantial "
                "fraction of reported gains. A limitation of our study is that it is "
                "restricted to convolutional architectures. Future work should examine "
                "whether these findings transfer to Vision Transformer backbones."
            ),
            "References": (
                "[1] Chen, L., Patel, R. On the Reproducibility of Residual Network "
                "Benchmarks. Journal of Machine Learning Studies, 2022.\n"
                "[2] Kumar, S., Alvarez, M. Attention Mechanisms for Reading "
                "Comprehension at Scale. Proceedings of NLP Conference, 2021.\n"
                "[3] Ivanova, T. Data Augmentation Strategies Revisited. Vision "
                "Journal, 2020."
            ),
        },
    },
    {
        "id": "vision_residual_reproduction_2022",
        "title": "On the Reproducibility of Residual Network Benchmarks",
        "sections": {
            "Abstract": (
                "This paper presents an independent reproduction study of residual "
                "network results on small-scale image classification. We retrain "
                "ResNet-50 under controlled conditions on CIFAR-10 and obtain 87.1% "
                "accuracy, substantially below several published figures. We argue that "
                "reported gains are sensitive to undocumented implementation details."
            ),
            "1. Introduction": (
                "Reproducibility is a persistent concern in empirical machine learning. "
                "We investigate whether published CIFAR-10 results for ResNet-50 can be "
                "reproduced from the descriptions given in the original papers. Our goal "
                "is to quantify the variance attributable to implementation choices."
            ),
            "2. Related Work": (
                "Several studies have examined reproducibility in deep learning. "
                "Reported accuracy on CIFAR-10 and ImageNet varies widely across "
                "independent implementations of the same architecture."
            ),
            "3. Methodology": (
                "We implement ResNet-50 from the published architecture description. "
                "The model is trained using stochastic gradient descent with the "
                "hyperparameters stated in the source papers. We apply data augmentation "
                "and batch normalization as described. No transfer learning is used, "
                "since the original protocol trains from scratch."
            ),
            "4. Experiments": (
                "Experiments are run on CIFAR-10 and CIFAR-100 using the standard "
                "splits. We report accuracy and macro-F1 averaged over ten seeds to "
                "characterise variance."
            ),
            "5. Results": (
                "Our reproduction of ResNet-50 achieves 87.1% accuracy on CIFAR-10, "
                "well below the 94.2% figure reported in the literature. On CIFAR-100 we "
                "obtain 68.4% accuracy. The gap does not close with extended training. "
                "Macro-F1 follows the same pattern at 0.869."
            ),
            "6. Conclusion": (
                "Published CIFAR-10 accuracy figures for ResNet-50 appear to depend on "
                "implementation details that are not reported. This is a limitation of "
                "current publication practice rather than of the architecture. Further "
                "research is needed on standardised evaluation protocols."
            ),
            "References": (
                "[1] Ivanova, T. Data Augmentation Strategies Revisited. Vision "
                "Journal, 2020.\n"
                "[2] Okonkwo, A. Standardised Protocols for Benchmark Evaluation. "
                "Methods in ML, 2021."
            ),
        },
    },
    {
        "id": "nlp_attention_reading_2021",
        "title": "Attention Mechanisms for Reading Comprehension at Scale",
        "sections": {
            "Abstract": (
                "We introduce a modified self-attention formulation for extractive "
                "question answering. Our model builds on BERT and is evaluated on SQuAD "
                "and Natural Questions. We achieve an exact match score of 88.5% on "
                "SQuAD, improving over the published baseline."
            ),
            "1. Introduction": (
                "Question answering has become a standard probe of language "
                "understanding. This work proposes a sparse attention variant that "
                "reduces the quadratic cost of self-attention. We aim to retain accuracy "
                "while improving throughput."
            ),
            "2. Related Work": (
                "The Transformer architecture established self-attention as the dominant "
                "mechanism for sequence modelling. BERT and RoBERTa demonstrated the "
                "value of pre-training on large corpora. Efficiency-oriented variants "
                "remain an open problem."
            ),
            "3. Methodology": (
                "Our approach modifies the self-attention mechanism to attend over a "
                "sparse set of positions. We use BERT as the encoder and apply "
                "fine-tuning on the target task. The model is trained using the Adam "
                "optimiser with a linear warmup schedule."
            ),
            "4. Experiments": (
                "We evaluate on SQuAD, Natural Questions and HotpotQA. We report exact "
                "match and F1 score. Latency is measured on a single GPU."
            ),
            "5. Results": (
                "Our model achieves an exact match of 88.5% on SQuAD and an F1 score of "
                "93.7%. On Natural Questions the F1 score is 79.2%. The sparse attention "
                "variant outperforms the dense baseline while reducing latency by a "
                "third."
            ),
            "6. Conclusion": (
                "Sparse self-attention preserves accuracy on reading comprehension while "
                "improving efficiency. Our method is limited to extractive settings. "
                "Future work should explore generative question answering."
            ),
            "References": (
                "[1] Nakamura, H. Efficient Transformers Under Constrained Compute "
                "Budgets. Transactions on NLP, 2023.\n"
                "[2] Ivanova, T. Data Augmentation Strategies Revisited. Vision "
                "Journal, 2020."
            ),
        },
    },
    {
        "id": "nlp_efficient_transformers_2023",
        "title": "Efficient Transformers Under Constrained Compute Budgets",
        "sections": {
            "Abstract": (
                "This paper studies the accuracy cost of efficiency modifications to the "
                "Transformer. We evaluate sparse attention variants on SQuAD under a "
                "fixed compute budget and observe an exact match of 81.3%, considerably "
                "lower than optimistic published claims."
            ),
            "1. Introduction": (
                "Efficiency claims are frequently made without controlling for total "
                "training compute. We investigate whether reported gains from sparse "
                "attention survive a compute-matched comparison."
            ),
            "2. Related Work": (
                "Sparse and linear attention mechanisms have proliferated. Few studies "
                "have compared them under matched compute, and little attention has been "
                "paid to the confound between architecture and training budget."
            ),
            "3. Methodology": (
                "We implement several sparse attention variants on a common BERT "
                "backbone. All models are trained with an identical compute budget. We "
                "apply fine-tuning on each downstream task using the same schedule."
            ),
            "4. Experiments": (
                "Evaluation covers SQuAD, GLUE and Natural Questions. We report exact "
                "match, F1 score and throughput."
            ),
            "5. Results": (
                "Under a matched compute budget, the sparse attention model reaches an "
                "exact match of 81.3% on SQuAD, against 88.5% reported elsewhere. The F1 "
                "score is 87.4%. On GLUE the average score is 82.6%. Efficiency gains do "
                "not translate into accuracy gains once compute is controlled."
            ),
            "6. Conclusion": (
                "Compute-matched evaluation substantially changes the ranking of "
                "efficient Transformer variants. A drawback of our protocol is its cost. "
                "Future research should establish compute reporting standards."
            ),
            "References": (
                "[1] Kumar, S., Alvarez, M. Attention Mechanisms for Reading "
                "Comprehension at Scale. Proceedings of NLP Conference, 2021.\n"
                "[2] Okonkwo, A. Standardised Protocols for Benchmark Evaluation. "
                "Methods in ML, 2021."
            ),
        },
    },
    {
        "id": "survey_graph_neural_networks_2022",
        "title": "A Survey of Graph Neural Networks for Scientific Knowledge Graphs",
        "sections": {
            "Abstract": (
                "This survey reviews graph neural network methods applied to scientific "
                "knowledge graphs. We present a taxonomy of architectures and summarise "
                "reported results across benchmark datasets. We provide a comparative "
                "study of existing approaches."
            ),
            "1. Introduction": (
                "Knowledge graphs have become central to scientific information "
                "retrieval. This review surveys the literature on graph neural network "
                "methods for knowledge graph embedding and relation extraction."
            ),
            "2. Related Work": (
                "Earlier overviews covered knowledge graph construction broadly. Our "
                "taxonomy focuses specifically on the graph neural network family, "
                "including GCN, GraphSAGE and GAT."
            ),
            "3. Methodology": (
                "We categorise methods along three axes: message passing scheme, "
                "training objective and evaluation protocol. Papers were collected from "
                "arXiv and S2ORC."
            ),
            "4. Experiments": (
                "We tabulate reported accuracy and MRR across DocRED, TACRED and SciERC. "
                "No new experiments are run; figures are taken from the source papers."
            ),
            "5. Results": (
                "Reported MRR on DocRED ranges from 0.52 to 0.71 across surveyed "
                "methods. Evaluation protocols differ substantially, which limits "
                "cross-paper comparison."
            ),
            "6. Conclusion": (
                "Graph neural networks for scientific knowledge graphs remain an active "
                "area. The relationship between knowledge graph embedding quality and "
                "downstream relation extraction accuracy has not been investigated "
                "systematically. This remains an open problem for the community."
            ),
            "References": (
                "[1] Chen, L., Patel, R. On the Reproducibility of Residual Network "
                "Benchmarks. Journal of Machine Learning Studies, 2022.\n"
                "[2] Okonkwo, A. Standardised Protocols for Benchmark Evaluation. "
                "Methods in ML, 2021."
            ),
        },
    },
    {
        "id": "method_contrastive_retrieval_2023",
        "title": "Contrastive Learning for Scientific Document Retrieval",
        "sections": {
            "Abstract": (
                "We propose a contrastive learning framework for retrieving related "
                "scientific documents. Our approach fine-tunes a Transformer encoder "
                "with a bespoke negative sampling strategy and is evaluated on S2ORC and "
                "SciERC."
            ),
            "1. Introduction": (
                "Finding related work is a bottleneck in the research process. We "
                "introduce a retrieval model trained with contrastive learning over "
                "citation relationships. Our objective is to improve recall of "
                "conceptually related papers that share no vocabulary."
            ),
            "2. Related Work": (
                "Dense retrieval has largely displaced lexical methods. Contrastive "
                "learning has been applied to sentence embedding, but few studies have "
                "applied it to scientific document retrieval at the corpus level."
            ),
            "3. Methodology": (
                "Our framework uses a Transformer encoder trained with a contrastive "
                "objective. We construct positive pairs from citation links and mine "
                "hard negatives from the same research area. The model is fine-tuned for "
                "ten epochs."
            ),
            "4. Experiments": (
                "We evaluate on S2ORC and SciERC, reporting NDCG and MRR. We compare "
                "against BM25 and a dense retrieval baseline."
            ),
            "5. Results": (
                "Our model achieves an NDCG of 0.741 on S2ORC, improving over the dense "
                "baseline at 0.682. MRR reaches 0.658. The gain is largest for pairs "
                "with low lexical overlap."
            ),
            "6. Conclusion": (
                "Contrastive learning over citation structure improves scientific "
                "document retrieval. Our method requires a substantial citation graph, "
                "which is a limitation for emerging fields. To the best of our "
                "knowledge, no prior work has combined contradiction detection with "
                "retrieval, and this remains unexplored."
            ),
            "References": (
                "[1] Nakamura, H. Efficient Transformers Under Constrained Compute "
                "Budgets. Transactions on NLP, 2023.\n"
                "[2] Sharma, D. A Survey of Graph Neural Networks for Scientific "
                "Knowledge Graphs. Computing Surveys, 2022."
            ),
        },
    },
]


def build_pdf(paper: dict, out_dir: Path) -> Path:
    """Render one paper dict into a multi-page PDF with real heading styling."""
    doc = fitz.open()
    page = doc.new_page()

    margin = 62
    width = page.rect.width - 2 * margin
    y = margin

    def new_page():
        nonlocal page, y
        page = doc.new_page()
        y = margin

    # Title: larger and bold so ingestion's heading heuristic sees it.
    title_box = fitz.Rect(margin, y, margin + width, y + 90)
    page.insert_textbox(
        title_box, paper["title"], fontname="Helvetica-Bold", fontsize=15, align=1
    )
    y += 96

    for heading, body in paper["sections"].items():
        if y > page.rect.height - 170:
            new_page()

        page.insert_textbox(
            fitz.Rect(margin, y, margin + width, y + 22),
            heading,
            fontname="Helvetica-Bold",
            fontsize=12.5,
        )
        y += 24

        # Estimate the height this body needs, then lay it out.
        needed = 13 * (len(body) / 88 + 2)
        if y + needed > page.rect.height - margin:
            available = page.rect.height - margin - y
            overflow = page.insert_textbox(
                fitz.Rect(margin, y, margin + width, page.rect.height - margin),
                body,
                fontname="Helvetica",
                fontsize=10,
                align=3,
            )
            if overflow < 0:
                new_page()
                page.insert_textbox(
                    fitz.Rect(margin, y, margin + width, page.rect.height - margin),
                    body,
                    fontname="Helvetica",
                    fontsize=10,
                    align=3,
                )
                y += needed
            else:
                y += available
                new_page()
            continue

        page.insert_textbox(
            fitz.Rect(margin, y, margin + width, y + needed + 20),
            body,
            fontname="Helvetica",
            fontsize=10,
            align=3,
        )
        y += needed + 14

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{paper['id']}.pdf"
    doc.save(str(path))
    doc.close()
    return path



def build_corpus(out_dir: str | Path) -> list[Path]:
    """Write the full sample corpus to *out_dir* and return the paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return [build_pdf(paper, out_dir) for paper in PAPERS]


def seed_if_empty(corpus_dir: str | Path) -> list[Path]:
    """
    Generate the corpus only when *corpus_dir* holds no PDFs.

    Returns the paths written, or an empty list if papers were already present -
    so this never overwrites a corpus somebody uploaded.
    """
    corpus_dir = Path(corpus_dir)
    if corpus_dir.exists() and any(corpus_dir.glob("*.pdf")):
        return []
    return build_corpus(corpus_dir)
