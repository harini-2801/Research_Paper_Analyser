"""
PDF report generation (Requirement 17).

Renders a pipeline result as a typeset PDF: cover page with the headline
figures, the strongest relationships, each confirmed contradiction set as a
two-column spread with its evidence, and the ranked research gaps.

Built on PyMuPDF, which is already a core dependency because ingestion reads
PDFs with it. Using it to write them too keeps the deployable install at 174 MB;
reportlab or weasyprint would each add more than the rest of the service.

The layout is a small flowing-text engine: `_Page` tracks a cursor down the
page, every draw call returns the height it consumed, and a break is taken when
the next block will not fit. That is enough for a report and avoids a dependency
whose only job would be pagination.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

from rpra.models import (
    Contradiction,
    ContradictionStatus,
    Document,
    RelationshipScore,
    ResearchGap,
)

# Page geometry, in points.
_WIDTH, _HEIGHT = fitz.paper_size("a4")
_MARGIN = 56.0
_CONTENT_WIDTH = _WIDTH - 2 * _MARGIN
_BOTTOM = _HEIGHT - 56.0

# Palette, echoing the interface: ink, academic gold, and the status hues.
_INK = (0.07, 0.09, 0.15)
_INK_SOFT = (0.36, 0.40, 0.48)
_INK_MUTED = (0.55, 0.58, 0.65)
_GOLD = (0.78, 0.60, 0.22)
_BLUE = (0.16, 0.42, 0.78)
_RED = (0.76, 0.22, 0.26)
_RULE = (0.82, 0.83, 0.86)
_WASH = (0.97, 0.96, 0.93)

_SERIF = "times-roman"
_SERIF_BOLD = "times-bold"
_SERIF_ITALIC = "times-italic"
_MONO = "courier"


def _clean(text: str, limit: int | None = None) -> str:
    """
    Normalise extracted text for display.

    PDF extraction leaves ligatures and broken spacing; a report that quotes
    them verbatim looks broken even though the underlying evidence is sound.
    """
    out = (
        text.replace("ﬁ", "fi").replace("ﬂ", "fl")
        .replace("ﬀ", "ff").replace("ﬃ", "ffi").replace("ﬄ", "ffl")
        .replace("’", "'").replace("‘", "'")
        .replace("“", '"').replace("”", '"')
        .replace("–", "-").replace("—", "-")
    )
    out = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", out)
    out = re.sub(r"\s+", " ", out).strip()
    if limit and len(out) > limit:
        out = out[: limit - 1].rstrip() + "…"
    return out


class _Report:
    """A paginated document with a cursor."""

    def __init__(self, title: str) -> None:
        self.doc = fitz.open()
        self.title = title
        self.page: fitz.Page | None = None
        self.y = 0.0
        self.page_number = 0
        self.new_page(first=True)

    # -- page management ------------------------------------------------

    def new_page(self, first: bool = False) -> None:
        self.page = self.doc.new_page(width=_WIDTH, height=_HEIGHT)
        self.page_number += 1
        self.y = _MARGIN
        if not first:
            self._running_head()

    def _running_head(self) -> None:
        self.page.insert_text(
            (_MARGIN, _MARGIN - 18),
            self.title,
            fontname=_SERIF_ITALIC,
            fontsize=8,
            color=_INK_MUTED,
        )
        self.page.draw_line(
            fitz.Point(_MARGIN, _MARGIN - 12),
            fitz.Point(_WIDTH - _MARGIN, _MARGIN - 12),
            color=_RULE,
            width=0.5,
        )
        self.y = _MARGIN + 6

    def ensure(self, needed: float) -> None:
        """Break to a new page when *needed* points will not fit."""
        if self.y + needed > _BOTTOM:
            self.new_page()

    def number_pages(self) -> None:
        for index, page in enumerate(self.doc, start=1):
            if index == 1:
                continue
            page.insert_text(
                (_WIDTH / 2 - 10, _HEIGHT - 32),
                str(index),
                fontname=_SERIF,
                fontsize=9,
                color=_INK_MUTED,
            )

    # -- drawing --------------------------------------------------------

    def gap(self, points: float) -> None:
        self.y += points

    def heading(self, text: str, size: float = 15.0) -> None:
        self.ensure(size + 26)
        self.page.insert_text(
            (_MARGIN, self.y + size),
            text,
            fontname=_SERIF_BOLD,
            fontsize=size,
            color=_INK,
        )
        self.y += size + 6
        self.page.draw_line(
            fitz.Point(_MARGIN, self.y),
            fitz.Point(_MARGIN + 46, self.y),
            color=_GOLD,
            width=1.6,
        )
        self.y += 12

    def label(self, text: str) -> None:
        self.ensure(18)
        self.page.insert_text(
            (_MARGIN, self.y + 8),
            text.upper(),
            fontname=_SERIF_BOLD,
            fontsize=7.5,
            color=_INK_MUTED,
        )
        self.y += 15

    def paragraph(
        self,
        text: str,
        size: float = 9.5,
        font: str = _SERIF,
        color: tuple = _INK,
        indent: float = 0.0,
        leading: float = 1.35,
    ) -> None:
        """Lay out wrapped text, breaking pages as needed."""
        width = _CONTENT_WIDTH - indent
        line_height = size * leading
        words = text.split()
        if not words:
            return

        line = ""
        for word in words:
            trial = f"{line} {word}".strip()
            if fitz.get_text_length(trial, fontname=font, fontsize=size) <= width:
                line = trial
                continue
            self.ensure(line_height)
            self.page.insert_text(
                (_MARGIN + indent, self.y + size),
                line,
                fontname=font,
                fontsize=size,
                color=color,
            )
            self.y += line_height
            line = word

        if line:
            self.ensure(line_height)
            self.page.insert_text(
                (_MARGIN + indent, self.y + size),
                line,
                fontname=font,
                fontsize=size,
                color=color,
            )
            self.y += line_height

    def quote(self, text: str, citation: str, accent: tuple = _GOLD) -> None:
        """An indented pull quote with a rule, then its citation."""
        start_y = self.y
        start_page = self.page_number
        self.paragraph(f"“{text}”", size=9, font=_SERIF_ITALIC, indent=16)
        # Only rule the quote when it did not straddle a page break.
        if self.page_number == start_page:
            self.page.draw_line(
                fitz.Point(_MARGIN + 6, start_y + 2),
                fitz.Point(_MARGIN + 6, self.y),
                color=accent,
                width=1.8,
            )
        self.paragraph(citation, size=7.5, font=_MONO, color=_INK_MUTED, indent=16)
        self.y += 4

    def key_value(self, rows: list[tuple[str, str]]) -> None:
        for key, value in rows:
            self.ensure(14)
            self.page.insert_text(
                (_MARGIN, self.y + 8),
                key,
                fontname=_SERIF_BOLD,
                fontsize=8.5,
                color=_INK_SOFT,
            )
            self.page.insert_text(
                (_MARGIN + 132, self.y + 8),
                value,
                fontname=_SERIF,
                fontsize=8.5,
                color=_INK,
            )
            self.y += 13

    def meter(self, value: float, label: str, color: tuple = _BLUE) -> None:
        """A labelled proportion bar."""
        self.ensure(18)
        bar_x = _MARGIN + 132
        bar_w = 190.0
        self.page.insert_text(
            (_MARGIN, self.y + 8), label, fontname=_SERIF, fontsize=8.5, color=_INK_SOFT
        )
        self.page.draw_rect(
            fitz.Rect(bar_x, self.y + 2, bar_x + bar_w, self.y + 9),
            color=None, fill=_WASH,
        )
        filled = max(0.0, min(1.0, value)) * bar_w
        if filled > 0:
            self.page.draw_rect(
                fitz.Rect(bar_x, self.y + 2, bar_x + filled, self.y + 9),
                color=None, fill=color,
            )
        self.page.insert_text(
            (bar_x + bar_w + 10, self.y + 8),
            f"{value:.3f}",
            fontname=_MONO, fontsize=8, color=_INK_SOFT,
        )
        self.y += 16

    def save(self, path: Path) -> Path:
        self.number_pages()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(path), garbage=3, deflate=True)
        self.doc.close()
        return path


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _cover(report: _Report, summary: dict, corpus_name: str) -> None:
    page = report.page
    page.draw_rect(fitz.Rect(0, 0, _WIDTH, 132), color=None, fill=(0.05, 0.07, 0.12))
    page.draw_line(fitz.Point(0, 132), fitz.Point(_WIDTH, 132), color=_GOLD, width=2.4)

    page.insert_text(
        (_MARGIN, 62), "Research Paper", fontname=_SERIF_BOLD, fontsize=26,
        color=(1, 1, 1),
    )
    page.insert_text(
        (_MARGIN, 92), "Relationship Analysis", fontname=_SERIF_BOLD, fontsize=26,
        color=(0.88, 0.76, 0.48),
    )
    page.insert_text(
        (_MARGIN, 116),
        datetime.now(timezone.utc).strftime("Generated %d %B %Y at %H:%M UTC"),
        fontname=_MONO, fontsize=8, color=(0.66, 0.70, 0.78),
    )

    report.y = 168

    report.label("Corpus")
    report.paragraph(corpus_name, size=11, font=_SERIF_BOLD)
    report.gap(14)

    report.label("At a glance")
    figures = [
        ("Papers analysed", summary.get("documents", 0)),
        ("Entities extracted", summary.get("entities", 0)),
        ("Bridge concepts", summary.get("bridge_entities", 0)),
        ("Knowledge graph",
         f"{summary.get('kg_nodes', 0)} nodes, {summary.get('kg_edges', 0)} edges"),
        ("Document pairs scored", summary.get("scored_pairs", 0)),
        ("Contradictions", (
            f"{summary.get('contradictions', 0)} "
            f"({summary.get('confirmed_contradictions', 0)} confirmed)"
        )),
        ("Research gaps", summary.get("gaps", 0)),
    ]
    report.key_value([(k, str(v)) for k, v in figures])

    report.gap(16)
    report.label("How this was produced")
    report.paragraph(
        f"Extraction backend: {summary.get('extraction_backend') or 'n/a'}. "
        f"Embeddings: {summary.get('embedding_backend') or 'n/a'}. "
        f"Completed in {summary.get('elapsed_seconds', 0)} seconds.",
        size=9, color=_INK_SOFT,
    )
    report.gap(6)
    report.paragraph(
        "Every finding below carries an evidence trail: the verbatim sentence it "
        "was derived from, with its source document, section and page. Nothing in "
        "this report is generated prose about the papers - the quotations are the "
        "papers' own words.",
        size=9, color=_INK_SOFT,
    )


def _relationships(report: _Report, scores: list[RelationshipScore],
                   titles: dict[str, str], limit: int = 12) -> None:
    report.new_page()
    report.heading("Strongest relationships")
    report.paragraph(
        "Each pair is scored across five dimensions - objective, methodology, "
        "dataset, results and citation overlap - and combined using the "
        "configured weights.",
        size=9, color=_INK_SOFT,
    )
    report.gap(10)

    if not scores:
        report.paragraph("No document pairs were scored.", font=_SERIF_ITALIC,
                         color=_INK_MUTED)
        return

    for score in sorted(scores, key=lambda s: s.composite_score, reverse=True)[:limit]:
        report.ensure(64)
        report.paragraph(
            f"{_clean(titles.get(score.doc_id_a, score.doc_id_a), 60)}  ↔  "
            f"{_clean(titles.get(score.doc_id_b, score.doc_id_b), 60)}",
            size=9.5, font=_SERIF_BOLD,
        )
        report.gap(2)
        report.meter(score.composite_score, "Composite", _BLUE)
        for label, value in (
            ("Objective", score.objective_similarity),
            ("Methodology", score.methodology_similarity),
            ("Dataset", score.dataset_overlap),
            ("Results & metrics", score.results_metrics_similarity),
            ("Citation", score.citation_overlap),
        ):
            report.meter(value, label, _GOLD)
        report.gap(8)


def _contradictions(report: _Report, contradictions: list[Contradiction],
                    titles: dict[str, str]) -> None:
    report.new_page()
    report.heading("Contradictions")

    confirmed = [c for c in contradictions if c.status == ContradictionStatus.CONFIRMED]
    others = [c for c in contradictions if c.status != ContradictionStatus.CONFIRMED]

    report.paragraph(
        "A pair is reported only when both papers state a measured result for the "
        "same metric on the same dataset, under the same evaluation regime, and "
        "the values differ materially. Papers studying different methods rarely "
        "meet that bar, so an empty section is a real result rather than a failure.",
        size=9, color=_INK_SOFT,
    )
    report.gap(12)

    if not contradictions:
        report.paragraph(
            "No contradictions were found in this corpus.",
            font=_SERIF_ITALIC, color=_INK_MUTED,
        )
        return

    for index, item in enumerate(confirmed + others, start=1):
        report.ensure(150)
        status = ("Confirmed" if item.status == ContradictionStatus.CONFIRMED
                  else "Unconfirmed")
        report.label(f"Contradiction {index} · {status} · "
                     f"confidence {item.confidence:.2f}")

        for side, doc_id, claim, accent in (
            ("A", item.doc_id_a, item.claim_a, _BLUE),
            ("B", item.doc_id_b, item.claim_b, _RED),
        ):
            report.paragraph(
                f"{side} — {_clean(titles.get(doc_id, doc_id), 76)}",
                size=8.5, font=_SERIF_BOLD, color=accent,
            )
            report.paragraph(_clean(claim, 420), size=9, indent=10)
            report.gap(4)

        for trail in item.evidence:
            if not trail.sentence_span.strip():
                continue
            report.quote(
                _clean(trail.sentence_span, 340),
                f"[{trail.source_doc_id} · §{trail.section} "
                f"· p.{trail.page_number}]",
            )

        report.key_value([
            ("Shared dataset", "yes" if item.dataset_compatible else "no"),
            ("Comparable metric", "yes" if item.metrics_comparable else "no"),
            ("Methodology similarity", f"{item.methodology_similarity:.3f}"),
        ])
        report.gap(14)


def _gaps(report: _Report, gaps: list[ResearchGap], titles: dict[str, str]) -> None:
    report.new_page()
    report.heading("Research gaps")
    report.paragraph(
        "Ranked by importance: how well evidenced the gap is, how specific it is, "
        "and whether a paper states it outright rather than the analysis inferring "
        "it. Only the strongest are listed.",
        size=9, color=_INK_SOFT,
    )
    report.gap(12)

    if not gaps:
        report.paragraph("No research gaps were identified.", font=_SERIF_ITALIC,
                         color=_INK_MUTED)
        return

    for index, gap in enumerate(gaps, start=1):
        report.ensure(96)
        report.label(f"Gap {index} · importance {gap.novelty_score:.2f}")
        report.paragraph(_clean(gap.description, 520), size=9.5)
        report.gap(4)

        if gap.bridge_entities:
            report.paragraph(
                "Concepts: " + ", ".join(_clean(b, 40) for b in gap.bridge_entities),
                size=8.5, font=_MONO, color=_INK_SOFT,
            )
        if gap.supporting_doc_ids:
            names = [_clean(titles.get(d, d), 54) for d in gap.supporting_doc_ids[:4]]
            more = len(gap.supporting_doc_ids) - len(names)
            report.paragraph(
                "Supporting papers: " + "; ".join(names)
                + (f" (+{more} more)" if more > 0 else ""),
                size=8.5, color=_INK_SOFT,
            )
        report.gap(4)

        for trail in gap.evidence[:2]:
            if trail.sentence_span.strip():
                report.quote(
                    _clean(trail.sentence_span, 300),
                    f"[{trail.source_doc_id} · §{trail.section} "
                    f"· p.{trail.page_number}]",
                )
        report.gap(10)


def _corpus(report: _Report, documents: list[Document]) -> None:
    report.new_page()
    report.heading("Corpus")
    report.paragraph(
        f"{len(documents)} papers, with the category assigned by the classifier "
        "and the sections recovered during segmentation.",
        size=9, color=_INK_SOFT,
    )
    report.gap(12)

    for doc in documents:
        report.ensure(42)
        report.paragraph(_clean(doc.title or doc.id, 88), size=9.5, font=_SERIF_BOLD)
        pages = max([s.page_end for s in doc.segments] or [0])
        report.paragraph(
            f"{doc.category.value} (confidence {doc.category_confidence:.2f}) "
            f"· {len(doc.segments)} sections · {pages} pages "
            f"· {doc.metadata.get('reference_count', 0)} references",
            size=8.5, font=_MONO, color=_INK_SOFT,
        )
        sections = ", ".join(s.section_type for s in doc.segments)
        if sections:
            report.paragraph(sections, size=8, color=_INK_MUTED)
        report.gap(8)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def export_pdf(
    documents: list[Document],
    contradictions: list[Contradiction],
    gaps: list[ResearchGap],
    scores: list[RelationshipScore],
    output_path: str | Path,
    summary: dict | None = None,
    corpus_name: str = "Corpus",
) -> Path:
    """Render the full report and return the path written."""
    summary = summary or {}
    titles = {d.id: (d.title or d.id) for d in documents}

    report = _Report("Research Paper Relationship Analysis")
    _cover(report, summary, corpus_name)
    _relationships(report, scores, titles)
    _contradictions(report, contradictions, titles)
    _gaps(report, gaps, titles)
    _corpus(report, documents)

    return report.save(Path(output_path) / "report.pdf")
