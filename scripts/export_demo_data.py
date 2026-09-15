"""
Freeze a pipeline run into a static JSON bundle for the web UI.

The frontend normally talks to the FastAPI backend. On a static host such as
Vercel there is no backend, so every panel sits empty and the app looks broken.

This script runs the pipeline once and writes every API response to
`src/rpra/static/demo/data.json`. When the UI cannot reach a live API it loads
that file instead and becomes fully explorable - graph, relationships,
contradictions, gaps and evidence all work; only starting a new run needs a
real backend.

Usage
-----
    python scripts/export_demo_data.py [corpus_dir]

Defaults to ./data/eval_corpus, falling back to ./data/papers.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpra.config import Settings
from rpra.pipeline import run_pipeline

OUTPUT = Path(__file__).resolve().parents[1] / "src" / "rpra" / "static" / "demo" / "data.json"


def pick_corpus() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    for candidate in (Path("./data/eval_corpus"), Path("./data/papers")):
        if candidate.exists() and any(candidate.glob("*.pdf")):
            return candidate
    raise SystemExit(
        "No corpus found. Run scripts/fetch_eval_corpus.py or "
        "scripts/make_sample_corpus.py first."
    )


def main() -> int:
    corpus = pick_corpus()
    print(f"Running pipeline over {corpus.resolve()}")

    settings = Settings()
    settings.storage.corpus_input_path = str(corpus)
    settings.storage.output_path = "./output/demo"
    settings.storage.graph_path = "./output/demo/knowledge_graph.json"
    settings.storage.embeddings_path = "./output/demo/embeddings.npz"

    def show(event):
        if event.status.value in ("complete", "failed") and not event.doc_id:
            print(f"  [{event.stage}] {event.message[:80]}")

    result = run_pipeline(
        settings, on_progress=show, extraction_backend="heuristic", use_nli=False
    )

    # Reuse the server's own serialisers so the demo payload and the live API
    # can never drift apart.
    from rpra import server

    server.state.result = result
    server.current_settings = settings

    bundle = {
        "generated_from": corpus.name,
        "status": asyncio.run(server.get_status()),
        "documents": asyncio.run(server.get_documents()),
        "graph": asyncio.run(server.get_knowledge_graph()),
        "contradictions": asyncio.run(server.get_contradictions()),
        "gaps": asyncio.run(server.get_research_gaps()),
        "scores": asyncio.run(server.get_relationship_scores()),
    }
    # The full entity list is large and the UI only needs it for filtering.
    bundle["entities"] = asyncio.run(server.get_entities())[:600]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(bundle, separators=(",", ":")), encoding="utf-8")

    size_kb = OUTPUT.stat().st_size // 1024
    print(f"\nWrote {OUTPUT.relative_to(Path.cwd())} ({size_kb} KB)")
    print(f"  documents      {len(bundle['documents'])}")
    print(f"  graph nodes    {len(bundle['graph']['nodes'])}")
    print(f"  graph edges    {len(bundle['graph']['edges'])}")
    print(f"  contradictions {len(bundle['contradictions'])}")
    print(f"  gaps           {len(bundle['gaps'])}")
    print(f"  scored pairs   {len(bundle['scores'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
