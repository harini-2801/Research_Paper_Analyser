"""Tests for research gap discovery (Requirement 8)."""

from __future__ import annotations

from rpra.gap_discovery import discover_gaps
from rpra.knowledge_graph import build_knowledge_graph
from rpra.models import (
    Document,
    Entity,
    EntityType,
    RelationshipScore,
)


def entity(doc_id: str, etype: EntityType, text: str, section: str = "methodology") -> Entity:
    return Entity(
        doc_id=doc_id,
        entity_type=etype,
        text=text,
        section=section,
        page_number=2,
        sentence_span=f"The paper discusses {text} in detail across the study.",
    )


def build(entities, scores=None, bridges=None):
    docs = [
        Document(id=d, title=f"Paper {d.upper()}", file_path=f"{d}.pdf")
        for d in sorted({e.doc_id for e in entities})
    ]
    scores = scores or []
    kg = build_knowledge_graph(docs, entities, [], bridges or {}, scores)
    titles = {d.id: d.title for d in docs}
    return kg, docs, scores, titles


# ---------------------------------------------------------------------------
# Stated gaps
# ---------------------------------------------------------------------------


def test_stated_research_gap_is_surfaced():
    entities = [
        entity("a", EntityType.RESEARCH_GAP,
               "The interaction remains an open problem for the field.", "conclusion"),
    ]
    kg, _, scores, titles = build(entities)
    gaps = discover_gaps(kg, entities, scores, {}, title_index=titles)

    assert len(gaps) == 1
    assert "open problem" in gaps[0].description
    assert gaps[0].supporting_doc_ids == ["a"]
    assert gaps[0].evidence
    assert gaps[0].evidence[0].source_doc_title == "Paper A"


def test_stated_gap_outranks_a_stated_limitation():
    """A declared open problem is a stronger lead than a limitation."""
    entities = [
        entity("a", EntityType.RESEARCH_GAP, "This remains unexplored entirely.", "conclusion"),
        entity("b", EntityType.LIMITATION, "A limitation is the small sample.", "conclusion"),
    ]
    kg, _, scores, titles = build(entities)
    gaps = discover_gaps(kg, entities, scores, {}, title_index=titles)

    assert len(gaps) == 2
    assert gaps[0].novelty_score > gaps[1].novelty_score


def test_duplicate_statements_are_reported_once():
    text = "This combination remains unexplored in the literature."
    entities = [
        entity("a", EntityType.RESEARCH_GAP, text, "conclusion"),
        entity("b", EntityType.RESEARCH_GAP, text, "conclusion"),
    ]
    kg, _, scores, titles = build(entities)
    assert len(discover_gaps(kg, entities, scores, {}, title_index=titles)) == 1


# ---------------------------------------------------------------------------
# Absent pairings
# ---------------------------------------------------------------------------


def test_absent_pairing_between_established_concepts_is_found():
    # "contrastive learning" and "CIFAR-10" are each well attested, but never
    # appear in the same paper.
    entities = [
        entity("a", EntityType.METHODOLOGY, "contrastive learning"),
        entity("b", EntityType.METHODOLOGY, "contrastive learning"),
        entity("c", EntityType.DATASET, "CIFAR-10"),
        entity("d", EntityType.DATASET, "CIFAR-10"),
    ]
    kg, _, scores, titles = build(entities)
    gaps = discover_gaps(kg, entities, scores, {}, title_index=titles)

    descriptions = " ".join(g.description for g in gaps)
    assert "contrastive learning" in descriptions
    assert "CIFAR-10" in descriptions


def test_pairing_that_already_co_occurs_is_not_a_gap():
    entities = [
        entity("a", EntityType.METHODOLOGY, "contrastive learning"),
        entity("a", EntityType.DATASET, "CIFAR-10"),
        entity("b", EntityType.METHODOLOGY, "contrastive learning"),
        entity("b", EntityType.DATASET, "CIFAR-10"),
    ]
    kg, _, scores, titles = build(entities)
    gaps = discover_gaps(kg, entities, scores, {}, title_index=titles)

    assert not any("No paper in the corpus applies" in g.description for g in gaps)


def test_concept_seen_in_only_one_paper_is_not_established_enough():
    entities = [
        entity("a", EntityType.METHODOLOGY, "contrastive learning"),
        entity("b", EntityType.DATASET, "CIFAR-10"),
    ]
    kg, _, scores, titles = build(entities)
    gaps = discover_gaps(kg, entities, scores, {}, title_index=titles)

    assert not any("No paper in the corpus applies" in g.description for g in gaps)


# ---------------------------------------------------------------------------
# Weak connections
# ---------------------------------------------------------------------------


def test_shared_concept_with_weak_relationship_is_a_gap():
    entities = [
        entity("a", EntityType.DATASET, "CIFAR-10"),
        entity("b", EntityType.DATASET, "CIFAR-10"),
    ]
    scores = [RelationshipScore(doc_id_a="a", doc_id_b="b", composite_score=0.04)]
    kg, _, _, titles = build(entities, scores, {"cifar-10": ["a", "b"]})

    gaps = discover_gaps(
        kg, entities, scores, {"cifar-10": ["a", "b"]},
        weak_connection_threshold=0.2, title_index=titles,
    )
    weak = [g for g in gaps if "weakly related" in g.description]
    assert weak
    assert weak[0].supporting_doc_ids == ["a", "b"]


def test_strongly_related_papers_are_not_a_weak_connection():
    entities = [
        entity("a", EntityType.DATASET, "CIFAR-10"),
        entity("b", EntityType.DATASET, "CIFAR-10"),
    ]
    scores = [RelationshipScore(doc_id_a="a", doc_id_b="b", composite_score=0.85)]
    kg, _, _, titles = build(entities, scores, {"cifar-10": ["a", "b"]})

    gaps = discover_gaps(
        kg, entities, scores, {"cifar-10": ["a", "b"]},
        weak_connection_threshold=0.2, title_index=titles,
    )
    assert not any("weakly related" in g.description for g in gaps)


# ---------------------------------------------------------------------------
# General contract
# ---------------------------------------------------------------------------


def test_gaps_are_ranked_by_novelty_descending():
    entities = [
        entity("a", EntityType.RESEARCH_GAP, "Remains an open problem here.", "conclusion"),
        entity("b", EntityType.LIMITATION, "A limitation of the approach.", "conclusion"),
        entity("a", EntityType.METHODOLOGY, "contrastive learning"),
        entity("b", EntityType.METHODOLOGY, "contrastive learning"),
        entity("c", EntityType.DATASET, "CIFAR-10"),
        entity("d", EntityType.DATASET, "CIFAR-10"),
    ]
    kg, _, scores, titles = build(entities)
    gaps = discover_gaps(kg, entities, scores, {}, title_index=titles)

    novelties = [g.novelty_score for g in gaps]
    assert novelties == sorted(novelties, reverse=True)
    assert all(0.0 <= n <= 1.0 for n in novelties)


def test_empty_corpus_yields_no_gaps():
    kg, _, scores, titles = build([])
    assert discover_gaps(kg, [], scores, {}, title_index=titles) == []
