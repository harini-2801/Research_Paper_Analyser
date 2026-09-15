"""Tests for the embedding backend (Requirement 16)."""

from __future__ import annotations

import numpy as np

from rpra.embeddings import (
    EmbeddingBackend,
    embed_entities,
    load_embeddings,
    save_embeddings,
)
from rpra.models import Entity, EntityType

# The transformer backend downloads a model; these tests exercise the
# deterministic fallback, which is what runs on an offline machine anyway.
FALLBACK = {"prefer_transformer": False}

CORPUS = [
    "deep convolutional networks for image classification on CIFAR-10",
    "transformer models for neural machine translation on the WMT benchmark",
    "residual network training schedules and image classification accuracy",
    "attention mechanisms for machine translation and sequence modelling",
]


def make_entity(text: str, etype: EntityType = EntityType.METHODOLOGY, doc="d1") -> Entity:
    return Entity(
        doc_id=doc,
        entity_type=etype,
        text=text,
        section="methodology",
        page_number=1,
        sentence_span=f"We use {text} in our experiments.",
    )


def test_fallback_backend_selected_when_transformer_disabled():
    backend = EmbeddingBackend(**FALLBACK)
    assert backend.kind == "tfidf"
    assert backend.dimension == 256


def test_vectors_are_l2_normalised():
    backend = EmbeddingBackend(**FALLBACK).fit(CORPUS)
    vectors = backend.encode(["image classification", "machine translation"])
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_similar_text_scores_higher_than_dissimilar():
    backend = EmbeddingBackend(**FALLBACK).fit(CORPUS)
    vectors = backend.encode([
        "image classification on CIFAR-10",
        "CIFAR-10 image classification accuracy",
        "neural machine translation WMT",
    ])
    same_topic = float(vectors[0] @ vectors[1])
    different_topic = float(vectors[0] @ vectors[2])
    assert same_topic > different_topic


def test_encoding_is_deterministic_across_instances():
    """A seeded projection means two runs must agree, or scores drift run to run."""
    first = EmbeddingBackend(**FALLBACK).fit(CORPUS).encode(["residual networks"])
    second = EmbeddingBackend(**FALLBACK).fit(CORPUS).encode(["residual networks"])
    assert np.allclose(first, second)


def test_empty_input_returns_empty_matrix():
    backend = EmbeddingBackend(**FALLBACK)
    assert backend.encode([]).shape == (0, 256)


def test_unfitted_backend_still_encodes():
    """Hash fallback keeps the pipeline running if fit() was never reached."""
    backend = EmbeddingBackend(**FALLBACK)
    vectors = backend.encode(["completely unseen terminology"])
    assert vectors.shape == (1, 256)
    assert np.isfinite(vectors).all()


def test_out_of_vocabulary_text_does_not_produce_nan():
    backend = EmbeddingBackend(**FALLBACK).fit(CORPUS)
    vectors = backend.encode(["zzzz qqqq wwww"])
    assert np.isfinite(vectors).all()


def test_embed_entities_populates_every_embedding():
    entities = [
        make_entity("convolutional neural network"),
        make_entity("CIFAR-10", EntityType.DATASET),
        make_entity("accuracy", EntityType.EVALUATION_METRIC),
    ]
    backend = embed_entities(entities, prefer_transformer=False)

    assert backend.kind == "tfidf"
    for entity in entities:
        assert len(entity.embedding) == 256
        assert any(value != 0.0 for value in entity.embedding)


def test_embed_entities_handles_empty_list():
    backend = embed_entities([], prefer_transformer=False)
    assert backend.kind == "tfidf"


def test_embeddings_round_trip_through_npz(tmp_path):
    entities = [make_entity("attention mechanism"), make_entity("beam search")]
    embed_entities(entities, prefer_transformer=False)

    path = save_embeddings(entities, tmp_path / "vectors.npz")
    assert path is not None

    loaded = load_embeddings(path)
    assert len(loaded) == 2
    for entity in entities:
        restored = loaded[str(entity.id)]
        assert np.allclose(restored, entity.embedding, atol=1e-6)


def test_save_embeddings_returns_none_without_vectors(tmp_path):
    assert save_embeddings([make_entity("unencoded")], tmp_path / "none.npz") is None


def test_load_embeddings_missing_file_returns_empty(tmp_path):
    assert load_embeddings(tmp_path / "absent.npz") == {}
