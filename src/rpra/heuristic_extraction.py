"""
Heuristic (LLM-free) entity and relation extraction.

This is the fallback extraction backend.  It exists so the full pipeline -
knowledge graph, relationship scoring, contradiction detection, gap discovery -
can run end to end with no API key, no network, and no GPU.

It is deliberately precision-oriented rather than recall-oriented: a rule fires
only when the surface evidence is strong, because every entity it emits becomes
a node in the knowledge graph and a term in the scoring function.  A wrong
entity is more costly than a missing one.

Three families of rules are used:

gazetteer
    Known dataset, metric and model names matched case-insensitively with word
    boundaries.  Catches the terms that actually drive cross-paper comparison.

cue phrase
    Sentence-level patterns keyed to section type - ``we propose`` in an
    abstract is an objective, ``however, ... fails`` anywhere is a limitation.

numeric claim
    Sentences reporting a metric together with a number.  These are the claims
    that contradiction detection later compares across papers.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from rpra.models import (
    Document,
    Entity,
    EntityType,
    EvidenceTrail,
    Relation,
    RelationType,
    Segment,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gazetteers
# ---------------------------------------------------------------------------

_DATASETS: tuple[str, ...] = (
    "CIFAR-10", "CIFAR-100", "ImageNet", "MNIST", "Fashion-MNIST", "COCO", "MS COCO",
    "Pascal VOC", "SQuAD", "GLUE", "SuperGLUE", "WMT", "IWSLT", "IMDB", "SST-2",
    "Penn Treebank", "WikiText", "MS MARCO", "Natural Questions", "TriviaQA",
    "SNLI", "MultiNLI", "CoNLL-2003", "OntoNotes", "LibriSpeech", "TIMIT",
    "Cityscapes", "ADE20K", "KITTI", "CelebA", "LFW", "UCI", "MovieLens",
    "Amazon Reviews", "Yelp", "Reuters", "20 Newsgroups", "SemEval", "BioASQ",
    "PubMed", "MIMIC-III", "ChestX-ray14", "OpenWebText", "C4", "The Pile",
    "HotpotQA", "DROP", "RACE", "BoolQ", "AG News", "DBpedia", "Flickr30k",
    "Visual Genome", "VQA", "SciERC", "S2ORC", "arXiv", "DocRED", "TACRED",
)

_METRICS: tuple[str, ...] = (
    "accuracy", "precision", "recall", "F1-score", "F1 score", "F1", "macro-F1",
    "micro-F1", "BLEU", "ROUGE", "ROUGE-L", "METEOR", "CIDEr", "perplexity",
    "AUC", "AUROC", "AUPRC", "ROC-AUC", "mAP", "IoU", "mIoU", "NDCG", "MRR",
    "MAE", "RMSE", "MSE", "R-squared", "Dice coefficient", "Jaccard index",
    "word error rate", "WER", "character error rate", "CER", "top-1 accuracy",
    "top-5 accuracy", "exact match", "Cohen's kappa", "Matthews correlation",
    "sensitivity", "specificity", "throughput", "latency", "FLOPs",
)

_MODELS: tuple[str, ...] = (
    "BERT", "RoBERTa", "DistilBERT", "ALBERT", "ELECTRA", "DeBERTa", "SciBERT",
    "BioBERT", "GPT", "GPT-2", "GPT-3", "GPT-4", "T5", "BART", "XLNet", "ERNIE",
    "Transformer", "LSTM", "BiLSTM", "GRU", "RNN", "CNN", "ResNet", "ResNet-50",
    "VGG", "VGG-16", "AlexNet", "DenseNet", "EfficientNet", "MobileNet",
    "Inception", "U-Net", "YOLO", "Faster R-CNN", "Mask R-CNN", "ViT",
    "Vision Transformer", "Swin Transformer", "CLIP", "GAN", "VAE", "Diffusion",
    "GNN", "GCN", "GraphSAGE", "GAT", "Node2Vec", "Word2Vec", "GloVe", "FastText",
    "SVM", "Random Forest", "XGBoost", "LightGBM", "AdaBoost", "Naive Bayes",
    "k-NN", "k-means", "logistic regression", "linear regression",
    "Q-learning", "DQN", "PPO", "Actor-Critic", "LLaMA", "Mistral", "Falcon",
)

_METHODOLOGY_TERMS: tuple[str, ...] = (
    "attention mechanism", "self-attention", "cross-attention", "transfer learning",
    "fine-tuning", "pre-training", "data augmentation", "regularization",
    "dropout", "batch normalization", "layer normalization", "knowledge distillation",
    "contrastive learning", "self-supervised learning", "semi-supervised learning",
    "unsupervised learning", "supervised learning", "reinforcement learning",
    "federated learning", "active learning", "meta-learning", "few-shot learning",
    "zero-shot learning", "multi-task learning", "curriculum learning",
    "ensemble learning", "gradient descent", "stochastic gradient descent",
    "backpropagation", "beam search", "greedy decoding", "cross-validation",
    "hyperparameter tuning", "feature engineering", "feature selection",
    "dimensionality reduction", "clustering", "topic modeling", "named entity recognition",
    "relation extraction", "sentiment analysis", "machine translation",
    "question answering", "text summarization", "image classification",
    "object detection", "semantic segmentation", "speech recognition",
    "retrieval-augmented generation", "prompt engineering", "chain-of-thought",
    "knowledge graph embedding", "graph neural network", "natural language inference",
)


def _gazetteer_regex(terms: Iterable[str]) -> re.Pattern:
    """Build one alternation regex, longest term first so `CIFAR-100` beats `CIFAR-10`."""
    ordered = sorted(set(terms), key=len, reverse=True)
    escaped = "|".join(re.escape(t) for t in ordered)
    return re.compile(rf"(?<![\w-])({escaped})(?![\w-])", re.IGNORECASE)


_DATASET_RE = _gazetteer_regex(_DATASETS)
_METRIC_RE = _gazetteer_regex(_METRICS)
_MODEL_RE = _gazetteer_regex(_MODELS)
_METHOD_TERM_RE = _gazetteer_regex(_METHODOLOGY_TERMS)


# ---------------------------------------------------------------------------
# Cue phrases
# ---------------------------------------------------------------------------

_OBJECTIVE_CUES = re.compile(
    r"\b("
    r"we\s+(?:propose|present|introduce|develop|design|investigate|study|address|explore)"
    r"|this\s+(?:paper|work|study|article)\s+(?:proposes|presents|introduces|investigates|studies|addresses|explores|aims)"
    r"|the\s+(?:goal|aim|objective|purpose)\s+of\s+th\w+\s+(?:paper|work|study)"
    r"|our\s+(?:goal|aim|objective|contribution)\s+is"
    r"|we\s+aim\s+to"
    r")\b",
    re.IGNORECASE,
)

_METHODOLOGY_CUES = re.compile(
    r"\b("
    r"we\s+(?:use|employ|apply|adopt|train|implement|build|construct|leverage|utilise|utilize)"
    r"|our\s+(?:method|approach|model|framework|architecture|system|algorithm|pipeline)"
    r"|the\s+proposed\s+(?:method|approach|model|framework|architecture|system|algorithm)"
    r"|is\s+(?:trained|implemented|optimised|optimized|fine-tuned)\s+(?:using|with|on)"
    r"|consists\s+of|is\s+composed\s+of|we\s+formulate"
    r")\b",
    re.IGNORECASE,
)

_LIMITATION_CUES = re.compile(
    r"\b("
    r"(?:a\s+)?limitation(?:s)?\s+of"
    r"|(?:the\s+)?(?:main\s+|key\s+|major\s+)?drawback"
    r"|fails?\s+to\s+(?:capture|generalise|generalize|account|handle|scale)"
    r"|suffers?\s+from"
    r"|is\s+(?:limited|constrained|restricted)\s+(?:by|to)"
    r"|does\s+not\s+(?:generalise|generalize|scale|account\s+for)"
    r"|(?:is|are)\s+computationally\s+expensive"
    r"|requires?\s+(?:large|substantial|extensive)\s+(?:amounts?\s+of\s+)?(?:labelled|labeled|annotated)\s+data"
    r")\b",
    re.IGNORECASE,
)

_GAP_CUES = re.compile(
    r"\b("
    r"remains?\s+(?:an\s+)?(?:open|unexplored|underexplored|under-explored|unresolved|challenging)"
    r"|(?:has|have)\s+(?:not\s+been|yet\s+to\s+be)\s+(?:explored|investigated|studied|addressed)"
    r"|little\s+(?:attention|work|research)\s+has\s+been"
    r"|few\s+studies\s+have"
    r"|future\s+(?:work|research|studies)\s+(?:should|could|will|may)"
    r"|an?\s+open\s+(?:problem|question|challenge)"
    r"|further\s+research\s+is\s+(?:needed|required)"
    r"|no\s+(?:prior|existing)\s+work\s+has"
    r"|to\s+the\s+best\s+of\s+our\s+knowledge,?\s+(?:no|this\s+is\s+the\s+first)"
    r")\b",
    re.IGNORECASE,
)

_COMPARATIVE_CUES = re.compile(
    r"\b(outperform(?:s|ed|ing)?|surpass(?:es|ed)?|exceed(?:s|ed)?|"
    r"improv(?:es|ed|ement)\s+(?:over|upon|on)|better\s+than|superior\s+to|"
    r"achiev(?:es|ed)\s+(?:a\s+)?(?:new\s+)?state[-\s]of[-\s]the[-\s]art)\b",
    re.IGNORECASE,
)

# A number that looks like a reported score: percentages, decimals, or x.y values.
_NUMERIC_RE = re.compile(r"\b\d{1,3}(?:\.\d+)?\s*%|\b0?\.\d{2,4}\b|\b\d{1,3}\.\d{1,2}\b")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])")

# Sections where a given entity type is worth looking for at all.
_SECTION_AFFINITY: dict[EntityType, frozenset[str]] = {
    EntityType.OBJECTIVE: frozenset({"abstract", "introduction", "conclusion"}),
    EntityType.METHODOLOGY: frozenset(
        {"abstract", "methodology", "experiments", "introduction"}
    ),
    EntityType.QUANTITATIVE_RESULT: frozenset(
        {"abstract", "results", "experiments", "conclusion"}
    ),
    EntityType.LIMITATION: frozenset(
        {"conclusion", "results", "introduction", "related_work", "experiments"}
    ),
    EntityType.RESEARCH_GAP: frozenset(
        {"abstract", "introduction", "related_work", "conclusion"}
    ),
}

# Sections produced by the ingestion fallback, where the paper could not be
# split by heading. Their content spans the whole paper, so no entity type can
# be ruled out by position.
_UNSTRUCTURED_SECTIONS = frozenset({"body", "preamble", ""})

_MAX_SPAN_CHARS = 400
_MAX_PER_TYPE_PER_SEGMENT = 12


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def split_sentences(text: str) -> list[str]:
    """
    Split *text* into sentences.

    PDF text is noisy - hyphenated line breaks, stray newlines inside sentences -
    so whitespace is normalised first and abbreviations common in papers are
    protected from splitting.
    """
    cleaned = re.sub(r"-\n\s*", "", text)  # rejoin hyphenated line breaks
    cleaned = re.sub(r"\s*\n\s*", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    # Protect abbreviations that would otherwise trigger a split.
    protected = re.sub(
        r"\b(et al|e\.g|i\.e|cf|vs|Fig|Eq|Sec|Tab|approx|Dr|Prof)\.",
        lambda m: m.group(0).replace(".", "\x00"),
        cleaned,
    )
    parts = _SENTENCE_SPLIT_RE.split(protected)
    return [p.replace("\x00", ".").strip() for p in parts if p.strip()]


def _normalise_surface(term: str) -> str:
    """Canonical display form for a gazetteer hit."""
    return re.sub(r"\s+", " ", term).strip()


def _truncate(sentence: str) -> str:
    return sentence[:_MAX_SPAN_CHARS].strip()


def _is_plausible_sentence(sentence: str) -> bool:
    """
    Filter out PDF extraction debris.

    Reference lines, table fragments and page furniture make terrible claims, and
    they are the main source of noise in a naive rule-based extractor.
    """
    if len(sentence) < 25 or len(sentence) > 600:
        return False
    letters = sum(c.isalpha() for c in sentence)
    if letters < len(sentence) * 0.55:
        return False
    # Kept as guard clauses rather than one boolean: each rejects a distinct
    # class of PDF debris and is meant to be readable on its own.
    if sentence.count("(") > 4 or sentence.count(",") > 12:  # noqa: SIM103
        return False
    return True


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


def extract_entities_from_segment(segment: Segment) -> list[Entity]:
    """Extract typed entities from a single segment using the rule set."""
    sentences = split_sentences(segment.text)
    section = segment.section_type
    found: list[Entity] = []
    counts: dict[EntityType, int] = {}

    def add(entity_type: EntityType, text: str, sentence: str) -> None:
        if counts.get(entity_type, 0) >= _MAX_PER_TYPE_PER_SEGMENT:
            return
        affinity = _SECTION_AFFINITY.get(entity_type)
        if (
            affinity is not None
            and section not in affinity
            and section not in _UNSTRUCTURED_SECTIONS
        ):
            return
        counts[entity_type] = counts.get(entity_type, 0) + 1
        found.append(
            Entity(
                doc_id=segment.doc_id,
                entity_type=entity_type,
                text=text,
                section=section,
                page_number=segment.page_start,
                sentence_span=_truncate(sentence),
            )
        )

    for sentence in sentences:
        if not _is_plausible_sentence(sentence):
            continue

        # --- gazetteer types (no section restriction) ----------------------
        for match in _DATASET_RE.finditer(sentence):
            add(EntityType.DATASET, _normalise_surface(match.group(1)), sentence)
        for match in _METRIC_RE.finditer(sentence):
            add(EntityType.EVALUATION_METRIC, _normalise_surface(match.group(1)).lower(), sentence)
        for match in _MODEL_RE.finditer(sentence):
            add(EntityType.MODEL, _normalise_surface(match.group(1)), sentence)
        for match in _METHOD_TERM_RE.finditer(sentence):
            add(EntityType.METHODOLOGY, _normalise_surface(match.group(1)).lower(), sentence)

        # --- cue-phrase types ---------------------------------------------
        if _OBJECTIVE_CUES.search(sentence):
            add(EntityType.OBJECTIVE, _truncate(sentence), sentence)

        if _METHODOLOGY_CUES.search(sentence):
            add(EntityType.METHODOLOGY, _truncate(sentence), sentence)

        if _LIMITATION_CUES.search(sentence):
            add(EntityType.LIMITATION, _truncate(sentence), sentence)

        if _GAP_CUES.search(sentence):
            add(EntityType.RESEARCH_GAP, _truncate(sentence), sentence)

        # --- numeric claims -------------------------------------------------
        # Only a metric mention plus a number counts, so plain years and section
        # numbers do not become results.
        if _NUMERIC_RE.search(sentence) and _METRIC_RE.search(sentence):
            add(EntityType.QUANTITATIVE_RESULT, _truncate(sentence), sentence)

    return found


# ---------------------------------------------------------------------------
# Relation extraction
# ---------------------------------------------------------------------------


def extract_relations_from_segment(
    segment: Segment,
    entities: list[Entity],
    doc_title: str,
) -> list[Relation]:
    """
    Derive relations from entity co-occurrence within the same sentence.

    Co-occurrence is a weak signal on its own, so each rule additionally
    requires the entity types to be ones the relation is actually defined
    between, and confidence is set below 1.0 to reflect that these are inferred
    rather than stated.
    """
    by_sentence: dict[str, list[Entity]] = {}
    for entity in entities:
        by_sentence.setdefault(entity.sentence_span, []).append(entity)

    relations: list[Relation] = []
    seen: set[tuple[str, str, str]] = set()

    def link(src: Entity, tgt: Entity, rel: RelationType, confidence: float, sentence: str) -> None:
        if src.id == tgt.id:
            return
        key = (str(src.id), str(tgt.id), rel.value)
        if key in seen:
            return
        seen.add(key)
        relations.append(
            Relation(
                source_id=str(src.id),
                target_id=str(tgt.id),
                relation_type=rel,
                confidence=confidence,
                is_cross_document=False,
                evidence=EvidenceTrail(
                    source_doc_id=segment.doc_id,
                    source_doc_title=doc_title,
                    section=segment.section_type,
                    page_number=segment.page_start,
                    sentence_span=_truncate(sentence),
                ),
            )
        )

    for sentence, group in by_sentence.items():
        datasets = [e for e in group if e.entity_type == EntityType.DATASET]
        models = [e for e in group if e.entity_type == EntityType.MODEL]
        methods = [e for e in group if e.entity_type == EntityType.METHODOLOGY]
        metrics = [e for e in group if e.entity_type == EntityType.EVALUATION_METRIC]
        results = [e for e in group if e.entity_type == EntityType.QUANTITATIVE_RESULT]
        objectives = [e for e in group if e.entity_type == EntityType.OBJECTIVE]
        gaps = [e for e in group if e.entity_type == EntityType.RESEARCH_GAP]
        limitations = [e for e in group if e.entity_type == EntityType.LIMITATION]

        # A model or method evaluated on a dataset.
        for actor in models + methods:
            for dataset in datasets:
                link(actor, dataset, RelationType.EVALUATES_ON, 0.75, sentence)

        # A method that uses a model.
        for method in methods:
            for model in models:
                link(method, model, RelationType.USES, 0.7, sentence)

        # A result measured by a metric.
        for result in results:
            for metric in metrics:
                link(result, metric, RelationType.USES, 0.65, sentence)

        # Comparative language turns a result into an `outperforms` claim.
        if _COMPARATIVE_CUES.search(sentence):
            for result in results:
                for other in models + methods:
                    link(result, other, RelationType.OUTPERFORMS, 0.6, sentence)

        # An objective addresses a stated gap; a limitation identifies one.
        for objective in objectives:
            for gap in gaps:
                link(objective, gap, RelationType.ADDRESSES, 0.6, sentence)
        for limitation in limitations:
            for actor in models + methods:
                link(limitation, actor, RelationType.IDENTIFIES_GAP_IN, 0.6, sentence)

    return relations


# ---------------------------------------------------------------------------
# Document-level entry point
# ---------------------------------------------------------------------------


def extract_document(doc: Document) -> tuple[list[Entity], list[Relation]]:
    """Run heuristic extraction over every segment of *doc*."""
    entities: list[Entity] = []
    relations: list[Relation] = []

    for segment in doc.segments:
        if segment.section_type == "references":
            continue  # handled by the citation parser instead
        try:
            seg_entities = extract_entities_from_segment(segment)
            seg_relations = extract_relations_from_segment(segment, seg_entities, doc.title)
            entities.extend(seg_entities)
            relations.extend(seg_relations)
        except Exception as exc:
            logger.warning(
                "Heuristic extraction failed in %s / %s: %s",
                doc.id,
                segment.section_type,
                exc,
            )

    return entities, relations
