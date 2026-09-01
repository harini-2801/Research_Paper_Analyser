"""Tests for document classification (Requirement 2)."""

import pytest
from rpra.models import Document, DocumentCategory, Segment
from rpra.classification import classify_document, classify_corpus


def _make_doc(doc_id: str, abstract_text: str) -> Document:
    doc = Document(id=doc_id, title=doc_id, file_path=f"/{doc_id}.pdf")
    doc.segments.append(
        Segment(
            doc_id=doc_id,
            section_type="abstract",
            page_start=1,
            page_end=1,
            text=abstract_text,
        )
    )
    return doc


# ---------------------------------------------------------------------------
# Classification correctness
# ---------------------------------------------------------------------------


def test_experimental_classification():
    doc = _make_doc(
        "exp_paper",
        "We train BERT on SQuAD 2.0 and evaluate on a test set. "
        "Our model achieves F1-score of 0.91 and accuracy of 89%, "
        "outperforming all baseline models on the benchmark.",
    )
    category, confidence = classify_document(doc)
    assert category == DocumentCategory.EXPERIMENTAL
    assert confidence > 0.0


def test_survey_classification():
    doc = _make_doc(
        "survey_paper",
        "This survey provides a comprehensive taxonomy and review of existing approaches "
        "in knowledge graph construction. We present a systematic review of the literature "
        "and an overview of chronological trends.",
    )
    category, confidence = classify_document(doc)
    assert category == DocumentCategory.SURVEY_REVIEW
    assert confidence > 0.0


def test_methodological_classification():
    doc = _make_doc(
        "method_paper",
        "We propose a novel algorithm based on graph neural network architecture. "
        "We introduce a new framework and prove its convergence. "
        "The algorithm has linear complexity.",
    )
    category, confidence = classify_document(doc)
    assert category == DocumentCategory.METHODOLOGICAL
    assert confidence > 0.0


def test_empty_document_defaults_to_experimental():
    """A document with no text should still get a category without crashing."""
    doc = Document(id="empty", title="empty", file_path="/empty.pdf")
    category, confidence = classify_document(doc)
    assert category == DocumentCategory.EXPERIMENTAL
    assert confidence == 0.0


# ---------------------------------------------------------------------------
# Low-confidence default (Req 2.4)
# ---------------------------------------------------------------------------


def test_low_confidence_flags_for_review():
    """Document with ambiguous signals should be flagged for manual review."""
    doc = _make_doc(
        "ambiguous_paper",
        "This paper discusses information.",  # no strong signals
    )
    docs = classify_corpus([doc])
    assert docs[0].metadata.get("needs_manual_review", False) is True


# ---------------------------------------------------------------------------
# Property-based: corpus classification never crashes
# ---------------------------------------------------------------------------


def test_corpus_classification_no_crash():
    """classify_corpus should complete without raising for any text content."""
    import string
    texts = [
        "Random text with no signals.",
        "Baseline experiment dataset accuracy F1-score evaluation results.",
        "Survey review taxonomy overview literature systematic.",
        "Algorithm architecture framework novel propose introduce convergence.",
        "",  # empty text
    ]
    docs = [_make_doc(f"doc_{i}", t) for i, t in enumerate(texts)]
    result = classify_corpus(docs)
    assert len(result) == len(docs)
    for d in result:
        assert d.category in list(DocumentCategory)
