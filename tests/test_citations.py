"""Tests for reference parsing and the citation score dimension."""

from __future__ import annotations

from rpra.citations import (
    detect_intra_corpus_citations,
    extract_citation_key,
    parse_corpus_references,
    parse_references,
    split_reference_entries,
)
from rpra.models import Document, RelationType, Segment
from rpra.scoring import _citation_overlap

NUMBERED = (
    "[1] Chen, L., Patel, R. On the Reproducibility of Residual Network Benchmarks. "
    "Journal of Machine Learning Studies, 2022. "
    "[2] Kumar, S., Alvarez, M. Attention Mechanisms for Reading Comprehension at Scale. "
    "Proceedings of NLP Conference, 2021. "
    "[3] Ivanova, T. Data Augmentation Strategies Revisited. Vision Journal, 2020."
)


def doc_with_references(doc_id: str, block: str, title: str = "") -> Document:
    return Document(
        id=doc_id,
        title=title,
        file_path=f"{doc_id}.pdf",
        segments=[
            Segment(
                doc_id=doc_id,
                section_type="references",
                page_start=9,
                page_end=9,
                text=block,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Splitting
# ---------------------------------------------------------------------------


def test_splits_numbered_reference_list():
    assert len(split_reference_entries(NUMBERED)) == 3


def test_empty_block_yields_no_entries():
    assert split_reference_entries("") == []
    assert split_reference_entries("   \n  ") == []


# ---------------------------------------------------------------------------
# Key extraction
# ---------------------------------------------------------------------------


def test_extracts_title_as_the_citation_key():
    key = extract_citation_key(
        "Chen, L., Patel, R. On the Reproducibility of Residual Network Benchmarks. "
        "Journal of Machine Learning Studies, 2022."
    )
    assert key == "on the reproducibility of residual network benchmarks"


def test_key_is_normalised_for_comparison():
    key = extract_citation_key("Smith, J. Deep Learning, Revisited: A Study. Proc. ICML, 2020.")
    assert key is not None
    assert key == key.lower()
    assert ":" not in key and "," not in key


def test_too_short_entry_returns_none():
    assert extract_citation_key("[1] ibid.") is None


# ---------------------------------------------------------------------------
# Document-level parsing
# ---------------------------------------------------------------------------


def test_parse_references_writes_metadata():
    doc = doc_with_references("d1", NUMBERED)
    keys = parse_references(doc)

    assert len(keys) == 3
    assert doc.metadata["cited_titles"] == keys
    assert doc.metadata["reference_count"] == 3


def test_document_without_references_gets_empty_metadata():
    doc = Document(id="d1", title="T", file_path="d1.pdf")
    assert parse_references(doc) == []
    assert doc.metadata["cited_titles"] == []


# ---------------------------------------------------------------------------
# Intra-corpus citation detection
# ---------------------------------------------------------------------------


def test_detects_a_paper_citing_another_in_the_corpus():
    citing = doc_with_references("citing", NUMBERED, title="A Citing Paper")
    cited = Document(
        id="cited",
        title="On the Reproducibility of Residual Network Benchmarks",
        file_path="cited.pdf",
    )
    relations = parse_corpus_references([citing, cited])

    assert len(relations) == 1
    relation = relations[0]
    assert relation.source_id == "citing"
    assert relation.target_id == "cited"
    assert relation.relation_type == RelationType.CITES
    assert relation.is_cross_document
    assert relation.evidence.section == "references"


def test_unrelated_title_is_not_matched():
    citing = doc_with_references("citing", NUMBERED, title="A Citing Paper")
    other = Document(
        id="other",
        title="Entirely Unrelated Work On Something Else Completely",
        file_path="other.pdf",
    )
    assert parse_corpus_references([citing, other]) == []


def test_a_document_does_not_cite_itself():
    doc = doc_with_references(
        "self", NUMBERED, title="On the Reproducibility of Residual Network Benchmarks"
    )
    assert detect_intra_corpus_citations([doc]) == []


# ---------------------------------------------------------------------------
# Feeding the score
# ---------------------------------------------------------------------------


def test_shared_bibliography_produces_citation_overlap():
    """The citation dimension stayed at zero until references were parsed."""
    a = Document(id="a", title="A", file_path="a.pdf")
    b = Document(id="b", title="B", file_path="b.pdf")
    a.metadata["cited_titles"] = ["paper one", "paper two", "paper three"]
    b.metadata["cited_titles"] = ["paper two", "paper three", "paper four"]

    overlap = _citation_overlap(a, b)
    assert overlap == 0.5  # 2 shared of 4 unique


def test_direct_citation_counts_as_maximal_overlap():
    a = Document(id="a", title="A", file_path="a.pdf")
    b = Document(id="b", title="B", file_path="b.pdf")
    a.metadata["cites_doc_ids"] = ["b"]
    assert _citation_overlap(a, b) == 1.0
    assert _citation_overlap(b, a) == 1.0


def test_no_references_means_no_overlap():
    a = Document(id="a", title="A", file_path="a.pdf")
    b = Document(id="b", title="B", file_path="b.pdf")
    assert _citation_overlap(a, b) == 0.0
