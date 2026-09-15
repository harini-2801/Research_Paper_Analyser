"""
PDF Ingestion and Segmentation (Requirement 1).

Extracts full text from PDFs and splits each document into logical sections
(abstract, introduction, related_work, methodology, experiments, results,
conclusion, references).  Section boundaries are detected using a set of
heuristic heading patterns that cover the majority of academic paper formats.

Emits ProgressEvents after each document is processed.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from pathlib import Path

import fitz  # PyMuPDF

from rpra.models import Document, PipelineStageStatus, ProgressEvent, Segment

# ---------------------------------------------------------------------------
# Heading-to-section-type mapping (order matters — first match wins)
# ---------------------------------------------------------------------------

_SECTION_PATTERNS: list[tuple[str, str]] = [
    (r"\babstract\b", "abstract"),
    (r"\bintroduction\b", "introduction"),
    (r"\brelated\s+work\b|\bliterature\s+review\b", "related_work"),
    (r"\bmethod(ology|s)?\b|\bapproach\b|\bproposed\s+system\b", "methodology"),
    (r"\bexperiment(s|al\s+setup)?\b|\bimplementation\b", "experiments"),
    (r"\bresult(s)?\b|\bevaluation\b|\bperformance\b", "results"),
    (r"\bconclusion(s)?\b|\bfuture\s+work\b|\bdiscussion\b", "conclusion"),
    (r"\breference(s)?\b|\bbibliograph(y|ies)\b", "references"),
]

_COMPILED_PATTERNS = [
    (re.compile(pat, re.IGNORECASE), label) for pat, label in _SECTION_PATTERNS
]


def _classify_heading(text: str) -> str | None:
    """Return the section label for a heading string, or None if not a heading."""
    stripped = text.strip()
    # Typical headings are short (≤ 80 chars) and do not end with punctuation
    if len(stripped) > 80 or stripped.endswith("."):
        return None
    for pattern, label in _COMPILED_PATTERNS:
        if pattern.search(stripped):
            return label
    return None


def _is_bold_or_large(block: dict) -> bool:
    """Heuristic: check if a text block contains bold/large spans (heading candidate)."""
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            flags = span.get("flags", 0)
            size = span.get("size", 0)
            is_bold = bool(flags & 2**4)  # flag bit 4 = bold
            if is_bold or size >= 12:
                return True
    return False


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------


def extract_document(pdf_path: str | Path, segment_types: list[str]) -> Document:
    """
    Parse a single PDF and return a :class:`Document` with its segments.

    Parameters
    ----------
    pdf_path:
        Absolute or relative path to the PDF file.
    segment_types:
        Ordered list of expected segment type labels (from config).

    Returns
    -------
    Document
        Populated document object.  On parse failure an empty Document is
        returned and the caller is expected to log the error.
    """
    pdf_path = Path(pdf_path)
    doc_id = pdf_path.stem
    doc = Document(id=doc_id, file_path=str(pdf_path))

    pdf = fitz.open(str(pdf_path))

    # -----------------------------------------------------------------
    # Pass 1 — collect (page, is_heading_candidate, text) tuples
    # -----------------------------------------------------------------
    raw_pages: list[tuple[int, str]] = []  # (page_number_1indexed, full_page_text)
    for page_idx in range(len(pdf)):
        page = pdf[page_idx]
        raw_pages.append((page_idx + 1, page.get_text("text")))

    pdf_dict_pages = []
    pdf2 = fitz.open(str(pdf_path))
    for page_idx in range(len(pdf2)):
        pdf_dict_pages.append(pdf2[page_idx].get_text("dict"))
    pdf2.close()
    pdf.close()

    # -----------------------------------------------------------------
    # Pass 2 — split into sections based on heading detection
    # -----------------------------------------------------------------
    # Build a flat list of (page, line_text) pairs
    all_lines: list[tuple[int, str, bool]] = []  # (page, text, is_bold_large)
    for page_idx, page_dict in enumerate(pdf_dict_pages):
        page_num = page_idx + 1
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue
            bold_large = _is_bold_or_large(block)
            for line in block.get("lines", []):
                line_text = " ".join(
                    span["text"] for span in line.get("spans", []) if span.get("text")
                ).strip()
                if line_text:
                    all_lines.append((page_num, line_text, bold_large))

    # -----------------------------------------------------------------
    # Pass 3 — group lines into sections
    # -----------------------------------------------------------------
    sections: list[tuple[str, int, list[str]]] = []  # (label, start_page, lines)
    current_label = "preamble"
    current_page = 1
    current_lines: list[str] = []

    for page_num, line_text, bold_large in all_lines:
        # Only attempt heading detection on bold/large or standalone short lines
        heading_label: str | None = None
        if bold_large or len(line_text) < 60:
            heading_label = _classify_heading(line_text)

        if heading_label and heading_label in segment_types:
            if current_lines:
                sections.append((current_label, current_page, current_lines))
            current_label = heading_label
            current_page = page_num
            current_lines = []
        else:
            current_lines.append(line_text)

    if current_lines:
        sections.append((current_label, current_page, current_lines))

    # -----------------------------------------------------------------
    # Pass 4 — build Segment objects and infer title
    # -----------------------------------------------------------------
    for label, start_page, lines in sections:
        if label == "preamble":
            # Try to infer document title from the first non-empty line
            for line in lines:
                if len(line.strip()) > 10:
                    doc.title = line.strip()[:200]
                    break
            continue  # don't create a segment for preamble

        text = "\n".join(lines).strip()
        if not text:
            continue

        segment = Segment(
            doc_id=doc_id,
            section_type=label,
            page_start=start_page,
            page_end=start_page,  # end page refinement is a future enhancement
            text=text,
        )
        doc.segments.append(segment)

    return doc


# ---------------------------------------------------------------------------
# Corpus ingestion
# ---------------------------------------------------------------------------


def ingest_corpus(
    corpus_path: str | Path,
    segment_types: list[str],
    max_documents: int = 10_000,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> tuple[list[Document], list[dict]]:
    """
    Ingest all PDF files under *corpus_path*.

    Parameters
    ----------
    corpus_path:
        Directory containing PDF files (searched non-recursively).
    segment_types:
        Expected segment types from config.
    max_documents:
        Hard upper limit on files processed (Requirement 1.6).
    on_progress:
        Optional callback receiving :class:`ProgressEvent` objects.

    Returns
    -------
    documents:
        Successfully parsed :class:`Document` objects.
    errors:
        List of ``{"file": str, "reason": str}`` dicts for failed files.
    """
    corpus_path = Path(corpus_path)
    pdf_files = sorted(corpus_path.glob("*.pdf"))[:max_documents]

    documents: list[Document] = []
    errors: list[dict] = []

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    for pdf_path in pdf_files:
        start = time.perf_counter()
        emit(
            ProgressEvent(
                stage="ingestion",
                doc_id=pdf_path.stem,
                status=PipelineStageStatus.RUNNING,
                message=f"Parsing {pdf_path.name}",
            )
        )
        try:
            # Reject non-PDF by extension (Requirement 1.7 already filtered by glob,
            # but check magic bytes for safety)
            with open(pdf_path, "rb") as f:
                header = f.read(4)
            if header != b"%PDF":
                raise ValueError("File does not start with %PDF magic bytes.")

            doc = extract_document(pdf_path, segment_types)
            documents.append(doc)

            elapsed = time.perf_counter() - start
            emit(
                ProgressEvent(
                    stage="ingestion",
                    doc_id=doc.id,
                    status=PipelineStageStatus.COMPLETE,
                    message=f"Parsed {pdf_path.name} -> {len(doc.segments)} segments",
                    details={"segments": len(doc.segments), "title": doc.title},
                    elapsed_seconds=round(elapsed, 2),
                )
            )

        except Exception as exc:
            elapsed = time.perf_counter() - start
            errors.append({"file": str(pdf_path), "reason": str(exc)})
            emit(
                ProgressEvent(
                    stage="ingestion",
                    doc_id=pdf_path.stem,
                    status=PipelineStageStatus.FAILED,
                    message=f"Failed to parse {pdf_path.name}: {exc}",
                    elapsed_seconds=round(elapsed, 2),
                )
            )

    return documents, errors
