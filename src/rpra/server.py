"""
FastAPI Backend Server for Research Paper Relationship Analyzer.

Exposes REST APIs for document upload, pipeline execution, graph retrieval,
contradictions, research gaps, relationship scores, and WebSocket live progress streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from rpra.config import load_settings, Settings
from rpra.models import ProgressEvent, PipelineStageStatus
from rpra.pipeline import run_pipeline, PipelineResult

logger = logging.getLogger("rpra.server")

# ----------------------------------------------------------------------
# Application Setup
# ----------------------------------------------------------------------
app = FastAPI(
    title="Research Paper Relationship Analyzer API",
    description="Explainable Knowledge Graph Construction, Contradiction Detection & Research Gap Discovery API",
    version="0.1.0",
)

# Enable CORS for Vercel, local development, and external frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared in-memory state
latest_result: Optional[PipelineResult] = None
pipeline_running: bool = False
config_path: Path = Path("config.yaml")

try:
    current_settings: Settings = load_settings(config_path)
except Exception:
    current_settings = Settings()

# ----------------------------------------------------------------------
# WebSocket Connection Manager
# ----------------------------------------------------------------------
class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# ----------------------------------------------------------------------
# Pydantic Schemas for API
# ----------------------------------------------------------------------
class RunRequest(BaseModel):
    skip_extraction: bool = Field(False, description="Skip LLM extraction for demo mode")
    skip_explanation: bool = Field(False, description="Skip LLM explanation generation")

class WeightUpdateRequest(BaseModel):
    objective: float = Field(..., ge=0.0, le=1.0)
    methodology: float = Field(..., ge=0.0, le=1.0)
    dataset: float = Field(..., ge=0.0, le=1.0)
    results_metrics: float = Field(..., ge=0.0, le=1.0)
    citation: float = Field(..., ge=0.0, le=1.0)

# ----------------------------------------------------------------------
# REST Endpoints
# ----------------------------------------------------------------------
@app.get("/api/status")
async def get_status() -> Dict[str, Any]:
    """Get system status, current corpus info, and recent result summary."""
    corpus_dir = Path(current_settings.storage.corpus_input_path)
    pdf_files = list(corpus_dir.glob("*.pdf")) if corpus_dir.exists() else []

    kg_node_count = 0
    kg_edge_count = 0
    if latest_result and latest_result.knowledge_graph:
        kg_node_count = latest_result.knowledge_graph.node_count()
        kg_edge_count = latest_result.knowledge_graph.edge_count()

    return {
        "status": "running" if pipeline_running else "idle",
        "corpus_path": str(corpus_dir),
        "pdf_count": len(pdf_files),
        "pdf_files": [f.name for f in pdf_files],
        "has_results": latest_result is not None,
        "kg_nodes": kg_node_count,
        "kg_edges": kg_edge_count,
        "contradictions_count": len(latest_result.contradictions) if latest_result else 0,
        "gaps_count": len(latest_result.gaps) if latest_result else 0,
        "config": {
            "llm_provider": current_settings.llm.provider,
            "llm_model": current_settings.llm.model,
            "weights": current_settings.relationship_scoring.weights.model_dump(),
        },
    }

@app.post("/api/upload")
async def upload_pdf(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a PDF research paper into the corpus input directory."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported."
        )

    target_dir = Path(current_settings.storage.corpus_input_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / file.filename

    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)

    return {
        "filename": file.filename,
        "size_bytes": len(content),
        "path": str(target_path),
        "message": f"Successfully uploaded {file.filename} to corpus.",
    }

@app.post("/api/run")
async def trigger_pipeline(request: RunRequest) -> Dict[str, Any]:
    """Trigger the RPRA pipeline execution."""
    global latest_result, pipeline_running
    if pipeline_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pipeline execution is already in progress."
        )

    pipeline_running = True

    # Helper callback to stream progress over WebSockets
    def handle_progress(event: ProgressEvent) -> None:
        loop = asyncio.get_event_loop()
        event_dict = {
            "stage": event.stage,
            "status": event.status.value,
            "message": event.message,
            "details": event.details,
            "elapsed_seconds": event.elapsed_seconds,
        }
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(manager.broadcast(event_dict), loop)

    def worker() -> PipelineResult:
        global latest_result, pipeline_running
        try:
            res = run_pipeline(
                current_settings,
                on_progress=handle_progress,
                skip_extraction=request.skip_extraction,
                skip_explanation=request.skip_explanation,
            )
            latest_result = res
            return res
        finally:
            pipeline_running = False

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, worker)

    return {"message": "Pipeline execution started", "skip_extraction": request.skip_extraction}

@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming real-time progress events."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/graph")
async def get_knowledge_graph() -> Dict[str, Any]:
    """Return Knowledge Graph formatted for Cytoscape.js visualization."""
    if not latest_result or not latest_result.knowledge_graph:
        # Fallback: check if graph saved on disk
        graph_file = Path(current_settings.storage.graph_path)
        if graph_file.exists():
            from rpra.knowledge_graph import KnowledgeGraph
            kg = KnowledgeGraph.load(graph_file)
        else:
            return {"nodes": [], "edges": [], "bridge_entities": {}}
    else:
        kg = latest_result.knowledge_graph

    nodes = []
    edges = []

    for node_id, attrs in kg.graph.nodes(data=True):
        n_type = attrs.get("type", "unknown")
        label = attrs.get("label") or node_id
        nodes.append({
            "data": {
                "id": node_id,
                "label": label,
                "type": n_type,
                "doc_id": attrs.get("doc_id", ""),
                "is_bridge": node_id in (latest_result.bridge_entities if latest_result else {}),
            }
        })

    for source, target, key, attrs in kg.graph.edges(keys=True, data=True):
        rel_type = attrs.get("type", "relates")
        ev = attrs.get("evidence", {})
        edges.append({
            "data": {
                "id": f"{source}->{target}:{key}",
                "source": source,
                "target": target,
                "label": rel_type,
                "doc_id": ev.get("doc_id", ""),
                "section": ev.get("section", ""),
                "page": ev.get("page_number", 0),
                "sentence": ev.get("sentence_span", ""),
            }
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "bridge_entities": latest_result.bridge_entities if latest_result else {},
    }

@app.get("/api/contradictions")
async def get_contradictions() -> List[Dict[str, Any]]:
    """Return all detected contradictions with NLI stance scores & evidence trails."""
    if not latest_result:
        return []

    output = []
    for idx, c in enumerate(latest_result.contradictions):
        output.append({
            "id": f"contradiction-{idx+1}",
            "claim_1": {
                "text": c.claim_1.text,
                "doc_id": c.claim_1.doc_id,
                "section": c.claim_1.section,
                "page": c.claim_1.page_number,
                "sentence": c.claim_1.sentence_span,
            },
            "claim_2": {
                "text": c.claim_2.text,
                "doc_id": c.claim_2.doc_id,
                "section": c.claim_2.section,
                "page": c.claim_2.page_number,
                "sentence": c.claim_2.sentence_span,
            },
            "nli_label": c.nli_label,
            "nli_confidence": round(c.nli_confidence, 3),
            "signal_fusion_score": round(c.signal_fusion_score, 3),
            "confirmed": c.confirmed,
            "bridge_entity": c.bridge_entity,
            "methodology_similarity": round(c.methodology_similarity, 3),
            "dataset_compatible": c.dataset_compatible,
            "explanation": c.explanation.text if c.explanation else "No LLM explanation generated.",
            "evidence_edges_count": len(c.evidence_graph.edges) if c.evidence_graph else 0,
        })
    return output

@app.get("/api/gaps")
async def get_research_gaps() -> List[Dict[str, Any]]:
    """Return novelty-ranked research gaps with evidence trails."""
    if not latest_result:
        return []

    output = []
    for idx, g in enumerate(latest_result.gaps):
        output.append({
            "id": f"gap-{idx+1}",
            "entity": g.entity,
            "doc_1_id": g.doc_1_id,
            "doc_2_id": g.doc_2_id,
            "description": g.description,
            "novelty_score": round(g.novelty_score, 3),
            "connection_density": round(g.connection_density, 3),
            "explanation": g.explanation.text if g.explanation else "No LLM explanation generated.",
            "evidence_edges_count": len(g.evidence_graph.edges) if g.evidence_graph else 0,
        })
    return output

@app.get("/api/scores")
async def get_relationship_scores() -> List[Dict[str, Any]]:
    """Return pairwise document relationship scores across 5 dimensions."""
    if not latest_result:
        return []

    output = []
    for s in latest_result.scores:
        output.append({
            "doc_1_id": s.doc_1_id,
            "doc_2_id": s.doc_2_id,
            "composite_score": round(s.composite_score, 3),
            "components": {
                "objective": round(s.objective_similarity, 3),
                "methodology": round(s.methodology_similarity, 3),
                "dataset": round(s.dataset_overlap, 3),
                "results_metrics": round(s.results_metrics_similarity, 3),
                "citation": round(s.citation_overlap, 3),
            },
        })
    return output

@app.get("/api/documents")
async def get_documents() -> List[Dict[str, Any]]:
    """Return ingested documents with categories and segment stats."""
    if not latest_result:
        return []

    output = []
    for d in latest_result.documents:
        output.append({
            "doc_id": d.doc_id,
            "title": d.title,
            "category": d.category.value if d.category else "Unclassified",
            "category_confidence": round(d.category_confidence, 2),
            "total_pages": d.total_pages,
            "segments": list(d.segments.keys()),
        })
    return output

@app.post("/api/config/weights")
async def update_weights(req: WeightUpdateRequest) -> Dict[str, Any]:
    """Update relationship scoring weights with sum validation."""
    total = req.objective + req.methodology + req.dataset + req.results_metrics + req.citation
    if abs(total - 1.0) > 1e-4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Weights must sum to 1.0 (current sum: {round(total, 4)})"
        )

    w = current_settings.relationship_scoring.weights
    w.objective = req.objective
    w.methodology = req.methodology
    w.dataset = req.dataset
    w.results_metrics = req.results_metrics
    w.citation = req.citation

    return {
        "message": "Weights updated successfully",
        "weights": w.model_dump(),
    }

# ----------------------------------------------------------------------
# Static Files Mounting
# ----------------------------------------------------------------------
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        return FileResponse(static_path / "index.html")
