"""
PDF Ingestion and Segmentation (Requirement 1).

Extracts text from PDFs and splits each document into logical sections
(abstract, introduction, related_work, methodology, experiments, results,
conclusion, references).

Why heading detection works the way it does
-------------------------------------------
The naive approach - "a short line containing the word `results` is a Results
heading" - fails badly on real papers, in three separate ways:

*Two-column layouts.* Column width is roughly 40 characters, so **every** body
line is short. Combined with a substring match, lines like "These results
suggest that the aggregate supervision" and "the performance of this approach"
were being read as section headings. One paper produced 186 sections.

*Small-caps headings.* ICLR-style papers set headings in small caps, and the
extractor injects a space after the leading capital: `I NTRODUCTION`,
`R ELATED   WORK`. Word-boundary matching never fires, so a paper produced zero
sections - and because unlabelled content was discarded, the entire document was
silently dropped.

*Inconsistent emphasis.* Headings are not reliably bold. ALBERT's are set in the
regular face; CLIP's and ResNet's are medium.

What is reliable across all of them is **relative font size**: headings are set
larger than the body. Measuring the document's own modal body size and comparing
against it works where a hardcoded threshold does not. That, plus section
numbering, plus matching the section word at the *start* of the line, is what
this module uses.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import fitz  # PyMuPDF

from rpra.models import Document, PipelineStageStatus, ProgressEvent, Segment

# ---------------------------------------------------------------------------
# Section patterns
# ---------------------------------------------------------------------------

# Anchored at the start of the line (after numbering is stripped). A body line
# that merely *mentions* "results" no longer qualifies; only one that begins
# with it does.
_SECTION_PATTERNS: list[tuple[str, str]] = [
    (r"^abstract\b", "abstract"),
    (r"^introduction\b", "introduction"),
    ((r"^(related\s+work|background|literature\s+review|prior\s+work|"
      r"related\s+literature)\b"), "related_work"),
    ((r"^(method(s|ology|ologies)?|approach|proposed\s+\w+|model|models|"
      r"architecture|framework|preliminaries|problem\s+(statement|formulation)|"
      r"system\s+design)\b"), "methodology"),
    ((r"^(experiment(s|al)?(\s+(setup|settings?|details?|protocol))?|"
      r"implementation(\s+details?)?|setup|training\s+details?|datasets?)\b"), "experiments"),
    ((r"^(results?|evaluation|performance|ablations?(\s+stud(y|ies))?|"
      r"analysis|findings|comparison)\b"), "results"),
    ((r"^(conclusions?|concluding\s+remarks|summary|discussion|future\s+work|"
      r"limitations?|broader\s+impacts?)\b"), "conclusion"),
    (r"^(references?|bibliography|works\s+cited)\b", "references"),
]

_COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), label) for p, label in _SECTION_PATTERNS]

# Leading section numbering: "3.", "2.3", "IV.", "A.1", "Chapter 4".
_NUMBERING_RE = re.compile(
    r"^\s*(?:(?:chapter|section|appendix)\s+)?"
    r"(?:\d{1,2}(?:\.\d{1,2}){0,3}|[IVXLC]{1,5}|[A-H])"
    r"\s*[.):]?\s+",
    re.IGNORECASE,
)

# A bare number with no trailing text is a page number, not a heading.
_BARE_NUMBER_RE = re.compile(r"^[\d.\s()IVXLC]+$", re.IGNORECASE)

# Running heads and stamps that masquerade as titles.
_TITLE_NOISE_RE = re.compile(
    r"arxiv[:\s]|preprint|under\s+review|published\s+as|accepted\s+(at|to)|"
    r"proceedings\s+of|conference\s+on|workshop\s+on|journal\s+of|"
    r"copyright|all\s+rights\s+reserved|doi[:\s]|"
    r"^\s*\d+\s*$|^\s*(submitted|revised|accepted)\b",
    re.IGNORECASE,
)

_MAX_HEADING_CHARS = 90
_MAX_HEADING_WORDS = 10
# A heading must exceed body size by at least this much to count as larger.
_SIZE_MARGIN = 0.4

_BOLD_FLAG = 1 << 4


# ---------------------------------------------------------------------------
# Line model
# ---------------------------------------------------------------------------


class _Line:
    """One extracted text line with the typography needed to classify it."""

    __slots__ = ("bold", "page", "size", "text", "x0", "y0")

    def __init__(self, page: int, text: str, size: float, bold: bool, x0: float, y0: float):
        self.page = page
        self.text = text
        self.size = size
        self.bold = bold
        self.x0 = x0
        self.y0 = y0


def _extract_lines(pdf: fitz.Document) -> list[_Line]:
    """
    Flatten the document into lines, in reading order.

    ``sort=True`` asks PyMuPDF to order blocks top-to-bottom, left-to-right,
    which keeps two-column pages from interleaving their columns.
    """
    lines: list[_Line] = []

    for page_index in range(len(pdf)):
        page = pdf[page_index]
        try:
            data = page.get_text("dict", sort=True)
        except TypeError:  # older PyMuPDF without the sort argument
            data = page.get_text("dict")

        for block in data.get("blocks", []):
            if block.get("type") != 0:  # 0 = text
                continue
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = " ".join(s["text"] for s in spans).strip()
                if not text:
                    continue
                bbox = line.get("bbox", (0, 0, 0, 0))
                lines.append(
                    _Line(
                        page=page_index + 1,
                        text=text,
                        size=max(float(s.get("size", 0)) for s in spans),
                        bold=any(int(s.get("flags", 0)) & _BOLD_FLAG for s in spans),
                        x0=float(bbox[0]),
                        y0=float(bbox[1]),
                    )
                )

    return lines


def _body_font_size(lines: list[_Line]) -> float:
    """
    The document's dominant body-text size.

    Weighted by characters so a handful of large headings cannot outvote the
    body. This is the baseline every heading test is measured against, and it is
    what makes detection survive different publisher templates.
    """
    weights: Counter[float] = Counter()
    for line in lines:
        weights[round(line.size, 1)] += len(line.text)

    if not weights:
        return 10.0
    return weights.most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Heading classification
# ---------------------------------------------------------------------------


def normalise_heading(text: str) -> str:
    """
    Repair small-caps letter spacing so headings can be matched.

    Small-caps headings extract with a space after the leading capital:
    ``I NTRODUCTION``, ``R ELATED   WORK``, ``E XPERIMENTAL  R ESULTS``. Joining
    a lone capital to the uppercase run that follows recovers the real word.
    """
    repaired = re.sub(r"\b([A-Z])\s+([A-Z]{2,})", r"\1\2", text)
    return re.sub(r"\s+", " ", repaired).strip()


def clean_title(text: str) -> str:
    """
    Tidy a recovered title for display and for citation matching.

    Small-caps rendering leaves artefacts that ``normalise_heading`` alone does
    not reach: a one-letter word split off its neighbour (``A N IMAGE``,
    ``SCI BERT``) and punctuation floated away from the word it belongs to
    (``LARGE -SCALE``, ``BERT :``). Both matter, because a title is compared
    against reference strings when detecting intra-corpus citations.

    "A" and "I" are deliberately excluded from the letter-rejoining rule. They
    are the only single-letter English words, so joining them to a neighbour is
    as likely to corrupt a real title - "A LITE BERT" would become "ALITE BERT" -
    as it is to repair an artefact. Titles rarely open with a section word, so
    leaving them split is the safer trade. Heading classification, which *does*
    need "A BSTRACT" to resolve, tries both spellings instead.
    """
    # Rejoin a lone capital to the uppercase run it was split from, skipping
    # A and I for the reason above.
    cleaned = re.sub(r"\b([B-HJ-Z])\s+([A-Z]{2,})", r"\1\2", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Rejoin two adjacent lone capitals: "A N IMAGE" -> "AN IMAGE". Bounded so a
    # pathological input cannot loop.
    for _ in range(3):
        merged = re.sub(r"\b([A-Z])\s+([A-Z])\b", r"\1\2", cleaned)
        if merged == cleaned:
            break
        cleaned = merged

    # Punctuation floated away from its word.
    cleaned = re.sub(r"\s+([:;,.!?])", r"\1", cleaned)
    cleaned = re.sub(r"\s+-\s*(?=[A-Za-z])", "-", cleaned)
    cleaned = re.sub(r"(?<=[A-Za-z])\s*-\s+", "-", cleaned)

    return re.sub(r"\s+", " ", cleaned).strip()


def strip_numbering(text: str) -> str:
    """Remove leading section numbering, returning the heading body."""
    return _NUMBERING_RE.sub("", text).strip()


def looks_like_heading(line: _Line, body_size: float) -> bool:
    """
    Decide whether *line* is typographically a heading.

    Length alone is useless in two columns, where every body line is short, so a
    line must additionally be visually distinguished: larger than body text,
    bold, explicitly numbered, or set in caps.
    """
    text = line.text.strip()

    if not text or len(text) > _MAX_HEADING_CHARS:
        return False
    if _BARE_NUMBER_RE.match(text):
        return False
    # Headings are not sentences.
    if text.endswith((".", ",", ";", ":")) and not _NUMBERING_RE.match(text):
        return False
    if len(normalise_heading(text).split()) > _MAX_HEADING_WORDS:
        return False

    is_larger = line.size >= body_size + _SIZE_MARGIN
    is_numbered = bool(_NUMBERING_RE.match(text))
    # All-caps is how small-caps headings survive extraction.
    letters = [c for c in text if c.isalpha()]
    is_upper = bool(letters) and len(letters) > 2 and all(c.isupper() for c in letters)

    return is_larger or line.bold or is_numbered or is_upper


def classify_heading(text: str) -> str | None:
    """
    Map heading text to a section label, or None.

    Matching happens after small-caps repair and numbering removal, and the
    pattern is anchored to the start, so a line must *begin* with the section
    word rather than merely contain it.

    Both the repaired and the raw spelling are tried. Small-caps repair is what
    makes ``A BSTRACT`` resolve, but it must not be the only spelling considered:
    a heading that needs no repair should not be forced through it.
    """
    for body in (
        strip_numbering(normalise_heading(text)),
        strip_numbering(text.strip()),
    ):
        if not body:
            continue
        for pattern, label in _COMPILED_PATTERNS:
            if pattern.match(body):
                return label
    return None


def _is_bold_or_large(block: dict) -> bool:
    """Whether a raw PyMuPDF block contains bold or large spans."""
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            if int(span.get("flags", 0)) & _BOLD_FLAG or float(span.get("size", 0)) >= 12:
                return True
    return False


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------


def _infer_title(pdf: fitz.Document, lines: list[_Line], fallback: str) -> str:
    """
    Recover the paper title.

    Tries PDF metadata first, then the largest type on page one. Running heads
    and arXiv stamps are excluded: they are often the physically first line, so
    "the first line on the page" picks them every time.
    """
    metadata_title = ((pdf.metadata or {}).get("title") or "").strip()
    if (
        len(metadata_title) > 12
        and not _TITLE_NOISE_RE.search(metadata_title)
        and not metadata_title.lower().endswith(".pdf")
    ):
        return metadata_title[:300]

    first_page = [ln for ln in lines if ln.page == 1]
    if not first_page:
        return fallback

    usable = [
        ln for ln in first_page
        if not _TITLE_NOISE_RE.search(ln.text) and len(ln.text.strip()) > 3
    ]
    if not usable:
        return fallback

    # The title is the largest type on the page; collect every line at that size
    # because titles routinely wrap onto two or three lines.
    largest = max(ln.size for ln in usable)
    title_lines = sorted(
        (ln for ln in usable if ln.size >= largest - 0.3),
        key=lambda ln: ln.y0,
    )

    title = clean_title(" ".join(ln.text for ln in title_lines))

    return title[:300] if len(title) >= 8 else fallback


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------


def extract_document(pdf_path: str | Path, segment_types: list[str]) -> Document:
    """
    Parse a single PDF into a :class:`Document` with segments.

    If no headings can be identified the document is still returned with its
    text intact, chunked by page, rather than discarded. Losing an entire paper
    because its template was unusual is worse than segmenting it coarsely.
    """
    pdf_path = Path(pdf_path)
    doc_id = pdf_path.stem
    doc = Document(id=doc_id, file_path=str(pdf_path))

    pdf = fitz.open(str(pdf_path))
    try:
        lines = _extract_lines(pdf)
        doc.metadata["page_count"] = len(pdf)
        doc.title = _infer_title(pdf, lines, fallback=doc_id.replace("_", " "))
    finally:
        pdf.close()

    if not lines:
        doc.metadata["segmentation"] = "empty"
        return doc

    body_size = _body_font_size(lines)
    doc.metadata["body_font_size"] = body_size

    allowed = set(segment_types)

    # ---- group lines into sections --------------------------------------
    sections: list[tuple[str, int, int, list[str]]] = []
    current_label = "preamble"
    current_start = lines[0].page
    current_end = lines[0].page
    current: list[str] = []
    heading_hits = 0

    for line in lines:
        label = classify_heading(line.text) if looks_like_heading(line, body_size) else None

        if label and label in allowed:
            if current:
                sections.append((current_label, current_start, current_end, current))
            heading_hits += 1
            current_label = label
            current_start = line.page
            current_end = line.page
            current = []
        else:
            current.append(line.text)
            current_end = line.page

    if current:
        sections.append((current_label, current_start, current_end, current))

    doc.metadata["headings_detected"] = heading_hits

    # ---- fall back rather than lose the document -------------------------
    if heading_hits == 0:
        doc.metadata["segmentation"] = "fallback_pages"
        _append_page_segments(doc, lines)
        return doc

    doc.metadata["segmentation"] = "headings"

    # ---- merge repeated labels ------------------------------------------
    # A paper has one Results section, not thirteen; subsections carrying the
    # same label belong to the same logical part of the paper.
    merged: dict[str, dict] = {}
    order: list[str] = []

    for label, start, end, body in sections:
        if label == "preamble":
            continue
        text = "\n".join(body).strip()
        if not text:
            continue
        if label not in merged:
            merged[label] = {"start": start, "end": end, "parts": []}
            order.append(label)
        merged[label]["parts"].append(text)
        merged[label]["start"] = min(merged[label]["start"], start)
        merged[label]["end"] = max(merged[label]["end"], end)

    for label in order:
        entry = merged[label]
        doc.segments.append(
            Segment(
                doc_id=doc_id,
                section_type=label,
                page_start=entry["start"],
                page_end=entry["end"],
                text="\n".join(entry["parts"]).strip(),
            )
        )

    if not doc.segments:
        doc.metadata["segmentation"] = "fallback_pages"
        _append_page_segments(doc, lines)

    return doc


def _append_page_segments(doc: Document, lines: list[_Line], chunk_pages: int = 3) -> None:
    """
    Chunk a document by page when heading detection finds nothing.

    The label is ``body``, which downstream stages treat as an ordinary section
    with no section affinity. The paper still contributes entities, a graph
    presence and relationship scores instead of vanishing.
    """
    by_page: dict[int, list[str]] = {}
    for line in lines:
        by_page.setdefault(line.page, []).append(line.text)

    pages = sorted(by_page)
    for i in range(0, len(pages), chunk_pages):
        group = pages[i : i + chunk_pages]
        text = "\n".join("\n".join(by_page[p]) for p in group).strip()
        if not text:
            continue
        doc.segments.append(
            Segment(
                doc_id=doc.id,
                section_type="body",
                page_start=group[0],
                page_end=group[-1],
                text=text,
            )
        )


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

    Returns the parsed documents and a list of ``{"file", "reason"}`` records for
    files that could not be read.
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
            with open(pdf_path, "rb") as fh:
                header = fh.read(4)
            if header != b"%PDF":
                raise ValueError("File does not start with %PDF magic bytes.")

            doc = extract_document(pdf_path, segment_types)
        except Exception as exc:
            errors.append({"file": str(pdf_path), "reason": str(exc)})
            emit(
                ProgressEvent(
                    stage="ingestion",
                    doc_id=pdf_path.stem,
                    status=PipelineStageStatus.FAILED,
                    message=f"Failed to parse {pdf_path.name}: {exc}",
                    elapsed_seconds=round(time.perf_counter() - start, 2),
                )
            )
            continue

        documents.append(doc)
        emit(
            ProgressEvent(
                stage="ingestion",
                doc_id=doc.id,
                status=PipelineStageStatus.COMPLETE,
                message=f"Parsed {pdf_path.name} -> {len(doc.segments)} segments",
                details={
                    "segments": len(doc.segments),
                    "title": doc.title,
                    "mode": doc.metadata.get("segmentation", ""),
                    "headings": doc.metadata.get("headings_detected", 0),
                },
                elapsed_seconds=round(time.perf_counter() - start, 2),
            )
        )

    return documents, errors
