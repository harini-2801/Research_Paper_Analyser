"""
Orchestration: end-to-end pipeline runner.

Wires together all stages in the correct order, threads progress events
through the ProgressPanel, and returns a PipelineResult.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from rpra.classification import classify_corpus
from rpra.config import Settings
from rpra.contradiction import detect_contradictions
from rpra.explainer import generate_explanations
from rpra.gap_discovery import discover_gaps
from rpra.ingestion import ingest_corpus
from rpra.knowledge_graph import KnowledgeGraph, build_knowledge_graph
from rpra.models import (
    Contradiction,
    Document,
    Entity,
    ProgressEvent,
    PipelineStageStatus,
    Relation,
    RelationshipScore,
    ResearchGap,
)
from rpra.progress import ProgressPanel
from rpra.reporter import export_json, export_markdown
from rpra.scoring import score_corpus


@dataclass
class PipelineResult:
    documents: list[Document] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    bridge_entities: dict[str, list[str]] = field(default_factory=dict)
    scores: list[RelationshipScore] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    gaps: list[ResearchGap] = field(default_factory=list)
    knowledge_graph: KnowledgeGraph | None = None
    ingestion_errors: list[dict] = field(default_factory=list)
    report_json: Path | None = None
    report_md: Path | None = None
    elapsed_seconds: float = 0.0


def run_pipeline(
    settings: Settings,
    on_progress: Callable[[ProgressEvent], None] | None = None,
    skip_extraction: bool = False,   # set True to skip LLM calls (for testing)
    skip_explanation: bool = False,  # set True to skip explanation LLM calls
) -> PipelineResult:
    """
    Execute the full analysis pipeline.

    Parameters
    ----------
    settings:
        Validated settings loaded from config.yaml.
    on_progress:
        Optional callback for progress events.
    skip_extraction:
        When True, skips entity/relation extraction (useful for tests).
    skip_explanation:
        When True, skips LLM explanation generation.
    """
    start_total = time.perf_counter()
    result = PipelineResult()

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    # ------------------------------------------------------------------
    # Stage 1: Ingestion
    # ------------------------------------------------------------------
    emit(ProgressEvent(stage="pipeline", status=PipelineStageStatus.RUNNING,
                       message="Starting pipeline"))

    documents, errors = ingest_corpus(
        corpus_path=settings.storage.corpus_input_path,
        segment_types=settings.pipeline.segment_types,
        max_documents=settings.pipeline.max_documents,
        on_progress=on_progress,
    )
    result.documents = documents
    result.ingestion_errors = errors

    if not documents:
        emit(ProgressEvent(stage="pipeline", status=PipelineStageStatus.FAILED,
                           message="No documents ingested. Check corpus_input_path."))
        return result

    # ------------------------------------------------------------------
    # Stage 2: Classification
    # ------------------------------------------------------------------
    classify_corpus(documents, on_progress=on_progress)

    # ------------------------------------------------------------------
    # Stage 3: Entity & Relation Extraction
    # ------------------------------------------------------------------
    entities: list[Entity] = []
    relations: list[Relation] = []
    bridge_entities: dict[str, list[str]] = {}

    if not skip_extraction:
        from rpra.extraction import extract_corpus
        entities, relations, bridge_entities = extract_corpus(
            documents, settings.llm, on_progress=on_progress
        )
    else:
        emit(ProgressEvent(stage="extraction", status=PipelineStageStatus.COMPLETE,
                           message="Extraction skipped (skip_extraction=True)"))

    result.entities = entities
    result.relations = relations
    result.bridge_entities = bridge_entities

    # ------------------------------------------------------------------
    # Stage 4: Relationship Scoring
    # ------------------------------------------------------------------
    weights = settings.relationship_scoring.weights.model_dump()
    scores = score_corpus(documents, entities, weights=weights, on_progress=on_progress)
    result.scores = scores

    # ------------------------------------------------------------------
    # Stage 5: Knowledge Graph Construction
    # ------------------------------------------------------------------
    emit(ProgressEvent(stage="kg_construction", status=PipelineStageStatus.RUNNING,
                       message="Building Knowledge Graph"))

    kg = build_knowledge_graph(documents, entities, relations, bridge_entities, scores)
    result.knowledge_graph = kg

    graph_path = Path(settings.storage.graph_path)
    kg.save(graph_path)

    emit(ProgressEvent(
        stage="kg_construction",
        status=PipelineStageStatus.COMPLETE,
        message=(
            f"Knowledge Graph built: {kg.node_count()} nodes, "
            f"{kg.edge_count()} edges → {graph_path}"
        ),
        details={"nodes": kg.node_count(), "edges": kg.edge_count()},
    ))

    # ------------------------------------------------------------------
    # Stage 6: Contradiction Detection
    # ------------------------------------------------------------------
    if not skip_extraction:
        contradictions = detect_contradictions(
            documents, entities, scores, bridge_entities,
            nli_model_name=settings.nli.model,
            nli_confidence_threshold=settings.nli.contradiction_confidence_threshold,
            methodology_similarity_threshold=settings.nli.methodology_similarity_threshold,
            on_progress=on_progress,
        )
    else:
        contradictions = []
        emit(ProgressEvent(stage="contradiction_detection", status=PipelineStageStatus.COMPLETE,
                           message="Contradiction detection skipped (skip_extraction=True)"))
    result.contradictions = contradictions

    # ------------------------------------------------------------------
    # Stage 7: Gap Discovery
    # ------------------------------------------------------------------
    gaps = discover_gaps(
        kg, entities, scores, bridge_entities,
        weak_connection_threshold=settings.gap_discovery.weak_connection_threshold,
        on_progress=on_progress,
    )
    result.gaps = gaps

    # ------------------------------------------------------------------
    # Stage 8: LLM Explanations
    # ------------------------------------------------------------------
    if not skip_explanation and not skip_extraction:
        emit(ProgressEvent(stage="explanation", status=PipelineStageStatus.RUNNING,
                           message="Generating evidence-grounded explanations"))
        generate_explanations(contradictions, gaps, settings.llm)
        emit(ProgressEvent(stage="explanation", status=PipelineStageStatus.COMPLETE,
                           message="Explanations generated"))

    # ------------------------------------------------------------------
    # Stage 9: Export
    # ------------------------------------------------------------------
    emit(ProgressEvent(stage="export", status=PipelineStageStatus.RUNNING,
                       message="Exporting reports"))

    output_path = Path(settings.storage.output_path)
    report_json = export_json(documents, contradictions, gaps, scores, output_path)
    report_md = export_markdown(documents, contradictions, gaps, scores, output_path)
    result.report_json = report_json
    result.report_md = report_md

    emit(ProgressEvent(
        stage="export",
        status=PipelineStageStatus.COMPLETE,
        message=f"Reports saved → {report_json.name}, {report_md.name}",
        details={"json": str(report_json), "markdown": str(report_md)},
    ))

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    result.elapsed_seconds = round(time.perf_counter() - start_total, 2)
    emit(ProgressEvent(
        stage="pipeline",
        status=PipelineStageStatus.COMPLETE,
        message=f"Pipeline complete in {result.elapsed_seconds}s",
        elapsed_seconds=result.elapsed_seconds,
    ))

    return result
