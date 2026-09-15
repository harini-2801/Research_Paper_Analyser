"""Tests for core domain models and round-trip serialisation (Requirement 18)."""


from rpra.knowledge_graph import KnowledgeGraph, build_knowledge_graph
from rpra.models import (
    Document,
    Entity,
    EntityType,
    EvidenceTrail,
    Relation,
    RelationType,
)

# ---------------------------------------------------------------------------
# Entity round-trip
# ---------------------------------------------------------------------------


def test_entity_round_trip():
    """Entity serialises and deserialises without data loss (Req 18.4)."""
    entity = Entity(
        doc_id="paper_a",
        entity_type=EntityType.DATASET,
        text="SQuAD 2.0",
        section="experiments",
        page_number=5,
        sentence_span="We evaluate on SQuAD 2.0.",
    )
    dumped = entity.model_dump()
    restored = Entity(**dumped)
    assert restored.text == entity.text
    assert restored.entity_type == entity.entity_type
    assert restored.doc_id == entity.doc_id


# ---------------------------------------------------------------------------
# KnowledgeGraph round-trip
# ---------------------------------------------------------------------------


def _make_minimal_kg() -> KnowledgeGraph:
    doc_a = Document(id="paper_a", title="Paper A", file_path="/a.pdf")
    doc_b = Document(id="paper_b", title="Paper B", file_path="/b.pdf")

    entity = Entity(
        doc_id="paper_a",
        entity_type=EntityType.METHODOLOGY,
        text="BERT fine-tuning",
        section="methodology",
        page_number=3,
        sentence_span="We fine-tune BERT on the target task.",
    )

    trail = EvidenceTrail(
        source_doc_id="paper_a",
        source_doc_title="Paper A",
        section="methodology",
        page_number=3,
        sentence_span="We fine-tune BERT on the target task.",
    )
    relation = Relation(
        source_id=str(entity.id),
        target_id="paper_b",
        relation_type=RelationType.EXTENDS,
        evidence=trail,
    )

    kg = build_knowledge_graph(
        documents=[doc_a, doc_b],
        entities=[entity],
        relations=[relation],
        bridge_entities={"BERT fine-tuning": ["paper_a", "paper_b"]},
    )
    return kg


def test_kg_round_trip(tmp_path):
    """KG serialises and deserialises preserving node/edge counts (Req 18.3)."""
    kg = _make_minimal_kg()
    original_nodes = kg.node_count()
    original_edges = kg.edge_count()

    path = tmp_path / "kg.json"
    kg.save(path)

    restored = KnowledgeGraph.load(path)
    assert restored.node_count() == original_nodes
    assert restored.edge_count() == original_edges


def test_kg_query_document_exists():
    kg = _make_minimal_kg()
    node = kg.get_node("paper_a")
    assert node is not None
    assert node["node_type"] == "document"
    assert node["title"] == "Paper A"


def test_kg_bridge_entity():
    kg = _make_minimal_kg()
    bridge_node = kg.get_node("bridge::BERT fine-tuning")
    assert bridge_node is not None

    # The lookup must work whichever casing the caller uses.
    expected = ["paper_a", "paper_b"]
    assert sorted(kg.documents_sharing_bridge_entity("BERT fine-tuning")) == expected
    assert sorted(kg.documents_sharing_bridge_entity("bert fine-tuning")) == expected


def test_kg_all_document_ids():
    kg = _make_minimal_kg()
    doc_ids = kg.all_document_ids()
    assert "paper_a" in doc_ids
    assert "paper_b" in doc_ids
