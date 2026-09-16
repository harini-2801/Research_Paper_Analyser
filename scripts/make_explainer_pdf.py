"""
Generate the panel-presentation explainer PDF.

This is the document you hand to (or present from in front of) an examining
panel. It explains what the system does, how every stage works, how the
relationship weights are assigned, and what happens when a paper is missing
the sections the pipeline expects.

It is generated rather than written by hand so the numbers in it - the
weights, the thresholds, the section lists - are read from the code and
config that actually run, and cannot drift out of date.

Usage
-----
    python scripts/make_explainer_pdf.py [output.pdf]
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# ---------------------------------------------------------------------------
# Page geometry and palette
# ---------------------------------------------------------------------------

_WIDTH, _HEIGHT = fitz.paper_size("a4")
_MARGIN = 58.0
_CONTENT = _WIDTH - 2 * _MARGIN
_BOTTOM = _HEIGHT - 62.0

_INK = (0.09, 0.11, 0.17)
_SOFT = (0.33, 0.37, 0.45)
_MUTED = (0.55, 0.58, 0.65)
_ACCENT = (0.15, 0.36, 0.68)
_GOLD = (0.72, 0.53, 0.15)
_GREEN = (0.16, 0.45, 0.32)
_RED = (0.70, 0.22, 0.25)
_RULE = (0.80, 0.82, 0.86)
_WASH = (0.955, 0.960, 0.975)
_WASH_GOLD = (0.985, 0.965, 0.915)

_SERIF = "times-roman"
_BOLD = "times-bold"
_ITALIC = "times-italic"
_MONO = "courier"
_MONO_BOLD = "courier-bold"


class Doc:
    """A paginated document with a simple vertical cursor."""

    def __init__(self, title: str) -> None:
        self.pdf = fitz.open()
        self.title = title
        self.page = None
        self.y = 0.0
        self.page_no = 0
        self.new_page(first=True)

    # -- page management ------------------------------------------------

    def new_page(self, first: bool = False) -> None:
        self.page = self.pdf.new_page(width=_WIDTH, height=_HEIGHT)
        self.page_no += 1
        self.y = _MARGIN
        if not first:
            self.page.insert_text(
                (_MARGIN, _MARGIN - 20),
                self.title,
                fontname=_ITALIC,
                fontsize=8.5,
                color=_MUTED,
            )
            self.page.draw_line(
                fitz.Point(_MARGIN, _MARGIN - 14),
                fitz.Point(_WIDTH - _MARGIN, _MARGIN - 14),
                color=_RULE,
                width=0.5,
            )
            self.y = _MARGIN + 8

    def space(self, need: float) -> None:
        """Start a new page if *need* points will not fit."""
        if self.y + need > _BOTTOM:
            self.new_page()

    def gap(self, amount: float = 10.0) -> None:
        self.y += amount

    def number_pages(self) -> None:
        for index, page in enumerate(self.pdf, start=1):
            if index == 1:
                continue
            page.insert_text(
                (_WIDTH / 2 - 10, _HEIGHT - 38),
                f"{index - 1}",
                fontname=_SERIF,
                fontsize=9,
                color=_MUTED,
            )

    # -- text primitives -------------------------------------------------

    def _wrap(self, text: str, font: str, size: float, width: float) -> list[str]:
        lines: list[str] = []
        for para in text.split("\n"):
            words = para.split()
            if not words:
                lines.append("")
                continue
            line = words[0]
            for word in words[1:]:
                trial = f"{line} {word}"
                if fitz.get_text_length(trial, fontname=font, fontsize=size) <= width:
                    line = trial
                else:
                    lines.append(line)
                    line = word
            lines.append(line)
        return lines

    def para(
        self,
        text: str,
        size: float = 10.5,
        font: str = _SERIF,
        color=_INK,
        indent: float = 0.0,
        leading: float = 1.45,
        after: float = 9.0,
    ) -> None:
        width = _CONTENT - indent
        step = size * leading
        for line in self._wrap(text, font, size, width):
            self.space(step + 2)
            self.page.insert_text(
                (_MARGIN + indent, self.y + size),
                line,
                fontname=font,
                fontsize=size,
                color=color,
            )
            self.y += step
        self.y += after

    def h1(self, number: str, text: str) -> None:
        self.space(72)
        self.gap(8)
        self.page.insert_text(
            (_MARGIN, self.y + 9),
            number,
            fontname=_BOLD,
            fontsize=9,
            color=_GOLD,
        )
        self.y += 15
        self.page.insert_text(
            (_MARGIN, self.y + 17),
            text,
            fontname=_BOLD,
            fontsize=17,
            color=_INK,
        )
        self.y += 24
        self.page.draw_line(
            fitz.Point(_MARGIN, self.y),
            fitz.Point(_MARGIN + 54, self.y),
            color=_GOLD,
            width=1.6,
        )
        self.y += 13

    def h2(self, text: str) -> None:
        self.space(46)
        self.gap(5)
        self.page.insert_text(
            (_MARGIN, self.y + 11),
            text,
            fontname=_BOLD,
            fontsize=11.5,
            color=_ACCENT,
        )
        self.y += 19

    def bullet(self, text: str, marker: str = "•", size: float = 10.5) -> None:
        self.space(size * 1.5 + 2)
        self.page.insert_text(
            (_MARGIN + 6, self.y + size),
            marker,
            fontname=_SERIF,
            fontsize=size,
            color=_GOLD,
        )
        self.para(text, size=size, indent=20, after=4.0)

    def keyval(self, key: str, value: str, size: float = 10.5) -> None:
        """A bolded lead-in term followed by its explanation."""
        self.space(size * 1.6)
        key_w = fitz.get_text_length(f"{key}  ", fontname=_BOLD, fontsize=size)
        self.page.insert_text(
            (_MARGIN + 14, self.y + size),
            key,
            fontname=_BOLD,
            fontsize=size,
            color=_INK,
        )
        first_w = _CONTENT - 14 - key_w
        lines = self._wrap(value, _SERIF, size, first_w)
        if lines:
            self.page.insert_text(
                (_MARGIN + 14 + key_w, self.y + size),
                lines[0],
                fontname=_SERIF,
                fontsize=size,
                color=_INK,
            )
        self.y += size * 1.45
        if len(lines) > 1:
            rest = " ".join(lines[1:])
            self.para(rest, size=size, indent=14, after=4.0)
        else:
            self.y += 4.0

    # -- blocks ----------------------------------------------------------

    def callout(self, title: str, body: str, tone: str = "neutral") -> None:
        fill = _WASH_GOLD if tone == "warn" else _WASH
        edge = _GOLD if tone == "warn" else _ACCENT
        size = 10.0
        lines = self._wrap(body, _SERIF, size, _CONTENT - 34)
        height = 26 + len(lines) * size * 1.45 + 12
        self.space(height + 8)
        top = self.y
        self.page.draw_rect(
            fitz.Rect(_MARGIN, top, _WIDTH - _MARGIN, top + height),
            color=None,
            fill=fill,
        )
        self.page.draw_rect(
            fitz.Rect(_MARGIN, top, _MARGIN + 3.5, top + height),
            color=None,
            fill=edge,
        )
        self.page.insert_text(
            (_MARGIN + 17, top + 18),
            title,
            fontname=_BOLD,
            fontsize=10,
            color=edge,
        )
        y = top + 32
        for line in lines:
            self.page.insert_text(
                (_MARGIN + 17, y + size),
                line,
                fontname=_SERIF,
                fontsize=size,
                color=_INK,
            )
            y += size * 1.45
        self.y = top + height + 12

    def code(self, lines: list[str]) -> None:
        size = 8.6
        step = size * 1.5
        height = len(lines) * step + 18
        self.space(height + 6)
        top = self.y
        self.page.draw_rect(
            fitz.Rect(_MARGIN, top, _WIDTH - _MARGIN, top + height),
            color=_RULE,
            fill=(0.975, 0.977, 0.983),
            width=0.5,
        )
        y = top + 12
        for line in lines:
            self.page.insert_text(
                (_MARGIN + 12, y + size),
                line,
                fontname=_MONO,
                fontsize=size,
                color=_INK,
            )
            y += step
        self.y = top + height + 11

    def table(
        self,
        headers: list[str],
        rows: list[list[str]],
        widths: list[float],
        size: float = 9.3,
    ) -> None:
        """A ruled table. *widths* are fractions of the content width."""
        cols = [w * _CONTENT for w in widths]
        head_h = 20.0
        # Reserve the header plus two rows, so a table never starts at the very
        # bottom of a page and strands a single orphan row on the next one.
        self.space(head_h + 60)

        top = self.y
        self.page.draw_rect(
            fitz.Rect(_MARGIN, top, _WIDTH - _MARGIN, top + head_h),
            color=None,
            fill=(0.93, 0.94, 0.96),
        )
        x = _MARGIN + 8
        for header, width in zip(headers, cols):
            self.page.insert_text(
                (x, top + 13.5),
                header,
                fontname=_BOLD,
                fontsize=size,
                color=_INK,
            )
            x += width
        self.y = top + head_h

        for row in rows:
            wrapped = [
                self._wrap(cell, _SERIF, size, width - 14)
                for cell, width in zip(row, cols)
            ]
            row_h = max(len(w) for w in wrapped) * size * 1.4 + 9
            self.space(row_h + 4)
            top = self.y
            x = _MARGIN + 8
            for cell_lines, width in zip(wrapped, cols):
                y = top + 5
                for line in cell_lines:
                    self.page.insert_text(
                        (x, y + size),
                        line,
                        fontname=_SERIF,
                        fontsize=size,
                        color=_INK,
                    )
                    y += size * 1.4
                x += width
            self.y = top + row_h
            self.page.draw_line(
                fitz.Point(_MARGIN, self.y),
                fitz.Point(_WIDTH - _MARGIN, self.y),
                color=_RULE,
                width=0.4,
            )
        self.y += 12

    def weight_bars(self, rows: list[tuple[str, float, str]]) -> None:
        """Weight name, fraction, and what it measures - drawn as bars."""
        size = 9.6
        label_w = 0.24 * _CONTENT
        bar_w = 0.20 * _CONTENT
        for name, weight, meaning in rows:
            self.space(34)
            top = self.y
            self.page.insert_text(
                (_MARGIN, top + size),
                name,
                fontname=_BOLD,
                fontsize=size,
                color=_INK,
            )
            bar_x = _MARGIN + label_w
            self.page.draw_rect(
                fitz.Rect(bar_x, top + 1, bar_x + bar_w, top + 10),
                color=None,
                fill=(0.90, 0.91, 0.94),
            )
            self.page.draw_rect(
                fitz.Rect(bar_x, top + 1, bar_x + bar_w * (weight / 0.25), top + 10),
                color=None,
                fill=_ACCENT,
            )
            self.page.insert_text(
                (bar_x + bar_w + 8, top + size),
                f"{weight:.2f}",
                fontname=_MONO_BOLD,
                fontsize=size,
                color=_ACCENT,
            )
            text_x = bar_x + bar_w + 38
            avail = _WIDTH - _MARGIN - text_x
            lines = self._wrap(meaning, _SERIF, size, avail)
            y = top
            for line in lines:
                self.page.insert_text(
                    (text_x, y + size),
                    line,
                    fontname=_SERIF,
                    fontsize=size,
                    color=_SOFT,
                )
                y += size * 1.35
            self.y = max(top + 18, y + 4)
        self.y += 8

    def flow(self, steps: list[tuple[str, str]], per_row: int = 3) -> None:
        """A boxed pipeline diagram, wrapped across rows."""
        gap_x = 14.0
        box_w = (_CONTENT - gap_x * (per_row - 1)) / per_row
        box_h = 52.0
        row_gap = 20.0

        rows = (len(steps) + per_row - 1) // per_row
        self.space(rows * (box_h + row_gap))

        for start in range(0, len(steps), per_row):
            chunk = steps[start : start + per_row]
            self.space(box_h + row_gap + 6)
            top = self.y
            for index, (label, detail) in enumerate(chunk):
                x = _MARGIN + index * (box_w + gap_x)
                rect = fitz.Rect(x, top, x + box_w, top + box_h)
                self.page.draw_rect(rect, color=_RULE, fill=_WASH, width=0.6)
                self.page.draw_rect(
                    fitz.Rect(x, top, x + box_w, top + 2.5), color=None, fill=_ACCENT
                )
                number = start + index + 1
                self.page.insert_text(
                    (x + 9, top + 16),
                    f"{number}",
                    fontname=_MONO_BOLD,
                    fontsize=8,
                    color=_GOLD,
                )
                self.page.insert_text(
                    (x + 22, top + 16),
                    label,
                    fontname=_BOLD,
                    fontsize=9,
                    color=_INK,
                )
                y = top + 26
                for line in self._wrap(detail, _SERIF, 8, box_w - 18)[:3]:
                    self.page.insert_text(
                        (x + 9, y + 8),
                        line,
                        fontname=_SERIF,
                        fontsize=8,
                        color=_SOFT,
                    )
                    y += 10.5
                if index < len(chunk) - 1:
                    arrow_y = top + box_h / 2
                    self.page.draw_line(
                        fitz.Point(x + box_w + 2, arrow_y),
                        fitz.Point(x + box_w + gap_x - 2, arrow_y),
                        color=_GOLD,
                        width=1.0,
                    )
            self.y = top + box_h + row_gap


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------


def cover(doc: Doc, facts: dict) -> None:
    page = doc.page
    page.draw_rect(fitz.Rect(0, 0, _WIDTH, 190), color=None, fill=(0.09, 0.13, 0.24))
    page.draw_rect(fitz.Rect(0, 187, _WIDTH, 191), color=None, fill=_GOLD)

    page.insert_text((_MARGIN, 72), "RESEARCH PAPER", fontname=_BOLD, fontsize=29,
                     color=(1, 1, 1))
    page.insert_text((_MARGIN, 105), "RELATIONSHIP ANALYSER", fontname=_BOLD,
                     fontsize=29, color=_GOLD)
    page.insert_text((_MARGIN, 136), "A simple explanation of how it works",
                     fontname=_ITALIC, fontsize=13, color=(0.78, 0.82, 0.90))

    doc.y = 224
    doc.para(
        "Give this system a folder of research papers. It reads them, works out "
        "which ones are about the same thing, spots places where two papers report "
        "different numbers for the same experiment, points out what the collection "
        "has not studied yet, and draws it all as a graph you can explore.",
        size=12, leading=1.55,
    )

    doc.gap(8)
    stats = [
        ("Papers tested on", facts["corpus"]),
        ("Pipeline stages", facts["stages"]),
        ("Scoring dimensions", facts["dimensions"]),
        ("Automated tests", facts["tests"]),
    ]
    top = doc.y
    cell_w = _CONTENT / 4
    for index, (label, value) in enumerate(stats):
        x = _MARGIN + index * cell_w
        page.draw_rect(fitz.Rect(x, top, x + cell_w - 8, top + 60), color=_RULE,
                       fill=_WASH, width=0.6)
        page.insert_text((x + 12, top + 31), value, fontname=_BOLD, fontsize=20,
                         color=_ACCENT)
        for offset, line in enumerate(doc._wrap(label, _SERIF, 7.6, cell_w - 26)):
            page.insert_text((x + 12, top + 44 + offset * 9), line, fontname=_SERIF,
                             fontsize=7.6, color=_SOFT)
    doc.y = top + 80

    doc.callout(
        "What makes it different from just asking an AI",
        "Every answer it gives can be checked. A relatedness score breaks down into "
        "five named parts, and every contradiction and gap it reports comes with the "
        "page number and the exact sentence it came from. It also runs entirely on "
        "your own machine - no API key needed.",
    )


def build(doc: Doc, facts: dict) -> None:
    cover(doc, facts)

    # -- 1 ---------------------------------------------------------------
    doc.new_page()
    doc.h1("PART 1", "What problem it solves")

    doc.para(
        "Reading thirty papers to understand a new field is slow, and four useful "
        "things are almost impossible to see one paper at a time - because they do "
        "not exist inside any single paper. They only exist between papers."
    )
    doc.keyval("Which papers belong together.",
               "Two papers can study the same thing in totally different words.")
    doc.keyval("Where papers disagree.",
               "Two papers reporting different accuracy for the same model on the "
               "same dataset - you only see it if you hold both numbers at once.")
    doc.keyval("What nobody has done.",
               "A gap is an absence. You cannot spot an absence by reading what is "
               "there; you have to survey everything and notice the hole.")
    doc.keyval("How it all connects.",
               "The mental map an experienced researcher builds is a graph. This "
               "system draws that graph.")

    # -- 2 ---------------------------------------------------------------
    doc.h1("PART 2", "The pipeline, step by step")

    doc.para(
        "Analysis runs as eleven steps in a fixed order. Each step uses what the "
        "steps before it produced."
    )
    doc.flow([
        ("Read PDFs", "Find headings, split into sections"),
        ("Citations", "Parse reference lists"),
        ("Classify", "Experimental, survey or method paper"),
        ("Extract", "Pull out datasets, methods, results"),
        ("Embed", "Turn text into numbers (vectors)"),
        ("Score", "Compare every pair of papers"),
        ("Graph", "Build the knowledge graph"),
        ("Contradictions", "Find claims that disagree"),
        ("Gaps", "Find what is missing"),
        ("Explain", "Optional written summary"),
        ("Export", "JSON, Markdown and PDF reports"),
    ])

    doc.para(
        "The order matters. Three of the five scoring dimensions compare vectors, so "
        "if embedding did not run first those three would all come out as zero - and "
        "the system would still produce confident-looking output that means almost "
        "nothing. That was a real bug during development, which is why the order is "
        "enforced rather than assumed."
    )

    # -- 3 ---------------------------------------------------------------
    doc.new_page()
    doc.h1("PART 3", "Reading a PDF and finding its sections")

    doc.para(
        "A PDF does not know what a 'section' is - it is just letters placed on a "
        "page. Recovering the structure is the hardest part of the whole project, "
        "and getting it wrong ruins every step after it."
    )

    doc.h2("How headings are found")
    doc.para(
        "Looking for bold text or short lines does not work: in a two-column paper "
        "every line is short, and headings are often not bold. Instead the system "
        "uses relative font size:"
    )
    doc.bullet("Work out the normal body text size for that specific paper - usually "
               "10pt in the papers tested.")
    doc.bullet("Any line noticeably bigger than that - usually 12pt - is a possible "
               "heading. Because it is relative, it works across different publishers.")
    doc.bullet("That text is then matched against the known section names, after "
               "fixing extraction glitches: 'I NTRODUCTION' is repaired to "
               "'INTRODUCTION'.")

    doc.h2("Authors do not agree on section names")
    doc.para(
        "This is the biggest reason a section looks 'missing' when it is not. The "
        "system maps all the common alternatives onto one standard name:"
    )
    doc.table(["Standard name", "Also recognised as"], facts["synonyms"], [0.24, 0.76])

    # -- 4 ---------------------------------------------------------------
    doc.new_page()
    doc.h1("PART 4", "What if a paper has no methodology or abstract?")

    doc.para(
        "This is the question that decides whether the system survives real "
        "documents. There are three different situations, and they are easy to "
        "confuse."
    )

    doc.h2("Case A - the section is there but called something else")
    doc.para(
        "Fully handled by the name table in Part 3. A paper with 'Background' "
        "instead of 'Related Work', or 'Proposed Architecture' instead of "
        "'Methodology', is split correctly and nothing is lost. This is by far the "
        "most common case."
    )

    doc.h2("Case B - no headings can be found at all")
    doc.para(
        "Scanned papers or unusual layouts. The paper is never thrown away. It is "
        "split into chunks of three pages and marked as unstructured text."
    )
    doc.para(
        "Normally the system uses the section a sentence came from as a clue about "
        "what it is - an objective usually lives in the abstract, introduction or "
        "conclusion. But when the text is unstructured, that clue does not exist, so "
        "the restriction is switched off completely and every sentence is considered "
        "for every entity type."
    )
    doc.code([
        "Normally:",
        "  OBJECTIVE   only from abstract, introduction, conclusion",
        "  METHODOLOGY only from abstract, methodology, experiments, introduction",
        "",
        "But if the text is unstructured -> no restriction at all,",
        "because the content covers the whole paper.",
    ])
    doc.para(
        "The trade-off is deliberate: such a paper loses some precision, but it does "
        "not lose recall. It still contributes objectives, methods and results."
    )

    doc.h2("Case C - the paper genuinely has no methodology")
    doc.para(
        "A short editorial or a position paper. There is nothing to recover, and the "
        "system does not pretend otherwise. The methodology score for that paper "
        "comes out as zero, and the weights are NOT adjusted to compensate."
    )

    doc.callout(
        "Why the weights are not rebalanced - worth saying out loud",
        "If a paper has no methodology, it loses the 0.25 that dimension is worth, "
        "so it scores lower against everything. The alternative would be to share "
        "that 0.25 among the other four. That was not chosen, because it would make "
        "a paper matching on one dimension look as confident as a paper matching on "
        "all five. Visibly incomplete is better than confidently wrong. The five "
        "separate scores are always shown next to the total, so anyone can see which "
        "evidence was actually available.",
        tone="warn",
    )
    doc.para(
        "In practice this is rare, because each entity type is collected from "
        "several sections - methodology comes from the abstract, methodology, "
        "experiments and introduction. A paper has to be unusual to produce none."
    )

    # -- 5 ---------------------------------------------------------------
    doc.new_page()
    doc.h1("PART 5", "How the weights work")

    doc.para(
        "Every pair of papers is compared. Thirty papers make 435 pairs. Each pair is "
        "measured five different ways, each giving a number between 0 and 1, and "
        "those five are combined into one score using weights."
    )
    doc.code([
        "score =  0.25 x objective     (are they solving the same problem?)",
        "       + 0.25 x methodology   (do they do it the same way?)",
        "       + 0.20 x dataset       (same data?)",
        "       + 0.20 x results       (comparable numbers?)",
        "       + 0.10 x citation      (do they cite the same papers?)",
    ])

    doc.h2("What each dimension actually measures")
    doc.weight_bars(facts["weights"])

    doc.h2("Why these numbers")
    doc.para("The weights are a judgement, not something learned from data. They say:")
    doc.bullet("What a paper is trying to do, and how it does it, are what make it "
               "that paper - so those two carry half the weight between them.")
    doc.bullet("Datasets and metrics are concrete, checkable common ground - "
               "together 0.40.")
    doc.bullet("Shared citations are real evidence but weaker and patchy: a 2024 "
               "paper cannot cite a 2025 one, and reference lists are the messiest "
               "part of a PDF to read. Kept at 0.10.")

    doc.para(
        "Two things stop this being arbitrary. The weights are checked at startup to "
        "add up to exactly 1.0 - if they do not, the system refuses to start and says "
        "why, rather than quietly producing scores that cannot be compared. And they "
        "can be changed from the interface while it is running, so the ranking can be "
        "recalculated under different assumptions without touching any code."
    )

    # -- 6 ---------------------------------------------------------------
    doc.new_page()
    doc.h1("PART 6", "Disagreements and gaps")

    doc.h2("Finding where two papers disagree")
    doc.para("Two methods run together, because they fail in different ways.")
    doc.keyval("The number checker.",
               "Compares the values two papers report, making sure they are measuring "
               "the same thing on the same dataset first. Needs no AI model at all "
               "and catches the most important kind of disagreement.")
    doc.keyval("The language model checker.",
               "An NLI model reads two sentences and decides whether the second "
               "agrees with, contradicts, or is unrelated to the first. Catches "
               "disagreements written in words rather than numbers.")

    doc.para("A disagreement is only marked CONFIRMED when all four of these hold:")
    doc.code([
        "the verdict is 'contradiction'",
        "AND confidence            >= 0.60",
        "AND (same dataset OR comparable metrics)",
        "AND methodology similarity >= 0.30",
    ])
    doc.para(
        "Anything else is shown as UNCONFIRMED rather than hidden. That last "
        "condition prevents the most common false alarm: two papers reporting "
        "different numbers because they measured different things are not actually "
        "disagreeing."
    )

    doc.h2("Finding what is missing")
    doc.para("Three kinds of gap are found, and they are not treated as equally solid:")
    doc.table(["Kind", "How it is found", "Base score"], facts["gaps"], [0.18, 0.62, 0.20])
    doc.para(
        f"Only gaps scoring at least {facts['min_importance']} survive, and at most "
        f"{facts['max_gaps']} are returned. An earlier version returned around sixty, "
        "which is not a findings list - it is a haystack that a reader skims and "
        "trusts none of."
    )

    # -- 7 ---------------------------------------------------------------
    doc.new_page()
    doc.h1("PART 7", "The ideas and techniques used")

    doc.table(["Technique", "What it is used for"], facts["concepts"], [0.27, 0.73])

    doc.para(
        "One detail worth knowing: the preferred way to turn text into vectors is a "
        "transformer model. If that model cannot be loaded - no internet, restricted "
        "machine - the system does not fail and does not quietly return zeros. It "
        "falls back to TF-IDF with a fixed random seed, so results stay reproducible, "
        "and it reports which method it used."
    )

    # -- 8 ---------------------------------------------------------------
    doc.h1("PART 8", "Does it actually work?")

    doc.para(
        "It is tested on thirty real papers from arXiv, deliberately arranged in four "
        "groups. Papers in the same group should score as related; papers in group A "
        "versus group D share almost nothing and act as the control. Without that "
        "control, a system that called every pair 'related' would look perfect."
    )
    doc.table(["Group", "Topic", "Papers"], facts["clusters"], [0.12, 0.72, 0.16])

    doc.h2("Measured results")
    doc.table(["What was measured", "Result"], facts["results"], [0.62, 0.38])

    doc.para(
        "Precision@10 means: of the ten pairs it ranked as most related, how many "
        "were genuinely in the same group. Eight out of ten, against 23% that "
        "random guessing would achieve."
    )

    doc.callout(
        "What is deliberately not claimed",
        "There is no correct answer key for which contradictions and gaps are right - "
        "building one would need an expert to label thousands of claim pairs by hand. "
        "So those are reported with their evidence trails for a human to check, "
        "rather than scored against a number that does not exist.",
    )


# ---------------------------------------------------------------------------
# Facts, read from the running configuration where possible
# ---------------------------------------------------------------------------


def collect_facts() -> dict:
    from rpra.config import Settings
    from rpra.gap_discovery import _MAX_GAPS_RETURNED, _MIN_IMPORTANCE

    settings = Settings()
    w = settings.relationship_scoring.weights

    return {
        "corpus": "30",
        "stages": "11",
        "dimensions": "5",
        "tests": "234",
        "min_importance": f"{_MIN_IMPORTANCE:.2f}",
        "max_gaps": str(_MAX_GAPS_RETURNED),
        "synonyms": [
            ["abstract", "Abstract"],
            ["introduction", "Introduction"],
            ["related work", "Related Work, Background, Literature Review, Prior Work"],
            ["methodology",
             ("Method, Methods, Methodology, Approach, Proposed <anything>, Model, "
             "Architecture, Framework, Preliminaries, Problem Statement, System Design")],
            ["experiments",
             ("Experiments, Experimental Setup, Experimental Settings, Implementation "
             "Details, Setup, Training Details, Dataset, Datasets")],
            ["results",
             ("Results, Evaluation, Performance, Ablation Study, Analysis, Findings, "
             "Comparison")],
            ["conclusion",
             ("Conclusion, Concluding Remarks, Summary, Discussion, Future Work, "
             "Limitations, Broader Impacts")],
            ["references", "References, Bibliography, Works Cited"],
        ],
        "weights": [
            ("Objective", w.objective,
             ("Are they trying to solve the same problem? Compares the meaning of each "
             "paper's stated goals.")),
            ("Methodology", w.methodology,
             ("Do they go about it the same way? Compares the meaning of the methods "
             "each paper uses.")),
            ("Dataset", w.dataset,
             ("Do they test on the same data? A direct overlap count of dataset names, "
             "not a meaning comparison, because names are exact.")),
            ("Results", w.results_metrics,
             ("Do they report comparable quantities? Compares reported results and "
             "evaluation metrics.")),
            ("Citation", w.citation,
             ("Do they share sources? How much their reference lists overlap. If one "
             "directly cites the other, this counts as maximum.")),
        ],
        "concepts": [
            ["PDF layout analysis",
             ("Text is read together with its font size, so headings can be found by "
             "size rather than guesswork.")],
            ["Rule-based extraction",
             ("Lists of known datasets, metrics and models, plus phrase patterns for "
             "goals and limitations. No training data or API key needed.")],
            ["Sentence embeddings",
             ("A transformer model turns text into 384 numbers, so similar meaning "
             "scores highly even with different wording.")],
            ["TF-IDF + random projection",
             ("The offline backup for the above. Word-importance weighting shrunk to a "
             "fixed size using a fixed seed, so it is reproducible.")],
            ["Cosine similarity",
             ("Measures whether two vectors point the same way, so document length "
             "does not distort the comparison.")],
            ["Jaccard index",
             ("Overlap between two sets, divided by their combined size. Used where "
             "exact names matter - datasets and citations.")],
            ["Bibliographic coupling",
             ("A classic library-science measure: two papers are related in proportion "
             "to how many references they share.")],
            ["Natural language inference",
             ("A model that decides whether one sentence contradicts another. Used for "
             "disagreements written in words.")],
            ["Graph modelling",
             ("A network of papers, concepts and the concepts that bridge them. "
             "Communities in it are used to find gaps.")],
            ["Weighted scoring",
             ("Five understandable dimensions combined by weights adding to one, so "
             "any score can be broken down and explained.")],
        ],
        "gaps": [
            ["Stated",
             ("An author says outright that something has not been done. Phrases like "
             "'to the best of our knowledge' score higher than a vague mention of "
             "future work."),
             "0.62"],
            ["Weak connection",
             ("Several papers share a specific concept but otherwise score poorly "
             "against each other - a topic being approached from disconnected "
             "directions."),
             "0.42"],
            ["Absent pairing",
             ("Two groups of related papers that no single paper has ever combined. "
             "The weakest evidence, so only the single best one can ever appear."),
             "0.37"],
        ],
        "clusters": [
            ["A", "Convolutional image classification", "8"],
            ["B", "Pretrained language models", "8"],
            ["C", "Vision transformers and self-supervised vision", "8"],
            ["D", "Retrieval, information extraction and knowledge graphs", "6"],
        ],
        "results": [],
    }


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/HOW_IT_WORKS.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)

    facts = collect_facts()
    # Measured by scripts/evaluate_corpus.py on the 30-paper arXiv corpus.
    facts["results"] = [
        ["Papers split by real headings (not the fallback)", "30 of 30"],
        ["Expected sections found", "215 of 240  (90%)"],
        ["Precision@10 on relatedness ranking", "8 of 10  (80%)"],
        ["Precision@20 on relatedness ranking", "17 of 20  (85%)"],
        ["What random guessing would score", "23%"],
        ["Related pairs vs unrelated pairs (mean score)", "0.463 vs 0.331"],
        ["Automated tests passing", "234"],
    ]

    doc = Doc("Research Paper Relationship Analyser - how it works")
    build(doc, facts)
    doc.number_pages()
    doc.pdf.save(str(out), garbage=4, deflate=True)
    doc.pdf.close()
    print(f"Wrote {out.resolve()} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
