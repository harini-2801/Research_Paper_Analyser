"""
FastAPI backend for the Research Paper Relationship Analyzer.

Exposes the pipeline over REST, streams progress over a WebSocket, and serves
the web UI.

Every response shape here is derived from the models in :mod:`rpra.models`.
Serialisation lives in the `_serialise_*` helpers rather than inline in the
route handlers so that a change to a model surfaces in one place.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rpra.config import Settings, load_settings
from rpra.knowledge_graph import KnowledgeGraph
from rpra.models import (
    Contradiction,
    ContradictionStatus,
    Document,
    PipelineStageStatus,
    ProgressEvent,
    RelationshipScore,
    ResearchGap,
)
from rpra.pipeline import PipelineResult, run_pipeline

logger = logging.getLogger("rpra.server")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Seed the corpus when the service starts, before it accepts traffic."""
    seed_corpus_if_empty(asyncio.get_running_loop())
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Research Paper Relationship Analyzer API",
    description=(
        "Knowledge graph construction, contradiction detection and research gap "
        "discovery over a corpus of research papers."
    ),
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = Path("config.yaml")

try:
    current_settings: Settings = load_settings(CONFIG_PATH)
except Exception as exc:
    logger.warning("Could not load %s (%s); using defaults.", CONFIG_PATH, exc)
    current_settings = Settings()


# ----------------------------------------------------------------------
# Corpus seeding
# ----------------------------------------------------------------------


def seed_corpus_if_empty(loop: asyncio.AbstractEventLoop | None = None) -> int:
    """
    Give a fresh instance something to analyse.

    A deployment starts with an empty corpus directory - the real one is
    gitignored, and on hosts with an ephemeral filesystem (Render's free tier
    among them) it is wiped every time the instance restarts, which on a free
    plan means after every ~15 minutes of inactivity. Without this, the
    interface opens reporting zero papers and "Run analysis" has nothing to
    do - and just as importantly, a corpus loaded by hand in a previous
    session (the 30-paper arXiv set, say) silently reverts to empty on the
    next cold start with no indication why.

    RPRA_SEED_CORPUS controls what gets restored. It defaults to "arxiv" when
    the repository's bundled `dataset/papers` directory is present - there is no
    reason to open on 6 synthetic papers when 30 real ones are sitting on disk
    and cost a file copy - and to "sample" otherwise, so a deployment without
    the dataset still has something to analyse.

      "sample" - the 6-paper synthetic corpus, written instantly.
      "arxiv"            - the 30-paper evaluation corpus. This is a two-minute
                            network fetch, so it is kicked off in a background
                            thread rather than awaited here: blocking startup
                            on it would fail the platform's health check, and
                            every restart would look like a failed deploy.
      "0" / "false" / "no" / "off" / "none" - do not seed at all.

    Never overwrites papers that are already there (of either curated set or a
    user's own uploads), so switching this on is always safe to leave set.
    """
    from rpra.arxiv_corpus import local_dataset_dir

    default_mode = "arxiv" if local_dataset_dir() else "sample"
    mode = os.environ.get("RPRA_SEED_CORPUS", default_mode).strip().lower()
    if mode in {"0", "false", "no", "off", "none"}:
        return 0

    corpus_dir = Path(current_settings.storage.corpus_input_path)
    already_has_papers = corpus_dir.exists() and any(corpus_dir.glob("*.pdf"))

    if mode == "arxiv":
        if already_has_papers:
            return 0
        if loop is None:
            logger.warning(
                "RPRA_SEED_CORPUS=arxiv needs a running event loop; "
                "falling back to the sample corpus for this start."
            )
        else:
            outstanding = _launch_arxiv_fetch(corpus_dir, loop)
            logger.info(
                "Fetching the arXiv corpus in the background on startup "
                "(%d paper(s) outstanding)", outstanding,
            )
            return 0

    try:
        from rpra.sample_corpus import seed_if_empty

        written = seed_if_empty(corpus_dir)
        if written:
            logger.info("Seeded sample corpus: %d papers", len(written))
        return len(written)
    except Exception as exc:
        logger.warning("Could not seed the sample corpus: %s", exc)
        return 0


def _purge_known(corpus_dir: Path, slugs: set[str]) -> int:
    """
    Remove PDFs whose filename stem is in *slugs*.

    Used when the interface switches which of the two curated demo corpora is
    loaded, so "Load" always means "replace with exactly this set" rather than
    "add to whatever is already there". Only filenames from the other curated
    set are ever touched - a paper a user uploaded under an arbitrary name is
    never removed by switching between sample and arXiv.
    """
    if not corpus_dir.exists():
        return 0
    removed = 0
    for pdf in corpus_dir.glob("*.pdf"):
        if pdf.stem in slugs:
            pdf.unlink()
            removed += 1
    return removed


# ----------------------------------------------------------------------
# Shared state
# ----------------------------------------------------------------------


class AppState:
    """
    Mutable state shared between the pipeline worker thread and request handlers.

    The pipeline runs in a worker thread, so every field written there and read
    from a handler is guarded by the lock.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.result: PipelineResult | None = None
        self.running: bool = False
        self.last_error: str | None = None
        self.events: list[dict] = []

    def snapshot(self) -> tuple[PipelineResult | None, bool, str | None]:
        with self.lock:
            return self.result, self.running, self.last_error


state = AppState()


class ConnectionManager:
    """Tracks live WebSocket clients and fans progress events out to them."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        stale: list[WebSocket] = []
        for connection in list(self.active):
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


manager = ConnectionManager()


def _safe_broadcast(loop: asyncio.AbstractEventLoop, payload: dict) -> None:
    """
    Fire a progress payload at connected clients, never raising.

    Broadcasting is best-effort: nobody may be listening, and the event loop
    can be mid-shutdown during a fast restart. It must never propagate into a
    worker thread, because the thread is doing the real work - downloading
    papers, running the pipeline - and a failed status message is not a reason
    to abandon it. This previously could raise, and since the error handlers
    also broadcast, a single bad send raised a second, unhandled exception
    straight out of the thread.
    """
    try:
        asyncio.run_coroutine_threadsafe(manager.broadcast(payload), loop)
    except Exception as exc:
        logger.debug("Could not broadcast progress: %s", exc)


# ----------------------------------------------------------------------
# Request schemas
# ----------------------------------------------------------------------


class RunRequest(BaseModel):
    extraction_backend: str = Field(
        "auto",
        description="auto | llm | heuristic. 'heuristic' needs no API key.",
        pattern="^(auto|llm|heuristic)$",
    )
    use_nli: bool = Field(
        True,
        description="Load the NLI model for contradiction detection.",
    )
    skip_explanation: bool = Field(
        False, description="Skip LLM explanation generation."
    )


class WeightUpdateRequest(BaseModel):
    objective: float = Field(..., ge=0.0, le=1.0)
    methodology: float = Field(..., ge=0.0, le=1.0)
    dataset: float = Field(..., ge=0.0, le=1.0)
    results_metrics: float = Field(..., ge=0.0, le=1.0)
    citation: float = Field(..., ge=0.0, le=1.0)

    def total(self) -> float:
        return (
            self.objective
            + self.methodology
            + self.dataset
            + self.results_metrics
            + self.citation
        )


# ----------------------------------------------------------------------
# Serialisation helpers
# ----------------------------------------------------------------------


def _serialise_document(doc: Document) -> dict[str, Any]:
    pages = [seg.page_end for seg in doc.segments] or [0]
    return {
        "doc_id": doc.id,
        "title": doc.title or doc.id,
        "category": doc.category.value,
        "category_confidence": round(doc.category_confidence, 3),
        "needs_review": bool(doc.metadata.get("needs_manual_review", False)),
        "segments": [seg.section_type for seg in doc.segments],
        "segment_count": len(doc.segments),
        "total_pages": max(pages),
        "reference_count": doc.metadata.get("reference_count", 0),
        "file_path": doc.file_path,
    }


def _serialise_contradiction(index: int, c: Contradiction) -> dict[str, Any]:
    return {
        "id": f"contradiction-{index + 1}",
        "doc_a": c.doc_id_a,
        "doc_b": c.doc_id_b,
        "claim_a": c.claim_a,
        "claim_b": c.claim_b,
        "nli_label": c.nli_label.value,
        "nli_confidence": round(c.nli_confidence, 3),
        "confidence": round(c.confidence, 3),
        "status": c.status.value,
        "confirmed": c.status == ContradictionStatus.CONFIRMED,
        "dataset_compatible": c.dataset_compatible,
        "metrics_comparable": c.metrics_comparable,
        "methodology_similarity": round(c.methodology_similarity, 3),
        "explanation": c.explanation or "",
        "evidence": [e.model_dump() for e in c.evidence],
    }


def _serialise_gap(index: int, g: ResearchGap) -> dict[str, Any]:
    return {
        "id": f"gap-{index + 1}",
        "description": g.description,
        "novelty_score": round(g.novelty_score, 3),
        "supporting_docs": g.supporting_doc_ids,
        "bridge_entities": g.bridge_entities,
        "confirmed": g.confirmed,
        "explanation": g.explanation or "",
        "evidence": [e.model_dump() for e in g.evidence],
    }


def _serialise_score(s: RelationshipScore) -> dict[str, Any]:
    return {
        "doc_a": s.doc_id_a,
        "doc_b": s.doc_id_b,
        "composite_score": round(s.composite_score, 3),
        "components": {
            "objective": round(s.objective_similarity, 3),
            "methodology": round(s.methodology_similarity, 3),
            "dataset": round(s.dataset_overlap, 3),
            "results_metrics": round(s.results_metrics_similarity, 3),
            "citation": round(s.citation_overlap, 3),
        },
        "weights_used": s.weights_used,
    }


def _node_label(node_id: str, attrs: dict) -> str:
    """Pick the best human-readable label for a graph node."""
    node_type = attrs.get("node_type")
    if node_type == "document":
        return attrs.get("title") or node_id
    if node_type in ("entity", "bridge_entity"):
        return attrs.get("text") or node_id
    return node_id


def _serialise_graph(kg: KnowledgeGraph, bridge_entities: dict[str, list[str]]) -> dict:
    """
    Convert the knowledge graph into Cytoscape.js element format.

    Node and edge attribute names come from :mod:`rpra.knowledge_graph`
    (`node_type`, `edge_type`), not from a parallel naming scheme.
    """
    graph = kg.graph
    bridge_texts = {t.lower() for t in bridge_entities}

    nodes = []
    for node_id, attrs in graph.nodes(data=True):
        node_type = attrs.get("node_type", "unknown")
        label = _node_label(node_id, attrs)
        nodes.append(
            {
                "data": {
                    "id": node_id,
                    "label": label,
                    "short_label": label if len(label) <= 46 else label[:44] + "…",
                    "node_type": node_type,
                    "entity_type": attrs.get("entity_type", ""),
                    "category": attrs.get("category", ""),
                    "doc_id": attrs.get("doc_id", ""),
                    "section": attrs.get("section", ""),
                    "page_number": attrs.get("page_number", 0),
                    "sentence_span": attrs.get("sentence_span", ""),
                    "is_bridge": (
                        node_type == "bridge_entity"
                        or attrs.get("text", "").lower() in bridge_texts
                    ),
                }
            }
        )

    edges = []
    for source, target, key, attrs in graph.edges(keys=True, data=True):
        evidence = attrs.get("evidence") or {}
        if not isinstance(evidence, dict):
            evidence = {}
        edges.append(
            {
                "data": {
                    "id": f"{source}__{target}__{key}",
                    "source": source,
                    "target": target,
                    "edge_type": attrs.get("edge_type", "relates"),
                    "confidence": attrs.get("confidence", 1.0),
                    "composite_score": attrs.get("composite_score"),
                    "is_cross_document": attrs.get("is_cross_document", False),
                    "source_doc_id": evidence.get("source_doc_id", ""),
                    "section": evidence.get("section", ""),
                    "page_number": evidence.get("page_number", 0),
                    "sentence_span": evidence.get("sentence_span", ""),
                }
            }
        )

    return {"nodes": nodes, "edges": edges}


def _load_graph_from_disk() -> KnowledgeGraph | None:
    graph_file = Path(current_settings.storage.graph_path)
    if not graph_file.exists():
        return None
    try:
        return KnowledgeGraph.load(graph_file)
    except Exception as exc:
        logger.warning("Could not load saved graph %s: %s", graph_file, exc)
        return None


# ----------------------------------------------------------------------
# REST endpoints
# ----------------------------------------------------------------------


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    """System status, corpus contents and a summary of the most recent run."""
    result, running, last_error = state.snapshot()

    corpus_dir = Path(current_settings.storage.corpus_input_path)
    pdf_files = sorted(corpus_dir.glob("*.pdf")) if corpus_dir.exists() else []

    summary = result.summary() if result else {}

    return {
        "status": "running" if running else "idle",
        "last_error": last_error,
        "corpus_path": str(corpus_dir),
        "pdf_count": len(pdf_files),
        "pdf_files": [f.name for f in pdf_files],
        "has_results": result is not None,
        "summary": summary,
        # Flattened for convenience; the UI reads these directly.
        "kg_nodes": summary.get("kg_nodes", 0),
        "kg_edges": summary.get("kg_edges", 0),
        "contradictions_count": summary.get("contradictions", 0),
        "confirmed_contradictions": summary.get("confirmed_contradictions", 0),
        "gaps_count": summary.get("gaps", 0),
        "entities_count": summary.get("entities", 0),
        "bridge_entities_count": summary.get("bridge_entities", 0),
        "corpus_sources": {
            "sample": 6,
            "arxiv": 30,
        },
        "config": {
            "llm_provider": current_settings.llm.provider,
            "llm_model": current_settings.llm.model,
            "embedding_model": current_settings.embedding.model,
            "nli_model": current_settings.nli.model,
            "extraction_backend": current_settings.pipeline.extraction_backend,
            "weights": current_settings.relationship_scoring.weights.model_dump(),
        },
    }


@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict[str, Any]:
    """Add a PDF to the corpus directory."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    content = await file.read()
    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{file.filename} is not a valid PDF (missing %PDF header).",
        )

    target_dir = Path(current_settings.storage.corpus_input_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    # Guard against a filename that tries to escape the corpus directory.
    target_path = target_dir / Path(file.filename).name
    target_path.write_bytes(content)

    return {
        "filename": target_path.name,
        "size_bytes": len(content),
        "message": f"Uploaded {target_path.name} to the corpus.",
    }


@app.delete("/api/corpus/{filename}")
async def delete_pdf(filename: str) -> dict[str, Any]:
    """Remove a PDF from the corpus directory."""
    target_dir = Path(current_settings.storage.corpus_input_path)
    target_path = target_dir / Path(filename).name
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found in corpus.")
    target_path.unlink()
    return {"filename": target_path.name, "message": f"Removed {target_path.name}."}


@app.post("/api/run")
async def trigger_pipeline(request: RunRequest) -> dict[str, Any]:
    """
    Start a pipeline run in a background thread.

    Progress is streamed to WebSocket clients; poll `/api/status` or watch the
    socket for completion.
    """
    with state.lock:
        if state.running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pipeline run is already in progress.",
            )
        state.running = True
        state.last_error = None
        state.events = []

    corpus_dir = Path(current_settings.storage.corpus_input_path)
    if not corpus_dir.exists() or not any(corpus_dir.glob("*.pdf")):
        with state.lock:
            state.running = False
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"No PDFs found in {corpus_dir}. Upload papers first, or run "
                "scripts/make_sample_corpus.py to generate a sample corpus."
            ),
        )

    # Capture the running loop here, on the main thread. The worker thread has
    # no event loop of its own, so asking for one there raises.
    loop = asyncio.get_running_loop()

    def handle_progress(event: ProgressEvent) -> None:
        payload = {
            "type": "progress",
            "stage": event.stage,
            "doc_id": event.doc_id,
            "status": event.status.value,
            "message": event.message,
            "details": event.details,
            "elapsed_seconds": event.elapsed_seconds,
        }
        with state.lock:
            state.events.append(payload)
        _safe_broadcast(loop, payload)

    def worker() -> None:
        try:
            result = run_pipeline(
                current_settings,
                on_progress=handle_progress,
                extraction_backend=request.extraction_backend,
                use_nli=request.use_nli,
                skip_explanation=request.skip_explanation,
            )
            with state.lock:
                state.result = result
            payload = {
                "type": "complete",
                "stage": "pipeline",
                "status": PipelineStageStatus.COMPLETE.value,
                "message": f"Pipeline complete in {result.elapsed_seconds}s",
                "details": result.summary(),
            }
        except Exception as exc:
            logger.exception("Pipeline run failed")
            with state.lock:
                state.last_error = str(exc)
            payload = {
                "type": "error",
                "stage": "pipeline",
                "status": PipelineStageStatus.FAILED.value,
                "message": f"Pipeline failed: {exc}",
                "details": {},
            }
        finally:
            with state.lock:
                state.running = False

        _safe_broadcast(loop, payload)

    threading.Thread(target=worker, name="rpra-pipeline", daemon=True).start()

    return {
        "message": "Pipeline started.",
        "extraction_backend": request.extraction_backend,
        "use_nli": request.use_nli,
    }


@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket) -> None:
    """Stream pipeline progress events to the UI."""
    await manager.connect(websocket)
    try:
        # Replay what has happened so far so a client that connects mid-run is
        # not left with a blank panel.
        with state.lock:
            backlog = list(state.events)
        for event in backlog:
            await websocket.send_json(event)

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


@app.get("/api/graph")
async def get_knowledge_graph() -> dict[str, Any]:
    """The knowledge graph in Cytoscape.js element format."""
    result, _, _ = state.snapshot()

    if result and result.knowledge_graph:
        return {
            **_serialise_graph(result.knowledge_graph, result.bridge_entities),
            "bridge_entities": result.bridge_entities,
        }

    kg = _load_graph_from_disk()
    if kg is None:
        return {"nodes": [], "edges": [], "bridge_entities": {}}
    return {**_serialise_graph(kg, {}), "bridge_entities": {}}


@app.get("/api/documents")
async def get_documents() -> list[dict[str, Any]]:
    """Ingested documents with category and segment statistics."""
    result, _, _ = state.snapshot()
    if not result:
        return []
    return [_serialise_document(d) for d in result.documents]


@app.get("/api/contradictions")
async def get_contradictions(confirmed_only: bool = False) -> list[dict[str, Any]]:
    """Detected contradictions with stance scores and evidence trails."""
    result, _, _ = state.snapshot()
    if not result:
        return []
    items = result.contradictions
    if confirmed_only:
        items = [c for c in items if c.status == ContradictionStatus.CONFIRMED]
    return [_serialise_contradiction(i, c) for i, c in enumerate(items)]


@app.get("/api/gaps")
async def get_research_gaps() -> list[dict[str, Any]]:
    """Novelty-ranked research gaps with evidence trails."""
    result, _, _ = state.snapshot()
    if not result:
        return []
    return [_serialise_gap(i, g) for i, g in enumerate(result.gaps)]


@app.get("/api/scores")
async def get_relationship_scores() -> list[dict[str, Any]]:
    """Pairwise relationship scores, strongest first."""
    result, _, _ = state.snapshot()
    if not result:
        return []
    ordered = sorted(result.scores, key=lambda s: s.composite_score, reverse=True)
    return [_serialise_score(s) for s in ordered]


@app.get("/api/entities")
async def get_entities(doc_id: str | None = None) -> list[dict[str, Any]]:
    """Extracted entities, optionally filtered to one document."""
    result, _, _ = state.snapshot()
    if not result:
        return []
    entities = result.entities
    if doc_id:
        entities = [e for e in entities if e.doc_id == doc_id]
    return [
        {
            "id": str(e.id),
            "doc_id": e.doc_id,
            "entity_type": e.entity_type.value,
            "text": e.text,
            "section": e.section,
            "page_number": e.page_number,
            "sentence_span": e.sentence_span,
        }
        for e in entities
    ]


@app.get("/api/report")
async def download_report(fmt: str = "json") -> FileResponse:
    """Download the generated report as JSON or Markdown."""
    if fmt not in ("json", "md", "pdf"):
        raise HTTPException(
            status_code=400, detail="fmt must be 'json', 'md' or 'pdf'."
        )

    output_dir = Path(current_settings.storage.output_path)
    report_file = output_dir / f"report.{fmt}"
    if not report_file.exists():
        raise HTTPException(
            status_code=404,
            detail="No report available yet. Run the pipeline first.",
        )

    media_type = {
        "json": "application/json",
        "md": "text/markdown",
        "pdf": "application/pdf",
    }[fmt]
    return FileResponse(report_file, media_type=media_type, filename=report_file.name)


@app.post("/api/config/weights")
async def update_weights(req: WeightUpdateRequest) -> dict[str, Any]:
    """
    Update relationship scoring weights.

    Takes effect on the next run; existing scores are not recomputed.
    """
    total = req.total()
    if abs(total - 1.0) > 1e-4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Weights must sum to 1.0 (current sum: {round(total, 4)})",
        )

    weights = current_settings.relationship_scoring.weights
    weights.objective = req.objective
    weights.methodology = req.methodology
    weights.dataset = req.dataset
    weights.results_metrics = req.results_metrics
    weights.citation = req.citation

    return {
        "message": "Weights updated. Re-run the pipeline to apply them.",
        "weights": weights.model_dump(),
    }


@app.post("/api/corpus/seed")
async def seed_corpus() -> dict[str, Any]:
    """
    Switch the corpus to the 6-paper sample set.

    Treated as an explicit "load this instead", not "add if missing": any
    arXiv papers left over from a previous switch are removed first, so the
    corpus always ends up as exactly the sample set rather than a mixture of
    both. A user's own uploads, under their own filenames, are never touched.
    """
    from rpra.arxiv_corpus import known_slugs as arxiv_known_slugs
    from rpra.sample_corpus import build_corpus

    corpus_dir = Path(current_settings.storage.corpus_input_path)
    corpus_dir.mkdir(parents=True, exist_ok=True)
    removed = _purge_known(corpus_dir, arxiv_known_slugs())
    written = build_corpus(corpus_dir)

    present = len(list(corpus_dir.glob("*.pdf")))
    return {
        "seeded": len(written),
        "removed": removed,
        "pdf_count": present,
        "message": f"Loaded the {len(written)}-paper sample corpus.",
    }


def _launch_arxiv_fetch(corpus_dir: Path, loop: asyncio.AbstractEventLoop) -> int:
    """
    Start a background download of the 30-paper arXiv corpus.

    Shared between the explicit `/api/corpus/fetch-arxiv` endpoint and the
    startup hook (`RPRA_SEED_CORPUS=arxiv`), so a fresh instance can converge
    on the full evaluation corpus automatically without ever blocking startup
    on a two-minute network fetch. Progress streams over the same WebSocket
    the pipeline uses, because a download this long with no feedback is
    indistinguishable from a hang. Returns the number of papers still missing.

    Claims the state.running flag itself. It used to be the caller's job, and
    the HTTP endpoint did it but the startup hook did not - so an auto-seeded
    instance reported itself idle while the download was still running, and the
    interface settled on however many papers happened to be on disk at that
    instant (usually one) instead of waiting for all thirty.
    """
    from rpra.arxiv_corpus import fetch_corpus, missing_papers
    from rpra.sample_corpus import known_slugs as sample_known_slugs

    corpus_dir.mkdir(parents=True, exist_ok=True)

    # This is a switch, not an add: remove the 6 sample papers if switching
    # away from them, so the corpus does not silently end up as 36 mixed
    # papers instead of exactly the 30 requested.
    removed = _purge_known(corpus_dir, sample_known_slugs())
    if removed:
        logger.info("Removed %d sample paper(s) before loading the arXiv corpus", removed)

    outstanding = len(missing_papers(corpus_dir))

    with state.lock:
        state.running = True

    def announce(stage_status: str, message: str, details: dict) -> None:
        payload = {
            "type": "progress",
            "stage": "corpus_fetch",
            "doc_id": None,
            "status": stage_status,
            "message": message,
            "details": details,
            "elapsed_seconds": 0.0,
        }
        with state.lock:
            state.events.append(payload)
        _safe_broadcast(loop, payload)

    def worker() -> None:
        try:
            def report(index: int, total: int, slug: str, ok: bool) -> None:
                announce(
                    "running",
                    f"{'Fetched' if ok else 'Failed'} {slug} ({index}/{total})",
                    {"completed": index, "total": total},
                )

            manifest = fetch_corpus(corpus_dir, on_progress=report)
            counts = manifest["counts"]
            announce(
                "complete",
                (
                    f"arXiv corpus ready: {counts['available']}/{counts['requested']} "
                    f"papers ({counts['downloaded_this_run']} downloaded)"
                ),
                counts,
            )
        except Exception as exc:
            logger.exception("arXiv corpus fetch failed")
            announce("failed", f"Corpus fetch failed: {exc}", {})
        finally:
            with state.lock:
                state.running = False

    threading.Thread(target=worker, name="rpra-corpus-fetch", daemon=True).start()
    return outstanding


@app.post("/api/corpus/fetch-arxiv")
async def fetch_arxiv_corpus() -> dict[str, Any]:
    """
    Download the 30-paper arXiv evaluation corpus into the corpus directory.

    Runs in the background: arXiv asks for a few seconds between requests, so
    thirty papers take a couple of minutes. Progress is streamed over the same
    WebSocket the pipeline uses, because a download that long with no feedback
    is indistinguishable from a hang.
    """
    with state.lock:
        if state.running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Wait for the current job to finish.",
            )

    from rpra.arxiv_corpus import PAPERS

    corpus_dir = Path(current_settings.storage.corpus_input_path)
    # What still has to come over the network, which is what makes this slow.
    # It is not the same as what is missing from the corpus directory: a paper
    # held in the bundled dataset is absent here but costs only a file copy.
    loop = asyncio.get_running_loop()
    outstanding = _launch_arxiv_fetch(corpus_dir, loop)

    if outstanding:
        message = (
            f"Fetching {outstanding} paper(s) from arXiv. This takes a couple of "
            "minutes; progress appears in the status bar."
        )
    else:
        message = f"Loading all {len(PAPERS)} papers from the bundled dataset."

    return {
        "message": message,
        "to_download": outstanding,
        "total": len(PAPERS),
    }


# ----------------------------------------------------------------------
# Static UI
# ----------------------------------------------------------------------

STATIC_DIR = Path(__file__).parent / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")
