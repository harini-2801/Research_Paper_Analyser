"""Tests for the LLM-free extraction backend."""

from __future__ import annotations

from rpra.heuristic_extraction import (
    extract_document,
    extract_entities_from_segment,
    extract_relations_from_segment,
    split_sentences,
)
from rpra.models import Document, EntityType, RelationType, Segment


def segment(text: str, section: str = "results", doc_id: str = "d1") -> Segment:
    return Segment(doc_id=doc_id, section_type=section, page_start=3, page_end=3, text=text)


def types_found(entities):
    return {e.entity_type for e in entities}


def texts_of(entities, etype):
    return {e.text.lower() for e in entities if e.entity_type == etype}


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------


def test_splits_on_sentence_boundaries():
    parts = split_sentences("We trained the model. It reached high accuracy. Results follow.")
    assert len(parts) == 3


def test_rejoins_hyphenated_line_breaks():
    """PDF text wraps mid-word; leaving the break in corrupts every downstream match."""
    parts = split_sentences("We use convolu-\ntional networks for classification.")
    assert "convolutional networks" in parts[0]


def test_does_not_split_on_common_abbreviations():
    parts = split_sentences("Prior work by Chen et al. showed gains. We extend it.")
    assert len(parts) == 2
    assert "et al." in parts[0]


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


def test_finds_dataset_metric_and_model_names():
    entities = extract_entities_from_segment(
        segment("Our ResNet-50 model reaches 94.2% accuracy on the CIFAR-10 benchmark dataset.")
    )
    assert "cifar-10" in texts_of(entities, EntityType.DATASET)
    assert "resnet-50" in texts_of(entities, EntityType.MODEL)
    assert "accuracy" in texts_of(entities, EntityType.EVALUATION_METRIC)


def test_cifar_100_does_not_match_as_cifar_10():
    """Longest-first alternation; otherwise every CIFAR-100 result is mislabelled."""
    entities = extract_entities_from_segment(
        segment("The network was evaluated on CIFAR-100 and reached 76.3% accuracy.")
    )
    datasets = texts_of(entities, EntityType.DATASET)
    assert "cifar-100" in datasets
    assert "cifar-10" not in datasets


def test_quantitative_result_requires_both_metric_and_number():
    with_both = extract_entities_from_segment(
        segment("The system achieves 88.5% accuracy on the held-out evaluation split.")
    )
    assert EntityType.QUANTITATIVE_RESULT in types_found(with_both)

    # A bare number with no metric is a section reference or a year, not a result.
    without_metric = extract_entities_from_segment(
        segment("As described in Section 3.2, the architecture has three stages of processing.")
    )
    assert EntityType.QUANTITATIVE_RESULT not in types_found(without_metric)


def test_objective_detected_in_abstract():
    entities = extract_entities_from_segment(
        segment(
            "We propose a revised training schedule for deep residual networks on images.",
            section="abstract",
        )
    )
    assert EntityType.OBJECTIVE in types_found(entities)


def test_objective_not_harvested_from_results_section():
    """Section affinity keeps objectives out of sections that cannot contain them."""
    entities = extract_entities_from_segment(
        segment("We propose a revised training schedule for residual networks.", section="results")
    )
    assert EntityType.OBJECTIVE not in types_found(entities)


def test_limitation_and_gap_cues():
    limitation = extract_entities_from_segment(
        segment(
            "A limitation of our study is that it is restricted to convolutional models.",
            section="conclusion",
        )
    )
    assert EntityType.LIMITATION in types_found(limitation)

    gap = extract_entities_from_segment(
        segment(
            "The interaction between these two factors remains an open problem for the field.",
            section="conclusion",
        )
    )
    assert EntityType.RESEARCH_GAP in types_found(gap)


def test_short_and_noisy_lines_are_rejected():
    entities = extract_entities_from_segment(segment("CIFAR-10."))
    assert entities == []


def test_reference_style_debris_is_rejected():
    noisy = segment(
        "[12] Chen, L., Patel, R., Kumar, S., Alvarez, M., Ivanova, T., Okonkwo, A., "
        "Nakamura, H., Sharma, D., Proc. ICML, vol. 32, pp. 1122-1130, 2021."
    )
    assert extract_entities_from_segment(noisy) == []


# ---------------------------------------------------------------------------
# Relation extraction
# ---------------------------------------------------------------------------


def test_model_evaluated_on_dataset_creates_relation():
    seg = segment("We train ResNet-50 and evaluate it on the CIFAR-10 dataset.")
    entities = extract_entities_from_segment(seg)
    relations = extract_relations_from_segment(seg, entities, "A Paper")
    assert RelationType.EVALUATES_ON in {r.relation_type for r in relations}


def test_comparative_language_creates_outperforms_relation():
    seg = segment(
        "Our ResNet-50 model achieves 94.2% accuracy and outperforms the baseline on CIFAR-10."
    )
    entities = extract_entities_from_segment(seg)
    relations = extract_relations_from_segment(seg, entities, "A Paper")
    assert RelationType.OUTPERFORMS in {r.relation_type for r in relations}


def test_relations_carry_evidence_and_sub_unit_confidence():
    seg = segment("We evaluate ResNet-50 on CIFAR-10 using top-1 accuracy.")
    entities = extract_entities_from_segment(seg)
    relations = extract_relations_from_segment(seg, entities, "A Paper")
    assert relations
    for relation in relations:
        assert relation.evidence.sentence_span
        assert relation.evidence.source_doc_id == "d1"
        assert relation.evidence.page_number == 3
        # Inferred from co-occurrence, so never asserted at full confidence.
        assert 0.0 < relation.confidence < 1.0


def test_no_duplicate_relations_for_the_same_triple():
    seg = segment("We evaluate ResNet-50 on CIFAR-10, training ResNet-50 on CIFAR-10 again.")
    entities = extract_entities_from_segment(seg)
    relations = extract_relations_from_segment(seg, entities, "A Paper")
    keys = [(r.source_id, r.target_id, r.relation_type) for r in relations]
    assert len(keys) == len(set(keys))


# ---------------------------------------------------------------------------
# Document level
# ---------------------------------------------------------------------------


def test_extract_document_skips_references_section():
    doc = Document(
        id="d1",
        title="A Paper",
        file_path="d1.pdf",
        segments=[
            segment("We evaluate ResNet-50 on CIFAR-10 with 94.2% accuracy.", "results"),
            segment("[1] Someone. Accuracy on CIFAR-10 with ResNet-50. Journal, 2021.", "references"),
        ],
    )
    entities, _ = extract_document(doc)
    assert entities
    assert all(e.section != "references" for e in entities)


def test_extract_document_isolates_segment_failures():
    """One unusable segment must not cost the whole document (Req 3.7)."""
    doc = Document(
        id="d1",
        title="A Paper",
        file_path="d1.pdf",
        segments=[
            segment("", "abstract"),
            segment("We evaluate ResNet-50 on CIFAR-10 achieving 94.2% accuracy.", "results"),
        ],
    )
    entities, _ = extract_document(doc)
    assert entities
