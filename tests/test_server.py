"""
Tests for the FastAPI backend.

The original suite only ever exercised the empty-result path, so every handler
passed while being written against fields the models do not have. These tests
populate a real result first, which is the only way the serialisers get run.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rpra import server
from rpra.knowledge_graph import build_knowledge_graph
from rpra.models import (
    Contradiction,
    ContradictionStatus,
    Document,
    DocumentCategory,
    Entity,
    EntityType,
    EvidenceTrail,
    NLILabel,
    RelationshipScore,
    ResearchGap,
    Segment,
)
from rpra.pipeline import PipelineResult

client = TestClient(server.app)


@pytest.fixture
def empty_state():
    server.state.result = None
    server.state.running = False
    server.state.last_error = None
    yield
    server.state.result = None


@pytest.fixture
def populated_state():
    """A small but structurally complete result, exercising every serialiser."""
    doc_a = Document(
        id="paper_a",
        title="Residual Networks Revisited",
        file_path="paper_a.pdf",
        category=DocumentCategory.EXPERIMENTAL,
        category_confidence=0.82,
        segments=[
            Segment(doc_id="paper_a", section_type="results", page_start=4, page_end=5, text="x"),
        ],
        metadata={"reference_count": 3, "cited_titles": ["some prior work"]},
    )
    doc_b = Document(
        id="paper_b",
        title="A Reproduction Study",
        file_path="paper_b.pdf",
        category=DocumentCategory.METHODOLOGICAL,
        category_confidence=0.41,
        segments=[
            Segment(doc_id="paper_b", section_type="results", page_start=6, page_end=6, text="y"),
        ],
        metadata={"needs_manual_review": True, "reference_count": 2},
    )

    entities = [
        Entity(doc_id="paper_a", entity_type=EntityType.DATASET, text="CIFAR-10",
               section="experiments", page_number=4, sentence_span="We use CIFAR-10."),
        Entity(doc_id="paper_b", entity_type=EntityType.DATASET, text="CIFAR-10",
               section="experiments", page_number=6, sentence_span="Evaluated on CIFAR-10."),
    ]

    score = RelationshipScore(
        doc_id_a="paper_a", doc_id_b="paper_b",
        objective_similarity=0.6, methodology_similarity=0.55,
        dataset_overlap=1.0, results_metrics_similarity=0.4,
        citation_overlap=0.2, composite_score=0.61,
        weights_used={"objective": 0.25, "methodology": 0.25, "dataset": 0.2,
                      "results_metrics": 0.2, "citation": 0.1},
    )

    bridges = {"cifar-10": ["paper_a", "paper_b"]}

    contradiction = Contradiction(
        doc_id_a="paper_a", doc_id_b="paper_b",
        claim_a="Reaches 94.2% accuracy on CIFAR-10.",
        claim_b="Reaches 87.1% accuracy on CIFAR-10.",
        nli_label=NLILabel.CONTRADICTION, nli_confidence=0.71,
        dataset_compatible=True, metrics_comparable=True,
        methodology_similarity=0.55, status=ContradictionStatus.CONFIRMED,
        confidence=0.71,
        evidence=[
            EvidenceTrail(source_doc_id="paper_a", source_doc_title="Residual Networks Revisited",
                          section="results", page_number=4,
                          sentence_span="Reaches 94.2% accuracy on CIFAR-10."),
            EvidenceTrail(source_doc_id="paper_b", source_doc_title="A Reproduction Study",
                          section="results", page_number=6,
                          sentence_span="Reaches 87.1% accuracy on CIFAR-10."),
        ],
    )

    gap = ResearchGap(
        description="No paper applies contrastive learning to CIFAR-10.",
        supporting_doc_ids=["paper_a", "paper_b"],
        bridge_entities=["contrastive learning", "CIFAR-10"],
        novelty_score=0.67, confirmed=True,
        evidence=[
            EvidenceTrail(source_doc_id="paper_a", source_doc_title="Residual Networks Revisited",
                          section="methodology", page_number=3,
                          sentence_span="We use contrastive learning."),
        ],
    )

    kg = build_knowledge_graph([doc_a, doc_b], entities, [], bridges, [score])

    server.state.result = PipelineResult(
        documents=[doc_a, doc_b], entities=entities, relations=[],
        bridge_entities=bridges, scores=[score],
        contradictions=[contradiction], gaps=[gap],
        knowledge_graph=kg, embedding_backend="tfidf",
        extraction_backend="heuristic", elapsed_seconds=3.5,
    )
    server.state.running = False
    yield server.state.result
    server.state.result = None


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------


def test_status_works_before_any_run(empty_state):
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "idle"
    assert body["has_results"] is False
    assert "weights" in body["config"]


@pytest.mark.parametrize(
    "path", ["/api/documents", "/api/contradictions", "/api/gaps", "/api/scores", "/api/entities"]
)
def test_collection_endpoints_return_empty_lists(empty_state, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Populated state - the paths that used to raise
# ---------------------------------------------------------------------------


def test_status_reports_the_run_summary(populated_state):
    body = client.get("/api/status").json()
    assert body["has_results"] is True
    assert body["summary"]["documents"] == 2
    assert body["summary"]["extraction_backend"] == "heuristic"
    assert body["kg_nodes"] > 0


def test_documents_serialise_with_real_model_fields(populated_state):
    body = client.get("/api/documents").json()
    assert len(body) == 2

    first = body[0]
    assert first["doc_id"] == "paper_a"
    assert first["title"] == "Residual Networks Revisited"
    assert first["category"] == "Experimental"
    assert first["total_pages"] == 5
    assert first["segments"] == ["results"]
    assert first["reference_count"] == 3
    assert body[1]["needs_review"] is True


def test_graph_uses_the_knowledge_graph_attribute_names(populated_state):
    body = client.get("/api/graph").json()
    assert body["nodes"] and body["edges"]

    kinds = {n["data"]["node_type"] for n in body["nodes"]}
    assert "document" in kinds and "entity" in kinds and "bridge_entity" in kinds

    labels = {n["data"]["label"] for n in body["nodes"]}
    assert "Residual Networks Revisited" in labels  # documents label by title
    assert "CIFAR-10" in labels                     # entities label by text

    edge_kinds = {e["data"]["edge_type"] for e in body["edges"]}
    assert "contains" in edge_kinds
    assert "relationship_score" in edge_kinds
    assert all("unknown" != e["data"]["edge_type"] for e in body["edges"])


def test_contradictions_expose_claims_and_evidence(populated_state):
    body = client.get("/api/contradictions").json()
    assert len(body) == 1

    item = body[0]
    assert item["doc_a"] == "paper_a"
    assert item["claim_a"].startswith("Reaches 94.2%")
    assert item["confirmed"] is True
    assert item["status"] == "confirmed"
    assert item["dataset_compatible"] is True
    assert len(item["evidence"]) == 2
    assert item["evidence"][0]["sentence_span"]


def test_confirmed_only_filter(populated_state):
    assert len(client.get("/api/contradictions?confirmed_only=true").json()) == 1

    server.state.result.contradictions[0].status = ContradictionStatus.UNCONFIRMED
    assert client.get("/api/contradictions?confirmed_only=true").json() == []
    assert len(client.get("/api/contradictions").json()) == 1


def test_gaps_expose_novelty_and_evidence(populated_state):
    body = client.get("/api/gaps").json()
    assert len(body) == 1
    assert body[0]["novelty_score"] == 0.67
    assert body[0]["bridge_entities"] == ["contrastive learning", "CIFAR-10"]
    assert body[0]["evidence"][0]["section"] == "methodology"


def test_scores_expose_all_five_dimensions(populated_state):
    body = client.get("/api/scores").json()
    assert len(body) == 1

    components = body[0]["components"]
    assert set(components) == {
        "objective", "methodology", "dataset", "results_metrics", "citation"
    }
    assert body[0]["doc_a"] == "paper_a"
    assert body[0]["composite_score"] == 0.61


def test_entities_can_be_filtered_by_document(populated_state):
    assert len(client.get("/api/entities").json()) == 2
    filtered = client.get("/api/entities?doc_id=paper_a").json()
    assert len(filtered) == 1
    assert filtered[0]["doc_id"] == "paper_a"


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------


def test_valid_weights_are_accepted():
    payload = {"objective": 0.2, "methodology": 0.3, "dataset": 0.2,
               "results_metrics": 0.2, "citation": 0.1}
    response = client.post("/api/config/weights", json=payload)
    assert response.status_code == 200
    assert response.json()["weights"]["methodology"] == 0.3


def test_weights_that_do_not_sum_to_one_are_rejected():
    payload = {"objective": 0.5, "methodology": 0.5, "dataset": 0.5,
               "results_metrics": 0.5, "citation": 0.5}
    response = client.post("/api/config/weights", json=payload)
    assert response.status_code == 400
    assert "Weights must sum to 1.0" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Upload, report, static
# ---------------------------------------------------------------------------


def test_non_pdf_upload_is_rejected():
    response = client.post(
        "/api/upload", files={"file": ("notes.txt", b"hello", "text/plain")}
    )
    assert response.status_code == 400


def test_file_without_pdf_header_is_rejected():
    response = client.post(
        "/api/upload", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")}
    )
    assert response.status_code == 400
    assert "%PDF" in response.json()["detail"]


def test_deleting_an_absent_paper_is_a_404():
    assert client.delete("/api/corpus/does-not-exist.pdf").status_code == 404


def test_report_rejects_an_unknown_format():
    assert client.get("/api/report?fmt=pdf").status_code == 400


def test_index_page_is_served():
    response = client.get("/")
    assert response.status_code == 200
    assert "Research Paper Relationship Analyzer" in response.text


def test_static_assets_are_served():
    for path in ["/static/css/rpra.css", "/static/js/app.js"]:
        assert client.get(path).status_code == 200


def test_run_is_rejected_while_one_is_in_progress():
    server.state.running = True
    try:
        response = client.post("/api/run", json={"extraction_backend": "heuristic"})
        assert response.status_code == 409
    finally:
        server.state.running = False


def test_run_rejects_an_unknown_backend():
    response = client.post("/api/run", json={"extraction_backend": "magic"})
    assert response.status_code == 422
