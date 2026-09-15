"""
Orchestration: end-to-end pipeline runner.

Wires every stage together in dependency order, threads progress events through
to the caller, and returns a :class:`PipelineResult`.

Stage order and why it matters:

1.  ingestion            PDFs to segmented documents
2.  citations            reference lists parsed; feeds the citation score term
3.  classification       document category
4.  extraction           entities and relations (LLM or heuristic)
5.  embedding            entity vectors; three of five score terms need these
6.  scoring              pairwise relationship scores
7.  kg_construction      the knowledge graph
8.  contradiction        needs scores (methodology similarity) and entities
9.  gap_discovery        needs the graph and the scores
10. explanation          optional, LLM only
11. export               JSON + Markdown reports

Embedding must precede scoring: without vectors, the objective, methodology and
results dimensions all evaluate to zero and the composite score collapses to
the dataset-overlap term.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from rpra.citations import parse_corpus_references
from rpra.classification import classify_corpus
from rpra.config import Settings
from rpra.contradiction import detect_contradictions
from rpra.embeddings import EmbeddingBackend, embed_entities, save_embeddings
from rpra.explainer import generate_explanations
from rpra.gap_discovery import discover_gaps
from rpra.ingestion import ingest_corpus
from rpra.knowledge_graph import KnowledgeGraph, build_knowledge_graph
from rpra.models import (
    Contradiction,
    Document,
    Entity,
    PipelineStageStatus,
    ProgressEvent,
    Relation,
    RelationshipScore,
    ResearchGap,
)
from rpra.progress import safe_callback
from rpra.report_pdf import export_pdf
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
    report_pdf: Path | None = None
    graph_path: Path | None = None
    embedding_backend: str = ""
    extraction_backend: str = ""
    elapsed_seconds: float = 0.0

    def summary(self) -> dict:
        """Compact counts, used by the API and the CLI."""
        from rpra.models import ContradictionStatus

        return {
            "documents": len(self.documents),
            "entities": len(self.entities),
            "relations": len(self.relations),
            "bridge_entities": len(self.bridge_entities),
            "scored_pairs": len(self.scores),
            "contradictions": len(self.contradictions),
            "confirmed_contradictions": sum(
                1 for c in self.contradictions if c.status == ContradictionStatus.CONFIRMED
            ),
            "gaps": len(self.gaps),
            "kg_nodes": self.knowledge_graph.node_count() if self.knowledge_graph else 0,
            "kg_edges": self.knowledge_graph.edge_count() if self.knowledge_graph else 0,
            "embedding_backend": self.embedding_backend,
            "extraction_backend": self.extraction_backend,
            "elapsed_seconds": self.elapsed_seconds,
            "ingestion_errors": len(self.ingestion_errors),
        }


def run_pipeline(
    settings: Settings,
    on_progress: Callable[[ProgressEvent], None] | None = None,
    skip_extraction: bool = False,
    skip_explanation: bool = False,
    extraction_backend: str | None = None,
    use_nli: bool | None = None,
) -> PipelineResult:
    """
    Execute the full analysis pipeline.

    Parameters
    ----------
    settings:
        Validated settings loaded from config.yaml.
    on_progress:
        Optional callback receiving every :class:`ProgressEvent`.
    skip_extraction:
        Skip entity/relation extraction entirely. The graph will contain only
        document nodes, so this is for smoke tests rather than demos - use
        ``extraction_backend="heuristic"`` for a fast run with real output.
    skip_explanation:
        Skip LLM explanation generation.
    extraction_backend:
        Overrides ``settings.pipeline.extraction_backend``.
    use_nli:
        Overrides ``settings.pipeline.use_nli``.
    """
    start_total = time.perf_counter()
    result = PipelineResult()

    # Guard once, here, so no stage can be marked failed by a reporting error.
    on_progress = safe_callback(on_progress)

    backend_choice = extraction_backend or settings.pipeline.extraction_backend
    nli_enabled = settings.pipeline.use_nli if use_nli is None else use_nli

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    emit(
        ProgressEvent(
            stage="pipeline",
            status=PipelineStageStatus.RUNNING,
            message="Starting pipeline",
        )
    )

    # ------------------------------------------------------------------
    # Stage 1: Ingestion
    # ------------------------------------------------------------------
    documents, errors = ingest_corpus(
        corpus_path=settings.storage.corpus_input_path,
        segment_types=settings.pipeline.segment_types,
        max_documents=settings.pipeline.max_documents,
        on_progress=on_progress,
    )
    result.documents = documents
    result.ingestion_errors = errors

    if not documents:
        emit(
            ProgressEvent(
                stage="pipeline",
                status=PipelineStageStatus.FAILED,
                message=(
                    "No documents ingested. Check that "
                    f"'{settings.storage.corpus_input_path}' contains PDF files."
                ),
            )
        )
        result.elapsed_seconds = round(time.perf_counter() - start_total, 2)
        return result

    # ------------------------------------------------------------------
    # Stage 2: Reference parsing
    # ------------------------------------------------------------------
    emit(
        ProgressEvent(
            stage="citations",
            status=PipelineStageStatus.RUNNING,
            message="Parsing reference lists",
        )
    )
    citation_relations = parse_corpus_references(documents)

    # Record direct citations on metadata so scoring can treat them as maximal
    # bibliographic overlap without re-deriving them.
    for relation in citation_relations:
        source_doc = next((d for d in documents if d.id == relation.source_id), None)
        if source_doc is not None:
            cited = source_doc.metadata.setdefault("cites_doc_ids", [])
            if relation.target_id not in cited:
                cited.append(relation.target_id)

    total_refs = sum(len(d.metadata.get("cited_titles", [])) for d in documents)
    emit(
        ProgressEvent(
            stage="citations",
            status=PipelineStageStatus.COMPLETE,
            message=(
                f"Parsed {total_refs} references; "
                f"{len(citation_relations)} intra-corpus citations found"
            ),
            details={
                "references": total_refs,
                "intra_corpus_citations": len(citation_relations),
            },
        )
    )

    # ------------------------------------------------------------------
    # Stage 3: Classification
    # ------------------------------------------------------------------
    classify_corpus(documents, on_progress=on_progress)

    # ------------------------------------------------------------------
    # Stage 4: Entity & Relation Extraction
    # ------------------------------------------------------------------
    entities: list[Entity] = []
    relations: list[Relation] = []
    bridge_entities: dict[str, list[str]] = {}

    if skip_extraction:
        emit(
            ProgressEvent(
                stage="extraction",
                status=PipelineStageStatus.COMPLETE,
                message="Extraction skipped (skip_extraction=True)",
            )
        )
    else:
        from rpra.extraction import extract_corpus, resolve_backend

        result.extraction_backend = resolve_backend(backend_choice, settings.llm)
        entities, relations, bridge_entities = extract_corpus(
            documents,
            settings.llm,
            backend=backend_choice,
            on_progress=on_progress,
        )

    relations = relations + citation_relations
    result.entities = entities
    result.relations = relations
    result.bridge_entities = bridge_entities

    # ------------------------------------------------------------------
    # Stage 5: Embedding (Requirement 16)
    # ------------------------------------------------------------------
    backend: EmbeddingBackend | None = None
    if entities:
        backend = embed_entities(
            entities,
            documents=documents,
            model_name=settings.embedding.model,
            device=settings.embedding.device,
            batch_size=settings.embedding.batch_size,
            on_progress=on_progress,
        )
        result.embedding_backend = backend.kind
        save_embeddings(entities, settings.storage.embeddings_path)

    # ------------------------------------------------------------------
    # Stage 6: Relationship Scoring
    # ------------------------------------------------------------------
    weights = settings.relationship_scoring.weights.model_dump()
    result.scores = score_corpus(
        documents, entities, weights=weights, on_progress=on_progress
    )

    # ------------------------------------------------------------------
    # Stage 7: Knowledge Graph Construction
    # ------------------------------------------------------------------
    emit(
        ProgressEvent(
            stage="kg_construction",
            status=PipelineStageStatus.RUNNING,
            message="Building Knowledge Graph",
        )
    )

    kg = build_knowledge_graph(
        documents, entities, relations, bridge_entities, result.scores
    )
    result.knowledge_graph = kg

    graph_path = Path(settings.storage.graph_path)
    kg.save(graph_path)
    result.graph_path = graph_path

    emit(
        ProgressEvent(
            stage="kg_construction",
            status=PipelineStageStatus.COMPLETE,
            message=(
                f"Knowledge Graph built: {kg.node_count()} nodes, "
                f"{kg.edge_count()} edges -> {graph_path}"
            ),
            details={"nodes": kg.node_count(), "edges": kg.edge_count()},
        )
    )

    # ------------------------------------------------------------------
    # Stage 8: Contradiction Detection
    # ------------------------------------------------------------------
    if entities:
        result.contradictions = detect_contradictions(
            documents,
            entities,
            result.scores,
            bridge_entities,
            nli_model_name=settings.nli.model,
            nli_confidence_threshold=settings.nli.contradiction_confidence_threshold,
            methodology_similarity_threshold=settings.nli.methodology_similarity_threshold,
            use_nli=nli_enabled,
            on_progress=on_progress,
        )
    else:
        emit(
            ProgressEvent(
                stage="contradiction_detection",
                status=PipelineStageStatus.COMPLETE,
                message="Contradiction detection skipped (no entities extracted)",
            )
        )

    # ------------------------------------------------------------------
    # Stage 9: Gap Discovery
    # ------------------------------------------------------------------
    result.gaps = discover_gaps(
        kg,
        entities,
        result.scores,
        bridge_entities,
        weak_connection_threshold=settings.gap_discovery.weak_connection_threshold,
        title_index={d.id: d.title for d in documents},
        on_progress=on_progress,
    )

    # ------------------------------------------------------------------
    # Stage 10: LLM Explanations
    # ------------------------------------------------------------------
    if not skip_explanation and result.extraction_backend == "llm":
        emit(
            ProgressEvent(
                stage="explanation",
                status=PipelineStageStatus.RUNNING,
                message="Generating evidence-grounded explanations",
            )
        )
        generate_explanations(result.contradictions, result.gaps, settings.llm)
        emit(
            ProgressEvent(
                stage="explanation",
                status=PipelineStageStatus.COMPLETE,
                message="Explanations generated",
            )
        )
    else:
        emit(
            ProgressEvent(
                stage="explanation",
                status=PipelineStageStatus.COMPLETE,
                message="Explanation generation skipped (no LLM backend active)",
            )
        )

    # ------------------------------------------------------------------
    # Stage 11: Export
    # ------------------------------------------------------------------
    emit(
        ProgressEvent(
            stage="export",
            status=PipelineStageStatus.RUNNING,
            message="Exporting reports",
        )
    )

    # The reports quote the elapsed time, so it has to be set before they are
    # written rather than at the very end - otherwise every report says 0.0s.
    result.elapsed_seconds = round(time.perf_counter() - start_total, 2)

    output_path = Path(settings.storage.output_path)
    result.report_json = export_json(
        documents, result.contradictions, result.gaps, result.scores, output_path
    )
    result.report_md = export_markdown(
        documents, result.contradictions, result.gaps, result.scores, output_path
    )
    try:
        result.report_pdf = export_pdf(
            documents, result.contradictions, result.gaps, result.scores,
            output_path,
            summary=result.summary(),
            corpus_name=Path(settings.storage.corpus_input_path).name or "Corpus",
        )
    except Exception as exc:
        emit(
            ProgressEvent(
                stage="export",
                status=PipelineStageStatus.RUNNING,
                message=f"PDF report could not be generated: {exc}",
            )
        )

    emit(
        ProgressEvent(
            stage="export",
            status=PipelineStageStatus.COMPLETE,
            message=(
                "Reports saved -> "
                + ", ".join(
                    p.name for p in (result.report_json, result.report_md,
                                     result.report_pdf) if p
                )
            ),
            details={
                "json": str(result.report_json),
                "markdown": str(result.report_md),
                "pdf": str(result.report_pdf) if result.report_pdf else "",
            },
        )
    )

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    result.elapsed_seconds = round(time.perf_counter() - start_total, 2)
    emit(
        ProgressEvent(
            stage="pipeline",
            status=PipelineStageStatus.COMPLETE,
            message=f"Pipeline complete in {result.elapsed_seconds}s",
            details=result.summary(),
            elapsed_seconds=result.elapsed_seconds,
        )
    )

    return result
