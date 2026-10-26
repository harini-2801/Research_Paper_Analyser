"""Appendices of the project report. Tables are built from the real run output."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKS: list = []
add = BLOCKS.append

_data = json.loads((ROOT / "paper" / "figure_data.json").read_text(encoding="utf-8"))
_run = json.loads((ROOT / "paper" / "_run" / "report.json").read_text(encoding="utf-8"))
_TITLE = dict(zip(_data["order"], _data["titles"]))


def _short(doc_id: str) -> str:
    t = _TITLE.get(doc_id, doc_id)
    t = t.split(":")[0]
    return t if len(t) <= 64 else t[:62] + "…"


# ----------------------------------------------------------------------
add(("h1u", "Appendix 1: Configuration File"))
add(("p",
     "The pipeline reads one YAML file. Every key is validated at start-up and a missing or "
     "invalid key stops the run with a descriptive message; the five scoring weights must "
     "sum to 1.0."))
config_lines = (ROOT / "config.yaml").read_text(encoding="utf-8").splitlines()
# Drop the long comment banner so the listing shows the settings themselves.
config_lines = [ln for ln in config_lines if not ln.startswith("# Research Paper") and
                not ln.startswith("# All keys")]
add(("code", {"caption": "Listing A1.1. config.yaml", "lines": config_lines, "size": 8.5}))

# ----------------------------------------------------------------------
add(("h1u", "Appendix 2: Running the System"))
add(("p", "**Installation and a first run on a single machine.**"))
add(("code", {
    "caption": "Listing A2.1. Commands",
    "lines": [
        "pip install -e .                       # core install, about 174 MB",
        "pip install -e \".[ml]\"                # optional: transformer models (~2.5 GB)",
        "",
        "python scripts/make_sample_corpus.py   # six PDFs with two planted contradictions",
        "rpra run --extraction-backend heuristic --no-nli",
        "rpra serve                             # interface at /app, backend page at /",
        "",
        "pytest -q                              # 236 tests",
    ],
}))
add(("p", "**Deployment on Render** uses the repository's `render.yaml`:"))
add(("code", {
    "caption": "Listing A2.2. Render service settings",
    "lines": [
        "services:",
        "  - type: web",
        "    name: rpra-api",
        "    runtime: python",
        "    plan: free",
        "    region: oregon",
        "    buildCommand: \"pip install --upgrade pip && pip install -r requirements.txt\"",
        "    startCommand: \"uvicorn rpra.server:app --host 0.0.0.0 --port $PORT --workers 1\"",
        "    healthCheckPath: /api/status",
    ],
}))

# ----------------------------------------------------------------------
add(("h1u", "Appendix 3: Structure of an Analysis Result"))
add(("p",
     "A research gap in the JSON report carries its description, a novelty score, the "
     "supporting documents and a full evidence trail. The entry below is abridged from the "
     "run on the thirty-paper corpus."))
gap = _run["research_gaps"][0]
ev = gap["evidence"][0]
add(("code", {
    "caption": "Listing A3.1. First research gap in report.json (abridged)",
    "lines": [
        "{",
        '  "description": "Empirical results show that DocRED is challenging for',
        '                  existing RE methods, which indicates that document-level RE',
        '                  remains an open problem and requires further efforts.",',
        f'  "novelty_score": {gap["novelty_score"]},',
        f'  "supporting_docs": {json.dumps(gap["supporting_docs"])},',
        '  "evidence": [{',
        f'    "source_doc_id": "{ev["source_doc_id"]}",',
        f'    "section": "{ev["section"]}",',
        f'    "page_number": {ev["page_number"]},',
        '    "sentence_span": "Empirical results show that DocRED is challenging ..."',
        "  }],",
        '  "explanation": "Stated directly in docred_2019 (abstract, p.1) as an open',
        '                  research gap."',
        "}",
    ],
}))
add(("p", "**Run summary** (from the same report):"))
summ = _run["summary"]
add(("tab", {
    "key": "runsummary",
    "caption": "Summary block of the report for the thirty-paper corpus.",
    "headers": ["Field", "Value"],
    "widths": [3.2, 1.5],
    "rows": [
        ["Documents", str(summ["total_documents"])],
        ["Relationship pairs scored", str(summ["relationship_pairs_scored"])],
        ["Confirmed contradictions", str(summ["confirmed_contradictions"])],
        ["Unconfirmed contradictions", str(summ["unconfirmed_contradictions"])],
        ["Confirmed research gaps", str(summ["confirmed_gaps"])],
    ],
}))

# ----------------------------------------------------------------------
add(("h1u", "Appendix 4: Twenty Strongest Relationships"))
add(("p",
     "The twenty highest composite scores from the evaluation run. The rank-ten cut-off used "
     "in Chapter 7 falls after the tenth row."))
rows = []
for i, p in enumerate(_run["top_related_pairs"], 1):
    rows.append([str(i), _short(p["doc_a"]), _short(p["doc_b"]), f'{p["composite_score"]:.3f}'])
add(("tab", {
    "key": "top20",
    "caption": "The twenty strongest document pairs in the evaluation corpus.",
    "size": 10,
    "headers": ["Rank", "Paper A", "Paper B", "Score"],
    "widths": [0.7, 3.0, 3.0, 0.9],
    "rows": rows,
}))

# ----------------------------------------------------------------------
add(("h1u", "Appendix 5: Repository Layout"))
add(("code", {
    "caption": "Listing A5.1. Principal directories and files",
    "lines": [
        "config.yaml            single configuration file",
        "render.yaml            Render deployment",
        "vercel.json            Vercel deployment of the interface",
        "requirements.txt       core dependencies",
        "src/rpra/",
        "    models.py          domain models",
        "    ingestion.py       PDF reading and segmentation",
        "    citations.py       reference parsing",
        "    classification.py  document category",
        "    heuristic_extraction.py, extraction.py   entity and relation extraction",
        "    embeddings.py      vectors, with fallback",
        "    scoring.py         five-dimension score",
        "    knowledge_graph.py graph construction and storage",
        "    claims.py, contradiction.py   comparable claims, detectors, gates",
        "    gap_discovery.py   stated, weak and absent gaps",
        "    explainer.py       evidence-grounded explanation",
        "    reporter.py, report_pdf.py    JSON, Markdown, PDF export",
        "    pipeline.py        orchestration",
        "    server.py          REST, WebSocket, static hosting",
        "    static/            interface and backend status page",
        "scripts/               corpus fetching, evaluation, figures",
        "tests/                 236 automated tests",
    ],
}))
