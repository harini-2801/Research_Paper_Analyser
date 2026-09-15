"""
Relationship Scoring (Requirement 6).

Computes a weighted composite relatedness score for every pair of documents
across five signal dimensions: objective, methodology, dataset, results/metrics,
and citation similarity.
"""

from __future__ import annotations

import itertools
import logging
import time
from collections.abc import Callable

import numpy as np

from rpra.models import (
    Document,
    Entity,
    EntityType,
    PipelineStageStatus,
    ProgressEvent,
    RelationshipScore,
)

logger = logging.getLogger(__name__)

_DEFAULT_WEIGHTS = {
    "objective": 0.25,
    "methodology": 0.25,
    "dataset": 0.20,
    "results_metrics": 0.20,
    "citation": 0.10,
}


# ---------------------------------------------------------------------------
# Similarity helpers
# ---------------------------------------------------------------------------


def _clamp(value: float) -> float:
    """Confine a similarity to [0, 1], the range a relatedness score occupies."""
    return min(max(float(value), 0.0), 1.0)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two embedding vectors."""
    if not a or not b:
        return 0.0
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0.0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard similarity between two sets of normalised strings."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _average_embedding(entities: list[Entity]) -> list[float]:
    """Mean embedding vector over a list of entities that have embeddings."""
    vecs = [e.embedding for e in entities if e.embedding]
    if not vecs:
        return []
    arr = np.mean(np.array(vecs, dtype=np.float32), axis=0)
    return arr.tolist()


# ---------------------------------------------------------------------------
# Per-dimension scorers
# ---------------------------------------------------------------------------


def _objective_similarity(entities_a: list[Entity], entities_b: list[Entity]) -> float:
    objs_a = [e for e in entities_a if e.entity_type == EntityType.OBJECTIVE]
    objs_b = [e for e in entities_b if e.entity_type == EntityType.OBJECTIVE]
    vec_a = _average_embedding(objs_a)
    vec_b = _average_embedding(objs_b)
    return _cosine_similarity(vec_a, vec_b)


def _methodology_similarity(entities_a: list[Entity], entities_b: list[Entity]) -> float:
    meth_a = [e for e in entities_a if e.entity_type == EntityType.METHODOLOGY]
    meth_b = [e for e in entities_b if e.entity_type == EntityType.METHODOLOGY]
    vec_a = _average_embedding(meth_a)
    vec_b = _average_embedding(meth_b)
    return _cosine_similarity(vec_a, vec_b)


def _dataset_overlap(entities_a: list[Entity], entities_b: list[Entity]) -> float:
    datasets_a = {e.text.lower().strip() for e in entities_a if e.entity_type == EntityType.DATASET}
    datasets_b = {e.text.lower().strip() for e in entities_b if e.entity_type == EntityType.DATASET}
    return _jaccard_similarity(datasets_a, datasets_b)


def _results_metrics_similarity(
    entities_a: list[Entity], entities_b: list[Entity]
) -> float:
    res_a = [
        e for e in entities_a
        if e.entity_type in (EntityType.QUANTITATIVE_RESULT, EntityType.EVALUATION_METRIC)
    ]
    res_b = [
        e for e in entities_b
        if e.entity_type in (EntityType.QUANTITATIVE_RESULT, EntityType.EVALUATION_METRIC)
    ]
    vec_a = _average_embedding(res_a)
    vec_b = _average_embedding(res_b)
    return _cosine_similarity(vec_a, vec_b)


def _citation_overlap(doc_a: Document, doc_b: Document) -> float:
    """
    Bibliographic coupling: how much of the two papers' reference lists overlap.

    Reads the citation keys written by :mod:`rpra.citations` during ingestion.
    Two papers citing the same prior work are related even when they share no
    vocabulary, which is exactly the signal the other four dimensions miss.

    Direct citation between the two documents is treated as maximal overlap:
    if A cites B, they are related regardless of bibliography similarity.
    """
    if doc_b.id in set(doc_a.metadata.get("cites_doc_ids", [])):
        return 1.0
    if doc_a.id in set(doc_b.metadata.get("cites_doc_ids", [])):
        return 1.0

    cites_a = {c.lower().strip() for c in doc_a.metadata.get("cited_titles", []) if c}
    cites_b = {c.lower().strip() for c in doc_b.metadata.get("cited_titles", []) if c}
    return _jaccard_similarity(cites_a, cites_b)


# ---------------------------------------------------------------------------
# Main scorer
# ---------------------------------------------------------------------------


def compute_relationship_score(
    doc_a: Document,
    doc_b: Document,
    entities_a: list[Entity],
    entities_b: list[Entity],
    weights: dict[str, float] | None = None,
) -> RelationshipScore:
    """Compute the five-dimensional weighted relationship score."""
    w = weights or _DEFAULT_WEIGHTS

    # Cosine similarity ranges over [-1, 1], but a *relatedness* score does not:
    # two papers pointing in opposite directions in vector space are unrelated,
    # not negatively related. Clamping here rather than letting the model reject
    # the value matters, because RelationshipScore requires >= 0 and a rejected
    # score is a silently dropped pair. With the TF-IDF backend, whose random
    # projection produces negatives routinely, that lost 203 of 435 pairs.
    obj_sim = _clamp(_objective_similarity(entities_a, entities_b))
    meth_sim = _clamp(_methodology_similarity(entities_a, entities_b))
    ds_overlap = _clamp(_dataset_overlap(entities_a, entities_b))
    res_sim = _clamp(_results_metrics_similarity(entities_a, entities_b))
    cit_overlap = _clamp(_citation_overlap(doc_a, doc_b))

    composite = (
        w["objective"] * obj_sim
        + w["methodology"] * meth_sim
        + w["dataset"] * ds_overlap
        + w["results_metrics"] * res_sim
        + w["citation"] * cit_overlap
    )
    composite = min(max(composite, 0.0), 1.0)

    return RelationshipScore(
        doc_id_a=doc_a.id,
        doc_id_b=doc_b.id,
        objective_similarity=round(obj_sim, 4),
        methodology_similarity=round(meth_sim, 4),
        dataset_overlap=round(ds_overlap, 4),
        results_metrics_similarity=round(res_sim, 4),
        citation_overlap=round(cit_overlap, 4),
        composite_score=round(composite, 4),
        weights_used=w,
    )


def score_corpus(
    documents: list[Document],
    entities: list[Entity],
    weights: dict[str, float] | None = None,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> list[RelationshipScore]:
    """
    Compute pairwise relationship scores for all document pairs.
    """

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    # Group entities by document
    entity_index: dict[str, list[Entity]] = {}
    for e in entities:
        entity_index.setdefault(e.doc_id, []).append(e)

    scores: list[RelationshipScore] = []
    pairs = list(itertools.combinations(documents, 2))
    total = len(pairs)

    emit(
        ProgressEvent(
            stage="scoring",
            status=PipelineStageStatus.RUNNING,
            message=f"Scoring {total} document pairs",
        )
    )

    for i, (doc_a, doc_b) in enumerate(pairs):
        start = time.perf_counter()
        try:
            ents_a = entity_index.get(doc_a.id, [])
            ents_b = entity_index.get(doc_b.id, [])
            score = compute_relationship_score(doc_a, doc_b, ents_a, ents_b, weights)
            scores.append(score)
        except Exception as exc:
            logger.warning("Scoring failed for (%s, %s): %s", doc_a.id, doc_b.id, exc)

        if (i + 1) % 50 == 0 or (i + 1) == total:
            elapsed = time.perf_counter() - start
            emit(
                ProgressEvent(
                    stage="scoring",
                    status=PipelineStageStatus.RUNNING,
                    message=f"Scored {i + 1}/{total} pairs",
                    details={"completed": i + 1, "total": total},
                    elapsed_seconds=round(elapsed, 3),
                )
            )

    emit(
        ProgressEvent(
            stage="scoring",
            status=PipelineStageStatus.COMPLETE,
            message=f"Relationship scoring complete: {len(scores)} scores computed",
            details={"scores": len(scores)},
        )
    )

    return scores
