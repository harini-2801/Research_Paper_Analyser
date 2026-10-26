"""
A local proxy for a similarity check: how much of the report repeats the
project's own earlier writing word for word.

Commercial checkers compare a submission with a large database that usually
includes the author's own earlier submissions and public repositories. This
script cannot reproduce that database, but it can measure the part that is
under our control: the report against the conference paper, the literature
survey, the READMEs and the code comments in this repository.

A report word counts as "matched" when it lies inside a run of at least N
consecutive words that also occurs, in the same order, in one of the sources.

Usage
-----
    python scripts/check_report_overlap.py [N=6] [--show 25]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import docx
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report" / "Project_Report_Harini_Sriram_23BDS1124.docx"

SOURCE_FILES = [
    "scripts/paper_content.py",
    "scripts/paper_body.py",
    "README.md",
    "IMPLEMENTATION_PLAN.md",
    "DEPLOYMENT.md",
    "SYSTEM_ARCHITECTURE_FILES.md",
    ".kiro/specs/research-paper-relationship-analyzer/requirements.md",
]
SOURCE_PDFS = [
    "Literature_Survey_Research_Paper_Relationship_Analyzer (1).pdf",
    "docs/HOW_IT_WORKS.pdf",
    "SYSTEM_ARCHITECTURE_FILES.pdf",
    "paper/Paper_AIP_Conference_Proceedings.pdf",
]

WORD = re.compile(r"[a-z0-9][a-z0-9\-']*")


def words(text: str) -> list[str]:
    return WORD.findall(text.lower().replace("’", "'"))


def load_sources() -> list[tuple[str, list[str]]]:
    out = []
    for rel in SOURCE_FILES:
        p = ROOT / rel
        if p.exists():
            out.append((rel, words(p.read_text(encoding="utf-8", errors="ignore"))))
    for p in sorted((ROOT / "src" / "rpra").glob("*.py")):
        out.append((f"src/rpra/{p.name}", words(p.read_text(encoding="utf-8", errors="ignore"))))
    for rel in SOURCE_PDFS:
        p = ROOT / rel
        if p.exists():
            doc = pymupdf.open(p)
            out.append((rel, words("\n".join(pg.get_text() for pg in doc))))
    return out


def report_paragraphs() -> list[str]:
    d = docx.Document(REPORT)
    paras = []
    started = False
    for block in d.element.body.iterchildren():
        tag = block.tag.split("}")[1]
        if tag == "p":
            text = "".join(t.text or "" for t in block.iter() if t.tag.endswith("}t"))
            text = text.strip()
            style = block.find(".//{*}pStyle")
            is_h1 = style is not None and style.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") == "Heading1"
            # The contents page repeats every heading, so key off the real heading style.
            if is_h1 and text.startswith("CHAPTER 1:"):
                started = True
            if is_h1 and text.upper().startswith("REFERENCES"):
                break
            if started and len(text.split()) >= 8:
                paras.append(text)
        elif tag == "tbl" and started:
            for r in block.iter():
                if r.tag.endswith("}p"):
                    text = "".join(t.text or "" for t in r.iter() if t.tag.endswith("}t")).strip()
                    if len(text.split()) >= 8:
                        paras.append(text)
    return paras


def main() -> None:
    n = 6
    show = 25
    args = sys.argv[1:]
    if args and args[0].isdigit():
        n = int(args[0])
    if "--show" in args:
        show = int(args[args.index("--show") + 1])

    sources = load_sources()
    index: dict[tuple, str] = {}
    for name, toks in sources:
        for i in range(len(toks) - n + 1):
            index.setdefault(tuple(toks[i:i + n]), name)

    total = matched = 0
    per_source: dict[str, int] = {}
    flagged = []
    for para in report_paragraphs():
        toks = words(para)
        if len(toks) < n:
            continue
        mark = [False] * len(toks)
        src_hits: dict[str, int] = {}
        for i in range(len(toks) - n + 1):
            src = index.get(tuple(toks[i:i + n]))
            if src:
                for j in range(i, i + n):
                    mark[j] = True
                src_hits[src] = src_hits.get(src, 0) + 1
        m = sum(mark)
        total += len(toks)
        matched += m
        for s, c in src_hits.items():
            per_source[s] = per_source.get(s, 0) + c
        if m:
            flagged.append((m / len(toks), m, para, src_hits))

    print(f"report words checked: {total:,}")
    print(f"words inside a {n}-word run found in the project's own writing: {matched:,} "
          f"({100 * matched / max(total, 1):.1f}%)")
    print("\nmatching by source (shingle hits):")
    for s, c in sorted(per_source.items(), key=lambda x: -x[1])[:10]:
        print(f"  {c:5d}  {s}")
    flagged.sort(key=lambda x: -x[1])
    print(f"\n{len(flagged)} paragraphs with any match; worst {show}:")
    for frac, m, para, hits in flagged[:show]:
        top = max(hits, key=hits.get)
        print(f"\n[{m} words, {100 * frac:.0f}% of paragraph, mostly {top}]\n  {para[:230]}")


if __name__ == "__main__":
    main()
