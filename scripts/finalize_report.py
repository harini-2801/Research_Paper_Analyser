"""
Refresh the fields in the generated report with Word, then export a PDF.

python-docx can write the contents / list-of-figures / list-of-tables fields but
cannot compute page numbers. Word can, so the finished file is opened here, every
field is updated (twice, because the first pass changes pagination), and the
document is saved and exported.

Usage
-----
    python scripts/finalize_report.py [path/to/report.docx]
"""

from __future__ import annotations

import sys
from pathlib import Path

import win32com.client as win32

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "report" / "Project_Report_Harini_Sriram_23BDS1124.docx"


def main() -> None:
    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    pdf = docx.with_suffix(".pdf")

    word = win32.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    try:
        doc = word.Documents.Open(str(docx.resolve()))
        # Word's built-in contents styles: the template sets chapter lines in bold and
        # indents the section lines beneath them.
        try:
            doc.Styles(-20).Font.Bold = True            # TOC 1
            doc.Styles(-20).ParagraphFormat.SpaceBefore = 6
            doc.Styles(-21).Font.Bold = False           # TOC 2
            doc.Styles(-21).ParagraphFormat.LeftIndent = word.CentimetersToPoints(0.8)
        except Exception as exc:  # cosmetic; the contents are correct without it
            print("could not style the contents:", exc)
        for _ in range(2):
            doc.Repaginate()
            for toc in doc.TablesOfContents:
                toc.Update()
            for tof in doc.TablesOfFigures:
                tof.Update()
            doc.Fields.Update()
        doc.Repaginate()
        pages = doc.ComputeStatistics(2)
        words = doc.ComputeStatistics(0)
        doc.Save()
        doc.ExportAsFixedFormat(str(pdf.resolve()), 17)
        doc.Close(False)
    finally:
        word.Quit()
    print(f"{docx.name}: {pages} pages, {words:,} words -> {pdf.name}")


if __name__ == "__main__":
    main()
