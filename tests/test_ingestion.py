"""
Tests for PDF ingestion and segmentation (Requirement 1).

Each test here pins a failure observed on real papers. Heading detection used to
key off "a short line containing a section word", which broke in three distinct
ways that only appear outside synthetic corpora.
"""

from __future__ import annotations

import pytest

from rpra.ingestion import (
    _BOLD_FLAG,
    _body_font_size,
    _Line,
    classify_heading,
    clean_title,
    extract_document,
    looks_like_heading,
    normalise_heading,
    strip_numbering,
)
from rpra.models import Document


def line(text: str, size: float = 10.0, bold: bool = False, page: int = 1) -> _Line:
    return _Line(page=page, text=text, size=size, bold=bold, x0=50.0, y0=100.0)


# ---------------------------------------------------------------------------
# Small-caps repair
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("I NTRODUCTION", "INTRODUCTION"),
        ("R ELATED   WORK", "RELATED WORK"),
        ("E XPERIMENTAL  R ESULTS", "EXPERIMENTAL RESULTS"),
        ("A BSTRACT", "ABSTRACT"),
        ("R EFERENCES", "REFERENCES"),
    ],
)
def test_repairs_small_caps_letter_spacing(raw, expected):
    """
    ICLR-style small-caps headings extract with a space after the leading
    capital. Word-boundary matching never fired, so these papers produced zero
    sections and were then discarded entirely.
    """
    assert normalise_heading(raw) == expected


def test_mixed_case_headings_are_left_alone():
    assert normalise_heading("Related Work") == "Related Work"
    assert normalise_heading("3. Deep Residual Learning") == "3. Deep Residual Learning"


# ---------------------------------------------------------------------------
# Numbering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1. Introduction", "Introduction"),
        ("2.3. Selecting a Method", "Selecting a Method"),
        ("IV. Experiments", "Experiments"),
        ("Section 4 Results", "Results"),
        ("Introduction", "Introduction"),
    ],
)
def test_strips_section_numbering(raw, expected):
    assert strip_numbering(raw) == expected


# ---------------------------------------------------------------------------
# Classification is anchored, not substring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,label",
    [
        ("Abstract", "abstract"),
        ("1. Introduction and Motivating Work", "introduction"),
        ("2. Related Work", "related_work"),
        ("3. Approach", "methodology"),
        ("4. Experiments", "experiments"),
        ("5. Results", "results"),
        ("6. Conclusion", "conclusion"),
        ("References", "references"),
        ("I NTRODUCTION", "introduction"),
        ("R ELATED   WORK", "related_work"),
    ],
)
def test_classifies_real_headings(text, label):
    assert classify_heading(text) == label


@pytest.mark.parametrize(
    "body_line",
    [
        "These results suggest that the aggregate supervision acces-",
        "the performance of this approach by benchmark-",
        "serve that transfer performance is a smoothly predictable",
        "trastive Language-Image Pre-training, is an efficient method",
        "balance the results by including up to 20,000 (image, text)",
    ],
)
def test_body_lines_are_not_headings(body_line):
    """
    Real body lines from a two-column paper. Substring matching classified every
    one of these as a section heading, which is how one paper produced 186
    sections.
    """
    assert classify_heading(body_line) is None


# ---------------------------------------------------------------------------
# Typographic gate
# ---------------------------------------------------------------------------


def test_short_body_line_is_not_a_heading_candidate():
    """
    Column width is ~40 characters, so length alone says nothing. Without a
    visual signal, a short line must not qualify.
    """
    assert not looks_like_heading(line("these results suggest that", size=10.0), 10.0)


def test_larger_type_makes_a_heading_candidate():
    """The signal that works across templates: headings are set larger."""
    assert looks_like_heading(line("Introduction", size=12.0), 10.0)


def test_bold_at_body_size_still_qualifies():
    assert looks_like_heading(line("Introduction", size=10.0, bold=True), 10.0)


def test_numbered_line_qualifies_without_other_signals():
    assert looks_like_heading(line("3. Deep Residual Learning", size=10.0), 10.0)


def test_all_caps_line_qualifies():
    """How small-caps headings survive extraction."""
    assert looks_like_heading(line("INTRODUCTION", size=10.0), 10.0)


def test_sentences_are_rejected():
    assert not looks_like_heading(
        line("We evaluate the approach on three datasets.", size=12.0), 10.0
    )


def test_page_numbers_are_rejected():
    assert not looks_like_heading(line("12", size=12.0), 10.0)
    assert not looks_like_heading(line("IV.", size=12.0), 10.0)


def test_long_lines_are_rejected():
    assert not looks_like_heading(line("Results " * 20, size=14.0), 10.0)


# ---------------------------------------------------------------------------
# Body size estimation
# ---------------------------------------------------------------------------


def test_body_size_is_the_character_weighted_mode():
    """
    Weighting by characters stops a handful of large headings from outvoting the
    body, which is what makes the relative-size comparison trustworthy.
    """
    lines = [line("x" * 500, size=10.0), line("Introduction", size=12.0)]
    assert _body_font_size(lines) == 10.0


def test_body_size_defaults_when_empty():
    assert _body_font_size([]) == 10.0


# ---------------------------------------------------------------------------
# Titles
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("VERY DEEP NETWORKS FOR LARGE -SCALE RECOGNITION",
         "VERY DEEP NETWORKS FOR LARGE-SCALE RECOGNITION"),
        ("ALBERT: A LITE BERT FOR SELF - SUPERVISED LEARNING",
         "ALBERT: A LITE BERT FOR SELF-SUPERVISED LEARNING"),
        ("BERT : A Model", "BERT: A Model"),
    ],
)
def test_title_cleanup_repairs_spacing_artifacts(raw, expected):
    assert clean_title(raw) == expected


def test_title_cleanup_leaves_ordinary_titles_alone():
    for title in [
        "Attention Is All You Need",
        "Deep Residual Learning for Image Recognition",
        "Densely Connected Convolutional Networks",
    ]:
        assert clean_title(title) == title


# ---------------------------------------------------------------------------
# Document-level behaviour on generated PDFs
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory):
    pytest.importorskip("fitz", reason="PyMuPDF required")
    from rpra.sample_corpus import PAPERS, build_pdf

    directory = tmp_path_factory.mktemp("ingest")
    return build_pdf(PAPERS[0], directory)


SEGMENT_TYPES = [
    "abstract", "introduction", "related_work", "methodology",
    "experiments", "results", "conclusion", "references",
]


def test_extracts_segments_and_title(sample_pdf):
    doc = extract_document(sample_pdf, SEGMENT_TYPES)
    assert isinstance(doc, Document)
    assert doc.segments
    assert doc.title
    assert doc.metadata["segmentation"] == "headings"


def test_each_section_label_appears_at_most_once(sample_pdf):
    """
    A paper has one Results section, not thirteen. Subsections carrying the same
    label are merged, so downstream stages see one coherent block per part.
    """
    doc = extract_document(sample_pdf, SEGMENT_TYPES)
    labels = [s.section_type for s in doc.segments]
    assert len(labels) == len(set(labels))


def test_page_ranges_are_sane(sample_pdf):
    doc = extract_document(sample_pdf, SEGMENT_TYPES)
    for segment in doc.segments:
        assert segment.page_start >= 1
        assert segment.page_end >= segment.page_start


def test_segments_carry_text(sample_pdf):
    doc = extract_document(sample_pdf, SEGMENT_TYPES)
    assert all(s.text.strip() for s in doc.segments)


def test_document_is_not_lost_when_no_heading_is_found(tmp_path):
    """
    The original code discarded every unlabelled line, so a paper whose template
    defeated heading detection silently produced zero segments and contributed
    nothing. Falling back to page chunks keeps it in the analysis.
    """
    pytest.importorskip("fitz", reason="PyMuPDF required")
    import fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_textbox(
        fitz.Rect(60, 60, 520, 700),
        "This document has no recognisable section headings whatsoever. "
        "It simply contains prose about evaluating a system on a dataset, "
        "written continuously without any structural markers at all. " * 6,
        fontsize=10,
    )
    path = tmp_path / "unstructured.pdf"
    pdf.save(str(path))
    pdf.close()

    doc = extract_document(path, SEGMENT_TYPES)
    assert doc.segments, "an unsegmentable document must not be discarded"
    assert doc.metadata["segmentation"] == "fallback_pages"
    assert all(s.section_type == "body" for s in doc.segments)
