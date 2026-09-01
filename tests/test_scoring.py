"""Tests for relationship scoring (Requirement 6)."""

import pytest
from rpra.models import Document, Entity, EntityType
from rpra.scoring import (
    compute_relationship_score,
    _jaccard_similarity,
    _cosine_similarity,
)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


def test_jaccard_identical_sets():
    assert _jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint_sets():
    assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0


def test_jaccard_empty_sets():
    assert _jaccard_similarity(set(), set()) == 0.0


def test_cosine_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_orthogonal_vectors():
    assert abs(_cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-6


def test_cosine_empty_vectors():
    assert _cosine_similarity([], [1.0]) == 0.0


# ---------------------------------------------------------------------------
# Relationship score
# ---------------------------------------------------------------------------


def _make_doc(doc_id: str) -> Document:
    return Document(id=doc_id, title=doc_id, file_path=f"/{doc_id}.pdf")


def _make_entity(doc_id: str, etype: EntityType, text: str, embedding: list[float]) -> Entity:
    e = Entity(
        doc_id=doc_id,
        entity_type=etype,
        text=text,
        section="methodology",
        page_number=1,
        sentence_span=f"Sentence about {text}.",
    )
    e.embedding = embedding
    return e


def test_score_same_datasets():
    """Documents sharing a dataset should have dataset_overlap > 0."""
    doc_a = _make_doc("a")
    doc_b = _make_doc("b")
    ents_a = [_make_entity("a", EntityType.DATASET, "SQuAD 2.0", [])]
    ents_b = [_make_entity("b", EntityType.DATASET, "SQuAD 2.0", [])]

    score = compute_relationship_score(doc_a, doc_b, ents_a, ents_b)
    assert score.dataset_overlap == 1.0


def test_score_different_datasets():
    doc_a = _make_doc("a")
    doc_b = _make_doc("b")
    ents_a = [_make_entity("a", EntityType.DATASET, "SQuAD 2.0", [])]
    ents_b = [_make_entity("b", EntityType.DATASET, "GLUE", [])]

    score = compute_relationship_score(doc_a, doc_b, ents_a, ents_b)
    assert score.dataset_overlap == 0.0


def test_composite_score_in_range():
    doc_a = _make_doc("a")
    doc_b = _make_doc("b")
    score = compute_relationship_score(doc_a, doc_b, [], [])
    assert 0.0 <= score.composite_score <= 1.0


def test_custom_weights_applied():
    doc_a = _make_doc("a")
    doc_b = _make_doc("b")
    custom_weights = {
        "objective": 0.5,
        "methodology": 0.2,
        "dataset": 0.1,
        "results_metrics": 0.1,
        "citation": 0.1,
    }
    score = compute_relationship_score(doc_a, doc_b, [], [], weights=custom_weights)
    assert score.weights_used == custom_weights


# ---------------------------------------------------------------------------
# Property: composite score is a convex combination of component scores
# ---------------------------------------------------------------------------


def test_composite_is_weighted_sum():
    """composite_score should equal the manually computed weighted sum."""
    doc_a = _make_doc("a")
    doc_b = _make_doc("b")
    ents_a = [_make_entity("a", EntityType.DATASET, "MNIST", [])]
    ents_b = [_make_entity("b", EntityType.DATASET, "MNIST", [])]

    w = {"objective": 0.25, "methodology": 0.25, "dataset": 0.20, "results_metrics": 0.20, "citation": 0.10}
    score = compute_relationship_score(doc_a, doc_b, ents_a, ents_b, weights=w)

    expected = (
        w["objective"] * score.objective_similarity
        + w["methodology"] * score.methodology_similarity
        + w["dataset"] * score.dataset_overlap
        + w["results_metrics"] * score.results_metrics_similarity
        + w["citation"] * score.citation_overlap
    )
    assert abs(score.composite_score - round(expected, 4)) < 1e-4
