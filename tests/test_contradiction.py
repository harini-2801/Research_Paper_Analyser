"""Tests for contradiction detection (Requirement 7)."""

from __future__ import annotations

import pytest

from rpra.contradiction import (
    _mentions,
    _numeric_disagreement,
    detect_contradictions,
    parse_reported_values,
)
from rpra.models import (
    ContradictionStatus,
    Document,
    Entity,
    EntityType,
    RelationshipScore,
)


def claim(doc_id: str, sentence: str, text: str | None = None) -> Entity:
    return Entity(
        doc_id=doc_id,
        entity_type=EntityType.QUANTITATIVE_RESULT,
        text=text or sentence,
        section="results",
        page_number=5,
        sentence_span=sentence,
    )


def named(doc_id: str, etype: EntityType, text: str) -> Entity:
    return Entity(
        doc_id=doc_id,
        entity_type=etype,
        text=text,
        section="experiments",
        page_number=4,
        sentence_span=f"We report {text}.",
    )


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence,expected",
    [
        ("accuracy of 94.2%", [0.942]),
        ("an F1 of 0.869", [0.869]),
        ("reaches 88.5% and 93.7%", [0.885, 0.937]),
    ],
)
def test_parses_reported_values(sentence, expected):
    assert parse_reported_values(sentence) == pytest.approx(expected)


def test_percentages_and_decimals_normalise_to_the_same_scale():
    assert parse_reported_values("92.4%") == parse_reported_values("0.924")


def test_values_outside_the_score_range_are_dropped():
    assert parse_reported_values("published in 2021 across 400 documents") == []


# ---------------------------------------------------------------------------
# Whole-term matching
# ---------------------------------------------------------------------------


def test_mentions_requires_a_whole_term():
    """`CIFAR-10` inside `CIFAR-100` was producing false contradictions."""
    assert _mentions("evaluated on CIFAR-10 today", "cifar-10")
    assert not _mentions("evaluated on CIFAR-100 today", "cifar-10")
    assert _mentions("evaluated on CIFAR-100 today", "cifar-100")


# ---------------------------------------------------------------------------
# Numeric disagreement
# ---------------------------------------------------------------------------


def test_same_dataset_different_values_is_a_disagreement():
    confidence = _numeric_disagreement(
        claim("a", "ResNet-50 reaches 94.2% accuracy on CIFAR-10."),
        claim("b", "Our ResNet-50 reproduction reaches 87.1% accuracy on CIFAR-10."),
        {"cifar-10", "accuracy"},
        {"cifar-10"},
        {"resnet-50"},
    )
    assert confidence is not None
    assert 0.5 < confidence < 1.0


def test_different_datasets_are_not_compared():
    assert _numeric_disagreement(
        claim("a", "ResNet-50 reaches 94.2% accuracy on CIFAR-10."),
        claim("b", "ResNet-50 reaches 68.4% accuracy on CIFAR-100."),
        {"cifar-10", "cifar-100", "accuracy"},
        {"cifar-10", "cifar-100"},
        {"resnet-50"},
    ) is None


def test_close_values_are_not_a_disagreement():
    assert _numeric_disagreement(
        claim("a", "ResNet-50 reaches 94.2% accuracy on CIFAR-10."),
        claim("b", "ResNet-50 reaches 94.0% accuracy on CIFAR-10."),
        {"cifar-10", "accuracy"},
        {"cifar-10"},
        {"resnet-50"},
    ) is None


def test_no_shared_term_means_no_comparison():
    assert _numeric_disagreement(
        claim("a", "We reach 94.2% accuracy on CIFAR-10."),
        claim("b", "We reach 40.1% BLEU on WMT."),
        set(),
        set(),
        set(),
    ) is None


def test_larger_gap_yields_higher_confidence():
    small = _numeric_disagreement(
        claim("a", "ResNet-50 reaches 90.0% accuracy on CIFAR-10."),
        claim("b", "ResNet-50 reaches 80.0% accuracy on CIFAR-10."),
        {"cifar-10", "accuracy"}, {"cifar-10"}, {"resnet-50"},
    )
    large = _numeric_disagreement(
        claim("a", "ResNet-50 reaches 90.0% accuracy on CIFAR-10."),
        claim("b", "ResNet-50 reaches 40.0% accuracy on CIFAR-10."),
        {"cifar-10", "accuracy"}, {"cifar-10"}, {"resnet-50"},
    )
    assert large > small


# ---------------------------------------------------------------------------
# End-to-end detection (NLI disabled; numeric detector only)
# ---------------------------------------------------------------------------


def build_corpus():
    docs = [
        Document(id="a", title="Paper A", file_path="a.pdf"),
        Document(id="b", title="Paper B", file_path="b.pdf"),
    ]
    entities = [
        claim("a", "ResNet-50 reaches 94.2% accuracy on CIFAR-10."),
        named("a", EntityType.DATASET, "CIFAR-10"),
        named("a", EntityType.EVALUATION_METRIC, "accuracy"),
        named("a", EntityType.MODEL, "ResNet-50"),
        claim("b", "Our ResNet-50 reproduction reaches 87.1% accuracy on CIFAR-10."),
        named("b", EntityType.DATASET, "CIFAR-10"),
        named("b", EntityType.EVALUATION_METRIC, "accuracy"),
        named("b", EntityType.MODEL, "ResNet-50"),
    ]
    scores = [
        RelationshipScore(
            doc_id_a="a", doc_id_b="b", composite_score=0.8, methodology_similarity=0.7
        )
    ]
    return docs, entities, scores


def test_detects_and_confirms_a_genuine_contradiction():
    docs, entities, scores = build_corpus()
    found = detect_contradictions(
        docs, entities, scores, {"cifar-10": ["a", "b"]}, use_nli=False
    )
    assert found
    confirmed = [c for c in found if c.status == ContradictionStatus.CONFIRMED]
    assert confirmed
    first = confirmed[0]
    assert first.dataset_compatible
    assert first.metrics_comparable
    assert len(first.evidence) == 2
    assert first.evidence[0].sentence_span
    assert first.evidence[0].source_doc_title == "Paper A"


def test_low_methodology_similarity_leaves_it_unconfirmed():
    """Req 7.4 - methodology similarity is a required condition for confirmation."""
    docs, entities, _ = build_corpus()
    scores = [
        RelationshipScore(
            doc_id_a="a", doc_id_b="b", composite_score=0.8, methodology_similarity=0.05
        )
    ]
    found = detect_contradictions(
        docs, entities, scores, {"cifar-10": ["a", "b"]}, use_nli=False
    )
    assert found
    assert all(c.status == ContradictionStatus.UNCONFIRMED for c in found)


def test_unrelated_documents_are_not_compared():
    docs, entities, _ = build_corpus()
    weak = [
        RelationshipScore(
            doc_id_a="a", doc_id_b="b", composite_score=0.05, methodology_similarity=0.0
        )
    ]
    assert detect_contradictions(docs, entities, weak, {}, use_nli=False) == []


def test_results_are_ordered_by_confidence():
    docs, entities, scores = build_corpus()
    found = detect_contradictions(
        docs, entities, scores, {"cifar-10": ["a", "b"]}, use_nli=False
    )
    confidences = [c.confidence for c in found]
    assert confidences == sorted(confidences, reverse=True)


def test_missing_nli_model_still_returns_numeric_findings():
    """A model that cannot load degrades the stage; it must not empty it."""
    docs, entities, scores = build_corpus()
    found = detect_contradictions(
        docs,
        entities,
        scores,
        {"cifar-10": ["a", "b"]},
        nli_model_name="this-model-does-not-exist/nowhere",
        use_nli=True,
    )
    assert found


def test_narration_is_not_a_claim():
    """
    "In Sec. 4.2, we apply Batch Normalization to the ImageNet network" names a
    dataset and a number but asserts no result. Sentences like this were the
    main source of false positives on real papers.
    """
    assert _numeric_disagreement(
        claim("a", "In Sec. 4.2, we apply Batch Normalization to the ImageNet network at 74.8%."),
        claim("b", "ResNet-50 reaches 77.7% accuracy on ImageNet."),
        {"imagenet", "accuracy"},
        {"imagenet"},
        {"resnet-50"},
    ) is None


def test_shared_dataset_without_a_shared_metric_is_not_comparable():
    """Two papers measuring different things on one dataset are not in conflict."""
    assert _numeric_disagreement(
        claim("a", "ResNet-50 achieves 74.8% accuracy on ImageNet."),
        claim("b", "ResNet-50 achieves 45.2% mAP on ImageNet."),
        {"imagenet"},
        {"imagenet"},
        {"resnet-50"},
    ) is None


def test_claims_naming_different_systems_are_not_compared():
    """Two papers reporting different numbers for different models do not conflict."""
    assert _numeric_disagreement(
        claim("a", "ResNet-50 achieves 95.2% accuracy on ImageNet."),
        claim("b", "MobileNet achieves 76.2% accuracy on ImageNet."),
        {"imagenet", "accuracy"},
        {"imagenet"},
        {"resnet-50", "mobilenet"},
    ) is None


def test_error_rate_is_not_compared_against_accuracy():
    """Inverted scales: 4.9% error and 76.2% accuracy are different quantities."""
    assert _numeric_disagreement(
        claim("a", "ResNet-50 reaches 4.9% top-5 validation error on ImageNet."),
        claim("b", "ResNet-50 achieves 76.2% accuracy on ImageNet."),
        {"imagenet", "accuracy"},
        {"imagenet"},
        {"resnet-50"},
    ) is None
