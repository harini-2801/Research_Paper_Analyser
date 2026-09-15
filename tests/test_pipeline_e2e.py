"""
End-to-end pipeline test over generated PDFs.

This is the test that would have caught the two largest defects in the project:
entities never receiving embeddings (which silently zeroed three of the five
scoring dimensions) and the API serialising against fields the models do not
have. Both only appear once real data flows through every stage.

Runs entirely offline: the heuristic extraction backend needs no API key, the
embedding backend falls back to TF-IDF when no model is cached, and NLI is off.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from rpra.config import Settings
from rpra.models import ContradictionStatus
from rpra.pipeline import run_pipeline

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


@pytest.fixture(scope="module")
def corpus(tmp_path_factory) -> Path:
    """Generate the sample PDF corpus once for the whole module."""
    pytest.importorskip("fitz", reason="PyMuPDF is required to build the corpus")
    from make_sample_corpus import PAPERS, build_pdf

    directory = tmp_path_factory.mktemp("papers")
    for paper in PAPERS:
        build_pdf(paper, directory)
    return directory


@pytest.fixture(scope="module")
def result(corpus, tmp_path_factory):
    output = tmp_path_factory.mktemp("output")

    settings = Settings()
    settings.storage.corpus_input_path = str(corpus)
    settings.storage.output_path = str(output)
    settings.storage.graph_path = str(output / "knowledge_graph.json")
    settings.storage.embeddings_path = str(output / "embeddings.npz")

    return run_pipeline(
        settings,
        extraction_backend="heuristic",
        use_nli=False,
        skip_explanation=True,
    )


# ---------------------------------------------------------------------------
# Ingestion and classification
# ---------------------------------------------------------------------------


def test_every_pdf_is_ingested_without_error(result):
    assert len(result.documents) == 6
    assert result.ingestion_errors == []


def test_documents_are_segmented_and_classified(result):
    for doc in result.documents:
        assert doc.segments, f"{doc.id} produced no segments"
        assert doc.category.value != ""
        assert 0.0 <= doc.category_confidence <= 1.0


def test_references_are_parsed(result):
    total = sum(len(d.metadata.get("cited_titles", [])) for d in result.documents)
    assert total > 0


def test_intra_corpus_citations_are_detected(result):
    cites = [r for r in result.relations if r.relation_type.value == "cites"]
    assert cites, "the sample corpus cross-cites; none were detected"
    assert all(r.is_cross_document for r in cites)


# ---------------------------------------------------------------------------
# Extraction and embedding
# ---------------------------------------------------------------------------


def test_entities_extracted_without_an_api_key(result):
    assert result.extraction_backend == "heuristic"
    assert len(result.entities) > 20


def test_every_entity_receives_an_embedding(result):
    """The regression that zeroed three of five scoring dimensions."""
    assert result.entities
    assert all(e.embedding for e in result.entities)
    widths = {len(e.embedding) for e in result.entities}
    assert len(widths) == 1


def test_bridge_entities_span_multiple_documents(result):
    assert result.bridge_entities
    for doc_ids in result.bridge_entities.values():
        assert len(set(doc_ids)) > 1


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def test_every_pair_is_scored(result):
    n = len(result.documents)
    assert len(result.scores) == n * (n - 1) // 2


def test_semantic_dimensions_are_not_all_zero(result):
    """Without embeddings these were structurally always 0.0."""
    assert any(s.objective_similarity > 0 for s in result.scores)
    assert any(s.methodology_similarity > 0 for s in result.scores)


def test_citation_dimension_contributes(result):
    assert any(s.citation_overlap > 0 for s in result.scores)


def test_scores_stay_in_range(result):
    for score in result.scores:
        assert 0.0 <= score.composite_score <= 1.0


def test_related_papers_outrank_unrelated_ones(result):
    """The two vision papers study the same thing; a vision/NLP pair does not."""
    def score_for(a: str, b: str) -> float:
        for s in result.scores:
            if {s.doc_id_a, s.doc_id_b} == {a, b}:
                return s.composite_score
        raise AssertionError(f"no score for {a} / {b}")

    same_field = score_for("vision_deep_residual_2021", "vision_residual_reproduction_2022")
    cross_field = score_for("vision_deep_residual_2021", "method_contrastive_retrieval_2023")
    assert same_field > cross_field


# ---------------------------------------------------------------------------
# Knowledge graph
# ---------------------------------------------------------------------------


def test_graph_contains_all_node_kinds(result):
    kg = result.knowledge_graph
    assert kg is not None

    kinds = {attrs.get("node_type") for _, attrs in kg.graph.nodes(data=True)}
    assert {"document", "entity", "bridge_entity"} <= kinds


def test_graph_round_trips_through_disk(result):
    """Requirement 18 - serialise and reload without losing nodes or edges."""
    from rpra.knowledge_graph import KnowledgeGraph

    reloaded = KnowledgeGraph.load(result.graph_path)
    assert reloaded.node_count() == result.knowledge_graph.node_count()
    assert reloaded.edge_count() == result.knowledge_graph.edge_count()


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------


def test_planted_contradictions_are_found(result):
    """Papers 1/2 and 3/4 disagree on a shared dataset and metric by construction."""
    confirmed = [c for c in result.contradictions if c.status == ContradictionStatus.CONFIRMED]
    assert confirmed, "no contradiction found in a corpus built to contain them"

    pairs = {frozenset([c.doc_id_a, c.doc_id_b]) for c in confirmed}
    expected = {
        frozenset(["vision_deep_residual_2021", "vision_residual_reproduction_2022"]),
        frozenset(["nlp_attention_reading_2021", "nlp_efficient_transformers_2023"]),
    }
    assert pairs & expected


def test_contradictions_carry_a_two_sided_evidence_trail(result):
    for contradiction in result.contradictions:
        assert len(contradiction.evidence) == 2
        assert contradiction.evidence[0].source_doc_id == contradiction.doc_id_a
        assert contradiction.evidence[1].source_doc_id == contradiction.doc_id_b
        for trail in contradiction.evidence:
            assert trail.sentence_span.strip()
            assert trail.page_number >= 0


def test_research_gaps_are_found_and_ranked(result):
    assert result.gaps
    novelties = [g.novelty_score for g in result.gaps]
    assert novelties == sorted(novelties, reverse=True)


def test_stated_gaps_are_traceable_to_a_sentence(result):
    assert any(g.evidence and g.evidence[0].sentence_span for g in result.gaps)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def test_reports_are_written(result):
    assert result.report_json.exists()
    assert result.report_md.exists()
    assert result.report_md.read_text(encoding="utf-8").startswith("# Research Paper")


def test_summary_is_self_consistent(result):
    summary = result.summary()
    assert summary["documents"] == len(result.documents)
    assert summary["entities"] == len(result.entities)
    assert summary["gaps"] == len(result.gaps)
    assert summary["kg_nodes"] == result.knowledge_graph.node_count()
    assert summary["elapsed_seconds"] > 0


def test_empty_corpus_fails_cleanly(tmp_path):
    settings = Settings()
    settings.storage.corpus_input_path = str(tmp_path / "empty")
    settings.storage.output_path = str(tmp_path / "out")

    outcome = run_pipeline(settings, extraction_backend="heuristic", use_nli=False)
    assert outcome.documents == []
    assert outcome.knowledge_graph is None
