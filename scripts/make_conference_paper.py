"""
Render the conference paper into the two publisher templates.

Rather than building a document from scratch, this opens each supplied template,
replaces the body, and writes it back. Everything that makes a template a
template - the named paragraph styles, the page size and margins, the fonts, the
section setup - stays exactly as the publisher shipped it, and the paper inherits
it by referencing style IDs instead of restating formatting.

The two houses disagree about almost everything. AIP leaves headings unnumbered,
centres them in capitals, and puts table captions below the table; Springer
numbers headings to two levels and puts captions above. Those differences live in
the two Renderer subclasses; the prose lives in paper_content.py and is shared.

Usage
-----
    python scripts/make_conference_paper.py [output_dir]
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paper_content as C  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AIP_TEMPLATE = ROOT / "AIPCP Article Template_Sept1_2023.docx"
LNCS_TEMPLATE = ROOT / "splnproc1703.docm"


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------


def runs(text: str, bold_prefix: str | None = None) -> str:
    """
    One or two runs of text, optionally with a bold lead-in.

    Both templates want their abstract to open with a bold "Abstract." before the
    body resumes in regular weight, which needs two runs rather than one.
    """
    out = ""
    if bold_prefix:
        out += (
            "<w:r><w:rPr><w:b/></w:rPr>"
            f'<w:t xml:space="preserve">{escape(bold_prefix)}</w:t></w:r>'
        )
    if text:
        out += f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
    return out


def rich_para(style: str, segments: list[tuple[str, str]]) -> str:
    """
    A paragraph built from (text, kind) segments, where kind is "" or "super".

    AIP marks an author's affiliation and e-mail with superscript digits and
    letters, which cannot be expressed as a single run.
    """
    body = ""
    for text, kind in segments:
        rpr = "<w:vertAlign w:val=\"superscript\"/>" if kind == "super" else ""
        rpr = f"<w:rPr>{rpr}</w:rPr>" if rpr else ""
        body += f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{body}</w:p>'


def para(style: str, text: str, bold_prefix: str | None = None) -> str:
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
        f"{runs(text, bold_prefix)}</w:p>"
    )


def png_size(path: Path) -> tuple[int, int]:
    """Pixel dimensions straight out of the PNG IHDR chunk."""
    raw = path.read_bytes()
    return int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")


EMU_PER_INCH = 914400


def drawing_xml(rel_id: str, width_emu: int, height_emu: int, name: str) -> str:
    """An inline image run. Word needs the full DrawingML scaffold for this."""
    return (
        "<w:r><w:drawing>"
        f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{width_emu}" cy="{height_emu}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{abs(hash(name)) % 90000 + 1000}" name="{escape(name)}"/>'
        "<wp:cNvGraphicFramePr>"
        '<a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/>'
        "</wp:cNvGraphicFramePr>"
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="0" name="{escape(name)}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        "<pic:spPr><a:xfrm><a:off x=\"0\" y=\"0\"/>"
        f'<a:ext cx="{width_emu}" cy="{height_emu}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        "</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>"
    )


def table_xml(spec: dict, style: str, total_dxa: int = 9000) -> str:
    """A ruled table using the template's own table style."""
    widths = [int(w * total_dxa) for w in spec["widths"]]
    # Trailing columns absorb any rounding drift so the grid still sums correctly.
    widths[-1] += total_dxa - sum(widths)

    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    rows = ""

    header_cells = ""
    for text, width in zip(spec["headers"], widths):
        header_cells += (
            f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:pPr><w:jc w:val="left"/></w:pPr>'
            f"<w:r><w:rPr><w:b/><w:sz w:val=\"18\"/></w:rPr>"
            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p></w:tc>'
        )
    rows += f"<w:tr><w:trPr><w:tblHeader/></w:trPr>{header_cells}</w:tr>"

    for row in spec["rows"]:
        cells = ""
        for text, width in zip(row, widths):
            cells += (
                f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
                f'<w:p><w:pPr><w:jc w:val="left"/></w:pPr>'
                f'<w:r><w:rPr><w:sz w:val="18"/></w:rPr>'
                f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p></w:tc>'
            )
        rows += f"<w:tr>{cells}</w:tr>"

    return (
        "<w:tbl><w:tblPr>"
        f'<w:tblStyle w:val="{style}"/>'
        f'<w:tblW w:w="{total_dxa}" w:type="dxa"/>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="6" w:color="000000"/>'
        '<w:bottom w:val="single" w:sz="6" w:color="000000"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="808080"/>'
        "</w:tblBorders>"
        "</w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{rows}</w:tbl>"
        # Word needs a paragraph after a table or the next block can merge into it.
        "<w:p/>"
    )


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


class Renderer:
    """Shared body-building logic; subclasses supply the house style."""

    styles: dict[str, str] = {}
    table_style = "TableGrid"
    number_headings = False
    caption_above = False
    heading_caps = False

    max_figure_inches = 6.0

    def __init__(self) -> None:
        self.h1_n = 0
        self.h2_n = 0
        self.table_n = 0
        self.figure_n = 0
        # Images collected during rendering, written into the package afterwards.
        self.media: list[tuple[str, Path]] = []

    def figure(self, key: str) -> str:
        """An inline image, centred, with its caption beneath it."""
        self.figure_n += 1
        spec = C.FIGURES[key]
        path = ROOT / spec["file"]

        px_w, px_h = png_size(path)
        width_in = min(self.max_figure_inches, px_w / 300)
        height_in = width_in * px_h / px_w

        rel_id = f"rIdFig{self.figure_n}"
        self.media.append((rel_id, path))

        image = (
            '<w:p><w:pPr><w:jc w:val="center"/></w:pPr>'
            + drawing_xml(
                rel_id,
                int(width_in * EMU_PER_INCH),
                int(height_in * EMU_PER_INCH),
                path.name,
            )
            + "</w:p>"
        )
        caption = para(
            self.styles["figcaption"],
            f"FIGURE {self.figure_n}. {spec['caption']}"
            if self.caps_figure_label
            else f"Fig. {self.figure_n}. {spec['caption']}",
        )
        return image + caption

    # -- per-house pieces, overridden below --------------------------------

    def front_matter(self) -> str:
        raise NotImplementedError

    def references(self) -> str:
        raise NotImplementedError

    # -- shared -------------------------------------------------------------

    def heading(self, level: int, text: str) -> str:
        if level == 1:
            self.h1_n += 1
            self.h2_n = 0
            label = f"{self.h1_n} {text}" if self.number_headings else text
            if self.heading_caps:
                label = label.upper()
            return para(self.styles["h1"], label)

        self.h2_n += 1
        label = f"{self.h1_n}.{self.h2_n} {text}" if self.number_headings else text
        return para(self.styles["h2"], label)

    def table(self, key: str) -> str:
        self.table_n += 1
        spec = C.TABLES[key]
        caption = para(
            self.styles["caption"],
            f"Table {self.table_n}. {spec['caption']}",
        )
        body = table_xml(spec, self.table_style)
        return caption + body if self.caption_above else body + caption

    def body(self) -> str:
        out = self.front_matter()
        for kind, payload in C.BODY:
            if kind == "h1":
                out += self.heading(1, payload)
            elif kind == "h2":
                out += self.heading(2, payload)
            elif kind == "p1":
                out += para(self.styles["p1"], payload)
            elif kind == "p":
                out += para(self.styles["p"], payload)
            elif kind == "bullet":
                out += para(self.styles["bullet"], payload)
            elif kind in C.TABLES:
                out += self.table(kind)
            elif kind in C.FIGURES:
                out += self.figure(kind)
            else:
                raise ValueError(f"unknown block kind: {kind}")
        out += self.references()
        return out


class AIPRenderer(Renderer):
    """AIP Conference Proceedings: unnumbered capitalised headings, captions below."""

    styles = {
        "title": "PaperTitle",
        "author": "AuthorName",
        "affil": "AuthorAffiliation",
        "email": "AuthorEmail",
        "abstract": "Abstract",
        "h1": "Heading1",
        "h2": "Heading2",
        "p1": "Paragraph",
        "p": "Paragraph",
        "bullet": "Paragraphbulleted",
        "ref": "Reference",
        "caption": "TableCaption",
        "figcaption": "FigureCaption",
    }
    table_style = "TableGrid"
    number_headings = False
    caption_above = False
    heading_caps = True
    caps_figure_label = True
    # US Letter with the template's margins leaves about this much column.
    max_figure_inches = 6.0

    def front_matter(self) -> str:
        out = para(self.styles["title"], C.TITLE)

        segments: list[tuple[str, str]] = []
        for position, author in enumerate(C.AUTHORS):
            if position:
                segments.append((" and ", ""))
            segments.append((author["name"], ""))
            segments.append((f"{author['affil']}, {author['email']})", "super"))
        out += rich_para(self.styles["author"], segments)

        for index, affil in enumerate(C.AFFILIATIONS, start=1):
            out += rich_para(
                self.styles["affil"], [(str(index), "super"), (affil, "")]
            )

        for letter, email in C.EMAILS:
            out += rich_para(
                self.styles["email"], [(letter, "super"), (f") {email}", "")]
            )

        out += para(self.styles["abstract"], " " + C.ABSTRACT, bold_prefix="Abstract.")
        return out

    def references(self) -> str:
        # The Reference style carries its own numbering, so the entries are
        # added bare; numbering them here as well produced "4. 4. Luan, Y. ...".
        out = self.heading(1, "References")
        for ref in C.REFERENCES:
            out += para(self.styles["ref"], ref)
        return out


class LNCSRenderer(Renderer):
    """Springer LNCS: numbered headings to two levels, captions above tables."""

    styles = {
        "title": "papertitle",
        "author": "author",
        "affil": "address",
        "email": "e-mail",
        "abstract": "abstract",
        "keywords": "keywords",
        "h1": "heading1",
        "h2": "heading2",
        "p1": "p1a",
        "p": "Normal",
        "bullet": "bulletitem",
        "ref": "referenceitem",
        "caption": "tablecaption",
        "figcaption": "figurecaption",
    }
    table_style = "TableGrid"
    # heading1 and heading2 in this template already carry a numPr, so Word
    # supplies "3.3" itself. Prefixing it here too produced "3.3  3.3 ...".
    number_headings = False
    caption_above = True
    heading_caps = False
    caps_figure_label = False
    # The LNCS text block is 12.2 cm wide.
    max_figure_inches = 4.8

    def front_matter(self) -> str:
        out = para(self.styles["title"], C.TITLE)

        names = " and ".join(a["name"] for a in C.AUTHORS)
        out += para(self.styles["author"], names)

        for affil in C.AFFILIATIONS:
            out += para(self.styles["affil"], affil)
        out += para(self.styles["email"], C.EMAILS[0][1].split(": ", 1)[-1])

        out += para(self.styles["abstract"], " " + C.ABSTRACT, bold_prefix="Abstract.")
        out += para(self.styles["keywords"], " " + C.KEYWORDS, bold_prefix="Keywords:")
        return out

    def references(self) -> str:
        # referenceitem numbers itself, as the heading styles do.
        out = para(self.styles["h1"], "References")
        for ref in C.REFERENCES:
            out += para(self.styles["ref"], ref)
        return out


# ---------------------------------------------------------------------------
# Template surgery
# ---------------------------------------------------------------------------


# A .docm carries a VBA project, and its main part is declared with the
# macro-enabled content type. Copying those into a file named .docx produces
# something Word refuses to open as corrupt, so they are dropped and the
# content type rewritten on the way out.
_VBA_PARTS = ("word/vbaProject.bin", "word/vbaData.xml", "word/_rels/vbaProject.bin.rels")
_MACRO_MAIN = "application/vnd.ms-word.document.macroEnabled.main+xml"
_DOCX_MAIN = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)


def _demacro_content_types(xml: str) -> str:
    xml = xml.replace(_MACRO_MAIN, _DOCX_MAIN)
    xml = re.sub(r"<Override[^>]*vbaData[^>]*/>", "", xml)
    # Only the VBA project's own bin declaration goes. The AIP template declares
    # the same extension for an embedded OLE object, and removing that one
    # leaves a file Word reports as corrupt.
    xml = re.sub(
        r'<Default[^>]*Extension="bin"[^>]*ContentType="[^"]*vbaProject"[^>]*/>',
        "",
        xml,
    )
    return xml


def _demacro_rels(xml: str) -> str:
    return re.sub(r'<Relationship[^>]*vbaProject[^>]*/>', "", xml)


def render(template: Path, renderer: Renderer, out_path: Path) -> None:
    """Replace *template*'s body with the paper, keeping everything else."""
    src = zipfile.ZipFile(template)
    document = src.read("word/document.xml").decode("utf-8")

    # The final sectPr carries page size, margins and column setup. Keeping the
    # publisher's own is the whole point of starting from their file.
    sect = re.search(r"<w:sectPr[ >].*?</w:sectPr>", document, re.S)
    sect_xml = sect.group(0) if sect else ""

    body_open = document.index("<w:body>") + len("<w:body>")
    body_close = document.rindex("</w:body>")
    new_document = (
        document[:body_open] + renderer.body() + sect_xml + document[body_close:]
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            name = item.filename
            if name in _VBA_PARTS:
                continue
            if name == "word/document.xml":
                dst.writestr(item, new_document.encode("utf-8"))
            elif name == "[Content_Types].xml":
                raw = _demacro_content_types(src.read(name).decode("utf-8"))
                if "Extension=\"png\"" not in raw:
                    raw = raw.replace(
                        "<Types ",
                        "<Types ", 1
                    ).replace(
                        "</Types>",
                        '<Default Extension="png" ContentType="image/png"/></Types>',
                    )
                dst.writestr(item, raw.encode("utf-8"))
            elif name == "word/_rels/document.xml.rels":
                raw = _demacro_rels(src.read(name).decode("utf-8"))
                added = "".join(
                    f'<Relationship Id="{rid}" '
                    'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                    'relationships/image" '
                    f'Target="media/{path.name}"/>'
                    for rid, path in renderer.media
                )
                raw = raw.replace("</Relationships>", added + "</Relationships>")
                dst.writestr(item, raw.encode("utf-8"))
            else:
                dst.writestr(item, src.read(name))

        for _, path in renderer.media:
            dst.writestr(f"word/media/{path.name}", path.read_bytes())
    src.close()


def to_pdf(docx: Path) -> Path | None:
    """Convert for visual checking; returns None when LibreOffice is unavailable."""
    soffice = shutil.which("soffice") or shutil.which("soffice.exe")
    if soffice is None:
        for guess in (
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ):
            if Path(guess).exists():
                soffice = guess
                break
    if soffice is None:
        return None

    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir",
         str(docx.parent), str(docx)],
        check=False, capture_output=True, timeout=300,
    )
    pdf = docx.with_suffix(".pdf")
    return pdf if pdf.exists() else None


def main() -> None:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "paper")
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = [
        (AIP_TEMPLATE, AIPRenderer(), out_dir / "Paper_AIP_Conference_Proceedings.docx"),
        (LNCS_TEMPLATE, LNCSRenderer(), out_dir / "Paper_Springer_LNCS.docx"),
    ]
    for template, renderer, out_path in jobs:
        render(template, renderer, out_path)
        size = out_path.stat().st_size // 1024
        print(f"Wrote {out_path}  ({size} KB)")
        pdf = to_pdf(out_path)
        if pdf:
            print(f"      preview: {pdf.name}")


if __name__ == "__main__":
    main()
