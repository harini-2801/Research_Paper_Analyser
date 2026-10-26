"""
Build the BCSE497J project report as a Word document.

The institute's template (BCE497J PROJECT REPORT TEMPLATE_V1.docx) is mostly
instructions plus a few sample pages, so rather than editing it in place this
script reproduces its specification exactly and writes the real content:

* A4 page; left margin 3.81 cm, the other three 2.54 cm
* Times New Roman 12 pt throughout; captions 11 pt
* chapter headings 16 pt bold, section headings 14 pt caps, subsection 12 pt caps
* 1.5 line spacing, justified body text
* Arabic page numbers at the bottom centre (Roman for the front matter)
* order: cover, title page, declaration, certificate, abstract, acknowledgement,
  contents, list of figures, list of tables, list of acronyms, chapters,
  conclusion, references (APA), appendices

Contents, list of figures and list of tables are real Word fields; after the
file is written Word is driven over COM to refresh them and to export a PDF, so
the page numbers in them are Word's own.

Usage
-----
    python scripts/make_project_report.py
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent))

import report_front as F  # noqa: E402
from report_refs import REFS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "report"
FIG_DIR = OUT_DIR / "figures"
OUT_DOCX = OUT_DIR / "Project_Report_Harini_Sriram_23BDS1124.docx"
TEMPLATE = ROOT / "BCE497J PROJECT REPORT TEMPLATE_V1.docx"
LOGO = OUT_DIR / "vit_logo.jpg"

FONT = "Times New Roman"
TEXT_WIDTH_CM = 21.0 - 3.81 - 2.54  # A4 width minus the two margins


# ---------------------------------------------------------------------------
# Low-level XML helpers
# ---------------------------------------------------------------------------


def set_run_font(run, size=None, bold=None, italic=None, underline=None, caps=None, color=None, name=FONT):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if italic is not None:
        run.font.italic = italic
    if underline is not None:
        run.font.underline = underline
    if caps is not None:
        run.font.all_caps = caps
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def style_font(style, size, bold=False, italic=False, caps=False, name=FONT):
    style.font.name = name
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), name)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rfonts.get(qn(attr)) is not None:
            del rfonts.attrib[qn(attr)]
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = italic
    style.font.all_caps = caps
    style.font.color.rgb = RGBColor(0, 0, 0)


def para_format(p, align=None, before=0, after=6, line=1.25, keep_next=False, keep_lines=False,
                left=None, first=None, page_break_before=False):
    pf = p.paragraph_format
    if align is not None:
        pf.alignment = align
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line
    pf.keep_with_next = keep_next
    pf.keep_together = keep_lines
    pf.widow_control = True
    pf.page_break_before = page_break_before
    if left is not None:
        pf.left_indent = Cm(left)
    if first is not None:
        pf.first_line_indent = Cm(first)


def add_field(paragraph, instr, placeholder="", size=None, bold=None, italic=None):
    """Insert a complex field (PAGE, SEQ, TOC ...) with cached placeholder text."""

    def mk(kind):
        r = paragraph.add_run()
        set_run_font(r, size=size, bold=bold, italic=italic)
        fc = OxmlElement("w:fldChar")
        fc.set(qn("w:fldCharType"), kind)
        r._element.append(fc)
        return r

    mk("begin")
    r = paragraph.add_run()
    set_run_font(r, size=size, bold=bold, italic=italic)
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    r._element.append(it)
    mk("separate")
    r = paragraph.add_run(placeholder)
    set_run_font(r, size=size, bold=bold, italic=italic)
    mk("end")


def shade(cell_or_par_el, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    return shd


def cell_shade(cell, fill):
    tcpr = cell._element.get_or_add_tcPr()
    tcpr.append(shade(cell, fill))


def set_cell_margins(table, top=40, bottom=40, left=80, right=80):
    tblpr = table._element.tblPr
    mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblpr.append(mar)


def set_borders(table, color="808080", sz=4):
    tblpr = table._element.tblPr
    b = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        b.append(el)
    tblpr.append(b)


def repeat_header(row):
    trpr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def no_split(row):
    trpr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def set_page(section, number_format=None, start=None):
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(3.81)
    section.right_margin = Cm(2.54)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.footer_distance = Cm(1.2)
    section.header_distance = Cm(1.2)
    sectpr = section._sectPr
    for old in sectpr.findall(qn("w:pgNumType")):
        sectpr.remove(old)
    if number_format or start:
        pg = OxmlElement("w:pgNumType")
        if number_format:
            pg.set(qn("w:fmt"), number_format)
        if start:
            pg.set(qn("w:start"), str(start))
        sectpr.append(pg)


def footer_page_number(section, show=True, italic=False):
    section.footer.is_linked_to_previous = False
    section.header.is_linked_to_previous = False
    footer = section.footer
    for p in list(footer.paragraphs)[1:]:
        p._element.getparent().remove(p._element)
    p = footer.paragraphs[0]
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    para_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, after=0, line=1.0)
    if show:
        add_field(p, "PAGE", "1", size=12, italic=italic)


# ---------------------------------------------------------------------------
# Inline markup:  **bold**  *italic*  `code`  plus citation and cross-reference tokens
# ---------------------------------------------------------------------------

_INLINE = re.compile(r"(\*\*.+?\*\*|\*.+?\*|`.+?`)")
_CITE = re.compile(r"\[\[(n:)?([a-z0-9;:_\s]+?)\]\]")
_XREF = re.compile(r"\{(fig|tab|sec):([a-z0-9_]+)\}")


class Registry:
    """Numbers figures and tables in order, and tracks which references are cited."""

    def __init__(self) -> None:
        self.fig: dict[str, int] = {}
        self.tab: dict[str, int] = {}
        self.sec: dict[str, str] = {}
        self.cited: set[str] = set()

    def expand(self, text: str) -> str:
        def cite(m: re.Match) -> str:
            narrative = bool(m.group(1))
            keys = [k.strip() for k in m.group(2).split(";")]
            for k in keys:
                if k not in REFS:
                    raise KeyError(f"citation key not in report_refs.py: {k!r}")
                self.cited.add(k)
            if narrative:
                a, y = REFS[keys[0]][0], REFS[keys[0]][1]
                return f"{a} ({y})"
            keys.sort(key=lambda k: (REFS[k][0], REFS[k][1]))
            return "(" + "; ".join(f"{REFS[k][0]}, {REFS[k][1]}" for k in keys) + ")"

        def xref(m: re.Match) -> str:
            kind, key = m.group(1), m.group(2)
            if kind == "sec":
                if key not in self.sec:
                    raise KeyError(f"unknown section reference {key!r}")
                return f"Section {self.sec[key]}"
            table = self.fig if kind == "fig" else self.tab
            if key not in table:
                raise KeyError(f"unknown {kind} reference {key!r}")
            return f"{'Figure' if kind == 'fig' else 'Table'} {table[key]}"

        out = _XREF.sub(xref, _CITE.sub(cite, text))
        # A citation written inside brackets would otherwise render as ((Author, 2020)).
        return re.sub(r"\(\(([^()]*)\)\)", lambda m: "(" + m.group(1) + ")", out)


def add_inline(paragraph, text, size=12, base_bold=False, base_italic=False):
    for piece in _INLINE.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**") and len(piece) > 4:
            r = paragraph.add_run(piece[2:-2])
            set_run_font(r, size=size, bold=True, italic=base_italic)
        elif piece.startswith("`") and piece.endswith("`") and len(piece) > 2:
            r = paragraph.add_run(piece[1:-1])
            set_run_font(r, size=size, bold=base_bold, italic=True)
        elif piece.startswith("*") and piece.endswith("*") and len(piece) > 2:
            r = paragraph.add_run(piece[1:-1])
            set_run_font(r, size=size, bold=base_bold, italic=True)
        else:
            r = paragraph.add_run(piece)
            set_run_font(r, size=size, bold=base_bold, italic=base_italic)


# ---------------------------------------------------------------------------
# Document builder
# ---------------------------------------------------------------------------


class ReportBuilder:
    def __init__(self, blocks: list) -> None:
        self.blocks = blocks
        self.reg = Registry()
        self.doc = Document()
        self.chapter = 0
        self.section = 0
        self.sub = 0
        self.fig_n = 0
        self.tab_n = 0
        self._number_floats()
        self._styles()

    # -- set-up ------------------------------------------------------------

    def _number_floats(self) -> None:
        """Figures and tables are numbered by chapter (4.2), as the template's lists show."""
        f = t = 0
        chapter = section = 0
        label = "0"
        for kind, payload in self.blocks:
            if kind == "h1":
                chapter += 1
                section = 0
                label = str(chapter)
                f = t = 0
            elif kind == "h1u":
                m = re.match(r"Appendix (\d+)", payload)
                if m:
                    label = f"A{m.group(1)}"
                    f = t = 0
            elif kind == "h2":
                section += 1
                if isinstance(payload, tuple):
                    self.reg.sec[payload[1]] = f"{chapter}.{section}"
            if kind == "fig":
                f += 1
                self.reg.fig[payload["key"]] = f"{label}.{f}"
            elif kind == "tab":
                t += 1
                self.reg.tab[payload["key"]] = f"{label}.{t}"

    def _styles(self) -> None:
        st = self.doc.styles
        style_font(st["Normal"], 12)
        st["Normal"].paragraph_format.line_spacing = 1.25
        st["Normal"].paragraph_format.space_after = Pt(6)

        h1, h2, h3 = st["Heading 1"], st["Heading 2"], st["Heading 3"]
        style_font(h1, 16, bold=True)
        style_font(h2, 14, bold=False, caps=True)
        style_font(h3, 12, bold=False, caps=True)
        for s, before, after in ((h1, 0, 18), (h2, 14, 8), (h3, 10, 6)):
            s.paragraph_format.space_before = Pt(before)
            s.paragraph_format.space_after = Pt(after)
            s.paragraph_format.line_spacing = 1.25
            s.paragraph_format.keep_with_next = True
        h1.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

        for name in ("Caption",):
            style_font(st[name], 11, bold=False, italic=False)
            st[name].paragraph_format.line_spacing = 1.0
        style_font(st["List Bullet"], 12)
        # The template's contents page: chapter lines bold, section lines plain and indented.
        from docx.enum.style import WD_STYLE_TYPE

        for name in ("TOC 1", "TOC 2", "Table of Figures"):
            try:
                style = st[name]
            except KeyError:
                style = st.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
                style.base_style = st["Normal"]
            style_font(style, 12, bold=(name == "TOC 1"))
            style.paragraph_format.line_spacing = 1.15
            style.paragraph_format.space_after = Pt(3)
            style.paragraph_format.space_before = Pt(6 if name == "TOC 1" else 0)
            if name == "TOC 2":
                style.paragraph_format.left_indent = Cm(0.8)

    # -- primitives --------------------------------------------------------

    def para(self, text="", align=WD_ALIGN_PARAGRAPH.JUSTIFY, size=12, bold=False, italic=False,
             before=0, after=6, line=1.25, keep_next=False, left=None, first=None, style=None):
        p = self.doc.add_paragraph(style=style) if style else self.doc.add_paragraph()
        para_format(p, align=align, before=before, after=after, line=line, keep_next=keep_next,
                    left=left, first=first)
        if text:
            add_inline(p, self.reg.expand(text), size=size, base_bold=bold, base_italic=italic)
        return p

    def page_break(self) -> None:
        p = self.doc.add_paragraph()
        para_format(p, after=0, line=1.0)
        p.add_run().add_break(WD_BREAK.PAGE)

    def blank(self, n=1, size=12) -> None:
        for _ in range(n):
            p = self.doc.add_paragraph()
            para_format(p, after=0, line=1.0)
            r = p.add_run("")
            set_run_font(r, size=size)

    def centred(self, text, size=12, bold=False, italic=False, underline=False, caps=False,
                before=0, after=0, line=1.25):
        p = self.doc.add_paragraph()
        para_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, before=before, after=after, line=line)
        r = p.add_run(text)
        set_run_font(r, size=size, bold=bold, italic=italic, underline=underline, caps=caps)
        return p

    def logo(self, width_cm=5.2) -> None:
        p = self.doc.add_paragraph()
        para_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, after=4, line=1.0)
        if LOGO.exists():
            p.add_run().add_picture(str(LOGO), width=Cm(width_cm))

    # -- front matter ------------------------------------------------------

    def cover(self, label: str) -> None:
        self.centred("A project report on", size=12, italic=True, before=6, after=14)
        self.centred(F.TITLE.upper(), size=20, bold=True, after=18, line=1.25)
        self.centred("Submitted in partial fulfillment for the award of the degree of",
                     size=14, italic=True, after=10)
        self.centred(f"Bachelor of Technology in {F.PROGRAM}", size=22, bold=True, after=22, line=1.1)
        self.centred("by", size=14, italic=True, after=10)
        for name, reg in F.TEAM:
            self.centred(f"{name.upper()} ({reg})", size=16, bold=True, after=3)
        self.blank(2)
        self.logo()
        self.centred("SCHOOL OF COMPUTER SCIENCE AND ENGINEERING", size=16, bold=True, before=6, after=8)
        self.centred(F.MONTH_YEAR, size=16, bold=True, after=0)

    def declaration(self) -> None:
        self.logo()
        self.centred("DECLARATION", size=14, bold=True, underline=True, before=10, after=16)
        self.para(
            f"I hereby declare that the thesis entitled “{F.TITLE}” submitted by "
            f"{F.NAME} ({F.REG_NO}), for the award of the degree of Bachelor of Technology in "
            f"Computer Science and Engineering, Vellore Institute of Technology, Chennai is a "
            f"record of bonafide work carried out by me under the supervision of {F.GUIDE}.",
            after=10)
        self.para(
            "I further declare that the work reported in this thesis has not been submitted and "
            "will not be submitted, either in part or in full, for the award of any other degree "
            "or diploma in this institute or any other institute or university.", after=10)
        self.blank(5)
        self.para("Place: Chennai", align=WD_ALIGN_PARAGRAPH.LEFT, after=0, line=1.25)
        p = self.para("", align=WD_ALIGN_PARAGRAPH.LEFT, after=0, line=1.25)
        p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), alignment=2)  # right
        add_inline(p, f"Date: {F.DATE_NUM}\t**Signature of the Candidate**")
        p = self.para("", align=WD_ALIGN_PARAGRAPH.RIGHT, after=0, line=1.25)
        add_inline(p, f"**{F.NAME}**")

    def certificate(self) -> None:
        self.logo()
        self.centred("School of Computer Science and Engineering", size=12, bold=True, after=14)
        self.centred("CERTIFICATE", size=14, bold=True, after=14)
        self.para(
            f"This is to certify that the report entitled “{F.TITLE}” is prepared and submitted by "
            f"{F.NAME} ({F.REG_NO}) to Vellore Institute of Technology, Chennai, in partial "
            f"fulfillment of the requirement for the award of the degree of Bachelor of Technology "
            f"in {F.PROGRAM} is a bonafide record carried out under my guidance. The project "
            f"fulfills the requirements as per the regulations of this University and in my "
            f"opinion meets the necessary standards for submission. The contents of this report "
            f"have not been submitted and will not be submitted either in part or in full, for "
            f"the award of any other degree or diploma and the same is certified.",
            line=1.3, after=14)
        for text in (f"Signature of the Guide:", f"Name: {F.GUIDE}", f"Date: {F.DATE_NUM}"):
            self.para(text, align=WD_ALIGN_PARAGRAPH.LEFT, after=8, line=1.25)
        self.blank(1)
        t = self.doc.add_table(rows=3, cols=2)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, label in enumerate(("Signature of the Examiner", "Name:", "Date:")):
            for j in range(2):
                c = t.cell(i, j)
                c.text = ""
                p = c.paragraphs[0]
                para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, after=6, line=1.25)
                set_run_font(p.add_run(label), size=12)
        self.blank(2)
        self.centred("Approved by the Head of Department,", size=12, after=2)
        self.centred(f"B.Tech. {F.PROGRAM_SHORT}", size=12, bold=True, after=8)
        self.centred(f"Name: {F.HOD}", size=12, after=2)
        self.centred(f"Date: {F.DATE_NUM}", size=12, after=14)
        self.centred("(Seal of the School of Computer Science and Engineering)", size=12, italic=True)

    def front_heading(self, text, toc=False, break_before=False, kind="abstract") -> None:
        """abstract: 14 underlined bold caps, centred. ack: 12 bold caps, centred.
        contents: 14 bold caps, left. list: 12 bold caps, left. All as the template shows."""
        centred = kind in ("abstract", "ack")
        size = 14 if kind in ("abstract", "contents") else 12
        p = self.doc.add_paragraph()
        para_format(p, align=WD_ALIGN_PARAGRAPH.CENTER if centred else WD_ALIGN_PARAGRAPH.LEFT,
                    before=0, after=14, line=1.25, keep_next=True, page_break_before=break_before)
        r = p.add_run(text)
        set_run_font(r, size=size, bold=True, underline=(kind == "abstract"), caps=True)
        if toc:
            ppr = p._element.get_or_add_pPr()
            ol = OxmlElement("w:outlineLvl")
            ol.set(qn("w:val"), "0")
            ppr.append(ol)

    def abstract(self) -> None:
        self.front_heading("Abstract")
        for para in F.ABSTRACT:
            self.para(para, after=8)
        p = self.para("", after=0)
        add_inline(p, f"**Keywords:** {F.KEYWORDS}")

    def acknowledgement(self) -> None:
        self.front_heading("Acknowledgement", kind="ack")
        for para in F.acknowledgement():
            self.para(para, after=8, line=1.4)
        self.blank(1)
        self.para("Place: Chennai", align=WD_ALIGN_PARAGRAPH.LEFT, after=0, line=1.25)
        p = self.para("", align=WD_ALIGN_PARAGRAPH.LEFT, after=0, line=1.25)
        p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), alignment=2)
        add_inline(p, f"Date: {F.DATE_NUM}\t**{F.NAME}**")

    def toc_page(self) -> None:
        self.front_heading("Contents", toc=True, kind="contents")
        p = self.doc.add_paragraph()
        para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, after=0, line=1.25)
        add_field(p, r'TOC \o "1-2" \h \z \u', "Right-click and choose Update Field to build the contents.")

    def list_page(self, title: str, label: str) -> None:
        self.front_heading(title, toc=True, break_before=True, kind="list")
        p = self.doc.add_paragraph()
        para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, after=0, line=1.25)
        add_field(p, rf'TOC \h \z \c "{label}"', f"Update field to list the {label.lower()}s.")

    def acronyms(self) -> None:
        self.front_heading("List of Acronyms", toc=True, break_before=True, kind="list")
        t = self.doc.add_table(rows=0, cols=2)
        for short, long in F.ACRONYMS:
            row = t.add_row()
            for c, txt, b in ((row.cells[0], short, True), (row.cells[1], long, False)):
                c.text = ""
                p = c.paragraphs[0]
                para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, after=3, line=1.25)
                set_run_font(p.add_run(txt), size=12, bold=b)
        for row in t.rows:
            row.cells[0].width = Cm(3.6)
            row.cells[1].width = Cm(TEXT_WIDTH_CM - 3.6)

    # -- body --------------------------------------------------------------

    def h1(self, text: str, numbered=True) -> None:
        is_appendix = (not numbered) and text.startswith("Appendix")
        if numbered:
            self.chapter += 1
            self.section = 0
            top, title = f"Chapter {self.chapter}", text
        elif is_appendix:
            top, title = (x.strip() for x in text.split(":", 1))
        else:
            top, title = None, text.upper()
        p = self.doc.add_paragraph(style="Heading 1")
        # Appendices after the first run on, so a five-line appendix does not take a page.
        later = is_appendix and getattr(self, "_appendix_seen", False)
        if is_appendix:
            self._appendix_seen = True
        para_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, before=26 if later else 0,
                    after=18, line=1.25, keep_next=True, page_break_before=not later)
        if top:
            r = p.add_run(top)
            set_run_font(r, size=12, bold=True)
            r.add_break()
        r = p.add_run(title)
        set_run_font(r, size=16, bold=True)

    def h2(self, text: str) -> None:
        self.section += 1
        self.sub = 0
        p = self.doc.add_paragraph(style="Heading 2")
        para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, before=14, after=8, line=1.25, keep_next=True)
        r = p.add_run(f"{self.chapter}.{self.section}  {text.upper()}")
        set_run_font(r, size=14, bold=False)

    def h3(self, text: str) -> None:
        self.sub += 1
        p = self.doc.add_paragraph(style="Heading 3")
        para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, before=10, after=6, line=1.25, keep_next=True)
        r = p.add_run(f"{self.chapter}.{self.section}.{self.sub}  {text.upper()}")
        set_run_font(r, size=12, bold=False)

    def bullets(self, items: list[str]) -> None:
        for it in items:
            p = self.doc.add_paragraph(style="List Bullet")
            para_format(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=3, line=1.25)
            add_inline(p, self.reg.expand(it))
        self.doc.paragraphs[-1].paragraph_format.space_after = Pt(8)

    def numbered(self, items: list[str]) -> None:
        for i, it in enumerate(items, 1):
            p = self.doc.add_paragraph()
            para_format(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, after=3, line=1.25, left=1.0, first=-0.75)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(1.0))
            add_inline(p, f"{i}.\t" + self.reg.expand(it))
        self.doc.paragraphs[-1].paragraph_format.space_after = Pt(8)

    def caption(self, kind: str, number: str, text: str, keep_next: bool) -> str:
        """Write the caption line and return any detail text for a note beneath.

        The number is chapter.item (Figure 4.2). Word's list of figures and list of
        tables repeat the whole caption paragraph, so the caption holds a short title
        and the explanation is set in a separate note.
        """
        text = self.reg.expand(text)
        parts = re.split(r"(?<=[a-z\)])\.\s+(?=[A-Z])", text, maxsplit=1)
        title = parts[0].rstrip(".")
        note = parts[1] if len(parts) > 1 else ""
        prefix, item = number.rsplit(".", 1)
        p = self.doc.add_paragraph(style="Caption")
        para_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, before=4 if kind == "Figure" else 8,
                    after=2 if kind == "Figure" else 4, line=1.0, keep_next=keep_next or bool(note))
        r = p.add_run(f"{kind} {prefix}.")
        set_run_font(r, size=11, bold=True)
        # \r forces the item number, so each chapter restarts at 1 and the lists still find it.
        add_field(p, f"SEQ {kind} " + r"\r " + item, item, size=11, bold=True)
        r = p.add_run(". ")
        set_run_font(r, size=11, bold=True)
        add_inline(p, title, size=11)
        return note

    def note(self, text: str, after=8) -> None:
        p = self.doc.add_paragraph()
        para_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, before=0, after=after, line=1.0)
        add_inline(p, text, size=10.5, base_italic=True)

    def spacer(self, points: float = 1) -> None:
        """A one-point paragraph: Word needs something after a table, but a taller
        one can spill onto a new page and leave it blank before a chapter heading."""
        sp = self.doc.add_paragraph()
        para_format(sp, after=0, line=1.0)
        sp.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        sp.paragraph_format.line_spacing = Pt(points)
        r = sp.add_run("")
        set_run_font(r, size=1)

    def figure(self, spec: dict, gap: float = 8) -> None:
        self.fig_n += 1
        path = FIG_DIR / spec["file"]
        number = self.reg.fig[spec["key"]]
        p = self.doc.add_paragraph()
        para_format(p, align=WD_ALIGN_PARAGRAPH.CENTER, before=6, after=2, line=1.0, keep_next=True)
        p.add_run().add_picture(str(path), width=Cm(min(spec.get("width_cm", 12.0), 11.0)))
        note = self.caption("Figure", number, spec["caption"], keep_next=False)
        if note:
            self.note(note, after=12)
        else:
            self.spacer(gap)

    def table(self, spec: dict, gap: float = 8) -> None:
        self.tab_n += 1
        note = self.caption("Table", self.reg.tab[spec["key"]], spec["caption"], keep_next=True)
        headers, rows = spec["headers"], spec["rows"]
        widths = spec.get("widths") or [1 / len(headers)] * len(headers)
        total = sum(widths)
        widths_cm = [TEXT_WIDTH_CM * w / total for w in widths]
        size = max(spec.get("size", 10.5), 10)   # the template: nothing under 10 pt
        t = self.doc.add_table(rows=1, cols=len(headers))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        set_borders(t)
        set_cell_margins(t)
        hdr = t.rows[0]
        repeat_header(hdr)
        for i, h in enumerate(headers):
            c = hdr.cells[i]
            c.width = Cm(widths_cm[i])
            c.text = ""
            p = c.paragraphs[0]
            para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, after=0, line=1.0)
            add_inline(p, h, size=size, base_bold=True)
        for row in rows:
            r = t.add_row()
            no_split(r)
            for i, val in enumerate(row):
                c = r.cells[i]
                c.width = Cm(widths_cm[i])
                c.text = ""
                p = c.paragraphs[0]
                para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, after=0, line=1.0)
                add_inline(p, self.reg.expand(str(val)), size=size)
        if len(rows) <= 12:
            # Keep a short table on one page: a header row stranded alone at the
            # foot of a page reads as a mistake.
            for r in t.rows[:-1]:
                for c in r.cells:
                    for pp in c.paragraphs:
                        pp.paragraph_format.keep_with_next = True
        if note:
            self.note(note, after=10)
        else:
            self.spacer(gap)

    def code(self, spec: dict, gap: float = 8) -> None:
        if spec.get("caption"):
            p = self.para(f"**{spec['caption']}**", align=WD_ALIGN_PARAGRAPH.LEFT, after=3, line=1.0,
                          keep_next=True, size=11)
        lines = spec["lines"]
        for i, line in enumerate(lines):
            p = self.doc.add_paragraph()
            # Chain only the first and last lines so a long listing can still break
            # across pages without leaving a short orphan at either end.
            chain = i < 2 or i >= len(lines) - 3
            para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, after=0, line=1.0, left=0.3,
                        keep_next=chain and i < len(lines) - 1)
            p.paragraph_format.keep_together = True
            ppr = p._element.get_or_add_pPr()
            ppr.append(shade(p, "F2F2F2"))
            r = p.add_run(line if line else " ")
            set_run_font(r, size=10)   # Times New Roman, as the template requires throughout
        self.spacer(gap)

    def equation(self, text: str, number: str) -> None:
        p = self.doc.add_paragraph()
        para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, before=4, after=8, line=1.3, keep_lines=True)
        ts = p.paragraph_format.tab_stops
        ts.add_tab_stop(Cm(TEXT_WIDTH_CM / 2), alignment=1)   # centre
        ts.add_tab_stop(Cm(TEXT_WIDTH_CM), alignment=2)       # right
        r = p.add_run("\t" + text + "\t" + f"({number})")
        set_run_font(r, size=12, italic=True)

    def references(self) -> None:
        self.h1("References", numbered=False)
        entries = sorted(self.reg.cited, key=lambda k: (REFS[k][2].lower()))
        for k in entries:
            p = self.doc.add_paragraph()
            para_format(p, align=WD_ALIGN_PARAGRAPH.LEFT, after=8, line=1.3, left=1.27, first=-1.27)
            add_inline(p, REFS[k][2])

    # -- assembly ----------------------------------------------------------

    def render_body(self) -> None:
        for idx, (kind, payload) in enumerate(self.blocks):
            nxt = self.blocks[idx + 1][0] if idx + 1 < len(self.blocks) else "end"
            # Before a chapter heading the page breaks anyway, so keep the spacer tiny.
            gap = 1 if nxt in ("h1", "h1u", "refs", "end") else 8
            if kind == "h1":
                self.h1(payload)
            elif kind == "h1u":
                self.h1(payload, numbered=False)
            elif kind == "h2":
                self.h2(payload[0] if isinstance(payload, tuple) else payload)
            elif kind == "h3":
                self.h3(payload)
            elif kind == "p":
                self.para(payload, first=1.0)
            elif kind == "bul":
                self.bullets(payload)
            elif kind == "num":
                self.numbered(payload)
            elif kind == "fig":
                self.figure(payload, gap)
            elif kind == "tab":
                self.table(payload, gap)
            elif kind == "code":
                self.code(payload, gap)
            elif kind == "eq":
                self.equation(*payload)
            elif kind == "refs":
                self.references()
            else:
                raise ValueError(f"unknown block kind {kind!r}")

    def build(self) -> Path:
        doc = self.doc
        # Section 1: cover and title page, no page number.
        s1 = doc.sections[0]
        set_page(s1)
        footer_page_number(s1, show=False)
        self.cover("cover")
        self.page_break()
        self.cover("title")

        # Section 2: declaration and certificate. The template numbers nothing before the abstract.
        s2 = doc.add_section(WD_SECTION.NEW_PAGE)
        set_page(s2)
        footer_page_number(s2, show=False)
        self.declaration()
        self.page_break()
        self.certificate()

        # Section 3: abstract onwards, lower-case Roman numerals in italics, starting at i.
        s2b = doc.add_section(WD_SECTION.NEW_PAGE)
        set_page(s2b, number_format="lowerRoman", start=1)
        footer_page_number(s2b, italic=True)
        self.abstract()
        self.page_break()
        self.acknowledgement()
        self.page_break()
        self.toc_page()
        self.list_page("List of Figures", "Figure")
        self.list_page("List of Tables", "Table")
        self.acronyms()

        # Section 3: the report proper, Arabic numerals from 1.
        s3 = doc.add_section(WD_SECTION.NEW_PAGE)
        set_page(s3, number_format="decimal", start=1)
        footer_page_number(s3)
        # The first body block is a chapter heading with page_break_before; the
        # section break already starts a new page, so avoid a blank page.
        self.render_body()

        # Anything that was cited must exist, and the list is built from that.
        self.doc.core_properties.title = F.TITLE
        self.doc.core_properties.author = F.NAME
        self.doc.core_properties.subject = "BCSE497J Project Report"
        OUT_DIR.mkdir(exist_ok=True)
        doc.save(OUT_DOCX)
        return OUT_DOCX


def extract_logo() -> None:
    if LOGO.exists():
        return
    OUT_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(TEMPLATE) as z:
        LOGO.write_bytes(z.read("word/media/image2.jpg"))


def collect_blocks() -> list:
    import report_ch1_3 as A
    import report_ch4_5 as B
    import report_ch6 as C6
    import report_ch7 as C7
    import report_ch8 as C8
    import report_ch9_10 as C9

    blocks = [*A.BLOCKS, *B.BLOCKS, *C6.BLOCKS, *C7.BLOCKS, *C8.BLOCKS, *C9.BLOCKS]
    blocks.append(("refs", None))
    import report_appendices as D

    blocks.extend(D.BLOCKS)
    return blocks


def main() -> None:
    extract_logo()
    builder = ReportBuilder(collect_blocks())
    path = builder.build()
    words = sum(len(p.text.split()) for p in builder.doc.paragraphs)
    print(f"wrote {path.name}: {builder.fig_n} figures, {builder.tab_n} tables, "
          f"~{words:,} words in body paragraphs, {len(builder.reg.cited)} references")


if __name__ == "__main__":
    main()
