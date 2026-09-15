"""
Tests for claim analysis.

Every case here is a sentence taken from, or modelled on, the 30-paper arXiv
corpus. Each one produced a false contradiction before the corresponding rule
existed, so these are regression tests rather than illustrations.
"""

from __future__ import annotations

import pytest

from rpra.claims import (
    analyse_claim,
    comparable_measurements,
    conditions_conflict,
    repair_spaced_decimals,
)


def metrics_of(sentence: str):
    return [(m.value, m.metric) for m in analyse_claim(sentence).measurements]


# ---------------------------------------------------------------------------
# Decimal repair
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("82 . 9% top-1 accuracy", "82.9% top-1 accuracy"),
        ("BYOL reaches 74 . 3% accuracy", "BYOL reaches 74.3% accuracy"),
        ("an F1 of 0 . 869", "an F1 of 0.869"),
    ],
)
def test_repairs_decimals_split_by_extraction(raw, expected):
    """
    PDF extraction splits decimal points with spaces. Unrepaired, the parser
    matched only the fractional part, so 82.9% was read as 9% - turning two
    papers that agree into a tenfold disagreement.
    """
    assert repair_spaced_decimals(raw) == expected


def test_decimal_repair_is_applied_during_analysis():
    assert metrics_of("The teacher reaches 82 . 9% top-1 accuracy.") == [(0.829, "top-1")]


# ---------------------------------------------------------------------------
# Levels versus changes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sentence",
    [
        "Swin-T yields +1.2% top-1 accuracy on ImageNet-1K.",
        "a significant improvement of 2% over training from scratch",
        "increases its ImageNet accuracy by 9.2% overall",
        "we improve the score by 3.4% on the benchmark",
        "this reduces the error by 1.5% relative",
    ],
)
def test_changes_are_not_treated_as_levels(sentence):
    """A delta and a level are different quantities; comparing them is noise."""
    assert analyse_claim(sentence).measurements == []


@pytest.mark.parametrize(
    "sentence,expected",
    [
        ("Our model achieves an accuracy of 92.4% on the test set.", 0.924),
        ("ResNet-50 achieves 94.2% accuracy on CIFAR-10.", 0.942),
        ("We obtain an F1 of 0.869.", 0.869),
    ],
)
def test_levels_are_kept(sentence, expected):
    """
    "an accuracy of 92.4%" is a level. Treating the bare word "of" as a delta
    cue removed almost every genuine claim, so it is deliberately not one.
    """
    measurements = analyse_claim(sentence).measurements
    assert measurements
    assert measurements[0].value == expected


def test_a_delta_and_a_level_in_one_sentence_keeps_only_the_level():
    facts = analyse_claim(
        "Adapting CLIP increases its ImageNet accuracy by 9.2% to 85.4% overall."
    )
    assert [m.value for m in facts.measurements] == [0.854]


# ---------------------------------------------------------------------------
# Own results versus quoted comparisons
# ---------------------------------------------------------------------------


def test_quoted_figures_are_excluded():
    """
    "reaches 81.3%, against 88.5% reported elsewhere" quotes a rival number.
    Taking the larger value compared the paper against itself.
    """
    facts = analyse_claim(
        "The sparse attention model reaches an exact match of 81.3% on SQuAD, "
        "against 88.5% reported elsewhere."
    )
    assert [m.value for m in facts.measurements] == [0.813]


def test_compared_to_marks_a_reference_value():
    facts = analyse_claim("Our system scores 91.0% compared to 84.2% for the baseline.")
    assert [m.value for m in facts.measurements] == [0.91]


# ---------------------------------------------------------------------------
# Metric binding
# ---------------------------------------------------------------------------


def test_each_value_is_bound_to_its_own_metric():
    """A sentence reporting two metrics must not have them conflated."""
    assert metrics_of(
        "Our model achieves an exact match of 88.5% on SQuAD and an F1 score of 93.7%."
    ) == [(0.885, "exact-match"), (0.937, "f1")]


def test_top_k_variants_are_distinct_metrics():
    assert metrics_of("SimCLR achieves 85.8% top-5 accuracy.") == [(0.858, "top-5")]
    assert metrics_of("ViT achieves 79.9% top-1 accuracy.") == [(0.799, "top-1")]


def test_error_metrics_get_lower_polarity():
    facts = analyse_claim("reaching 4.9% top-5 validation error on ImageNet")
    assert facts.measurements[0].polarity == "lower"


def test_accuracy_gets_higher_polarity():
    facts = analyse_claim("The model reaches 76.2% accuracy on ImageNet.")
    assert facts.measurements[0].polarity == "higher"


# ---------------------------------------------------------------------------
# Non-claims and extraction blobs
# ---------------------------------------------------------------------------


def test_task_descriptions_are_not_claims():
    facts = analyse_claim(
        "Given a sentence, the task is to choose the most plausible continuation "
        "among four choices, scoring 65.1 on the benchmark."
    )
    assert facts.is_non_claim
    assert not facts.usable()


def test_implementation_notes_are_not_claims():
    facts = analyse_claim(
        "Implementation: Semantic segmentation As here ImageNet is the downstream "
        "task, we report 77.0 for reference."
    )
    assert facts.is_non_claim


def test_run_together_sentences_are_rejected():
    """
    Imperfect extraction glues several sentences into one, producing a "claim"
    with a dozen unrelated figures. Comparing anything against that is noise.
    """
    facts = analyse_claim(
        "Swin-T yields 81.4% and 95.6% and 50.2% and 43.5% and 45.8% and 79.0% "
        "and 94.2% top-1 accuracy across benchmarks."
    )
    assert facts.is_blob
    assert not facts.usable()


# ---------------------------------------------------------------------------
# Condition matching
# ---------------------------------------------------------------------------


def test_top_1_conflicts_with_top_5():
    a = analyse_claim("SimCLR achieves 85.8% top-5 accuracy on ImageNet.")
    b = analyse_claim("ViT achieves 79.9% top-1 accuracy on ImageNet.")
    assert conditions_conflict(a, b)


def test_named_variant_conflicts_with_unqualified_accuracy():
    """An unqualified "accuracy" cannot safely be assumed to mean top-1."""
    a = analyse_claim("The teacher reaches 82.9% top-1 accuracy on ImageNet.")
    b = analyse_claim("CLIP reaches 85.4% accuracy on ImageNet.")
    assert conditions_conflict(a, b)


def test_linear_probe_conflicts_with_fine_tuning():
    a = analyse_claim("BYOL reaches 74.3% accuracy using a linear evaluation protocol.")
    b = analyse_claim("The model reaches 79.9% accuracy when fine-tuned on ImageNet.")
    assert conditions_conflict(a, b)


def test_matching_regimes_do_not_conflict():
    a = analyse_claim("BYOL reaches 74.3% accuracy using a linear evaluation protocol.")
    b = analyse_claim("MoCo reaches 71.1% accuracy using a linear evaluation protocol.")
    assert not conditions_conflict(a, b)


def test_self_supervised_is_not_read_as_supervised():
    assert "self-supervised" in analyse_claim("with self-supervised pre-training").regimes
    assert "supervised" not in analyse_claim("with self-supervised pre-training").regimes
    assert "supervised" in analyse_claim("the supervised baseline achieves 76.3%").regimes


# ---------------------------------------------------------------------------
# End-to-end pairing
# ---------------------------------------------------------------------------


def test_matching_metrics_are_compared():
    a = analyse_claim("Our model achieves an exact match of 88.5% on SQuAD and an F1 of 93.7%.")
    b = analyse_claim("The sparse model reaches an exact match of 81.3% on SQuAD.")
    pair = comparable_measurements(a, b)

    assert pair is not None
    left, right = pair
    assert left.metric == right.metric == "exact-match"
    assert (left.value, right.value) == (0.885, 0.813)


def test_error_and_accuracy_are_never_compared():
    a = analyse_claim("reaching 4.9% top-5 validation error on ImageNet")
    b = analyse_claim("CLIP improves accuracy on ImageNet to 76.2%.")
    assert comparable_measurements(a, b) is None


def test_claims_sharing_no_metric_are_not_compared():
    a = analyse_claim("We achieve 74.8% accuracy on ImageNet.")
    b = analyse_claim("We achieve 45.2% mAP on COCO.")
    assert comparable_measurements(a, b) is None
