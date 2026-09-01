"""
Research Gap Discovery (Requirement 8).

Identifies candidate research gaps by analysing weak or absent connections
in the Knowledge Graph between entity clusters.  Each candidate is validated
against existing "research_gap" / "limitation" entities before being confirmed.
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from rpra.knowledge_graph import KnowledgeGraph
from rpra.models import (
    Entity,
    EntityType,
    EvidenceTrail,
    ProgressEvent,
    PipelineStageStatus,
    RelationshipScore,
    ResearchGap,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _already_addressed(
    bridge_entity_text: str,
    all_entities: list[Entity],
) -> bool:
    """
    Return True if any existing entity of type research_gap or limitation
    mentions the bridge entity concept.
    """
    needle = bridge_entity_text.lower()
    for e in all_entities:
        if e.entity_type in (EntityType.RESEARCH_GAP, EntityType.LIMITATION):
            if needle in e.text.lower():
                return True
    return False


def _novelty_score(
    bridge_entity_text: str,
    kg: KnowledgeGraph,
    scores: list[RelationshipScore],
) -> float:
    """
    Compute a novelty score for a candidate gap:
      - Lower density of bridge connections → higher novelty
      - We invert and normalise connection density.
    """
    connected_docs = kg.documents_sharing_bridge_entity(bridge_entity_text)
    num_connections = len(connected_docs)

    # More documents share this bridge → lower novelty (already well-covered)
    if num_connections == 0:
        return 1.0
    # Soft inverse: novelty = 1 / (1 + connections)
    raw_novelty = 1.0 / (1.0 + num_connections)

    # Penalise if the connected doc pairs already have high relationship scores
    avg_score = 0.0
    pair_count = 0
    for i in range(len(connected_docs)):
        for j in range(i + 1, len(connected_docs)):
            a, b = connected_docs[i], connected_docs[j]
            for s in scores:
                if {s.doc_id_a, s.doc_id_b} == {a, b}:
                    avg_score += s.composite_score
                    pair_count += 1
                    break

    if pair_count > 0:
        avg_score /= pair_count
        # If avg pair score is already high, the gap is less novel
        raw_novelty *= (1.0 - avg_score * 0.5)

    return round(min(max(raw_novelty, 0.0), 1.0), 4)


# ---------------------------------------------------------------------------
# Main discoverer
# ---------------------------------------------------------------------------


def discover_gaps(
    kg: KnowledgeGraph,
    all_entities: list[Entity],
    scores: list[RelationshipScore],
    bridge_entities: dict[str, list[str]],
    weak_connection_threshold: float = 0.20,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> list[ResearchGap]:
    """
    Discover and rank research gaps.

    Parameters
    ----------
    kg:
        The constructed Knowledge Graph.
    all_entities:
        All extracted entities (used for validation).
    scores:
        Pairwise relationship scores.
    bridge_entities:
        Bridge entity text → list of doc_ids.
    weak_connection_threshold:
        Composite score below which a connection is considered weak (Req 8.2).
    on_progress:
        Optional progress callback.

    Returns
    -------
    Ranked list of confirmed :class:`ResearchGap` objects.
    """

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    emit(
        ProgressEvent(
            stage="gap_discovery",
            status=PipelineStageStatus.RUNNING,
            message="Scanning Knowledge Graph for weak/absent connections",
        )
    )

    # Score index for quick lookup
    score_index: dict[frozenset, float] = {}
    for s in scores:
        score_index[frozenset([s.doc_id_a, s.doc_id_b])] = s.composite_score

    gaps: list[ResearchGap] = []

    for bridge_text, doc_ids in bridge_entities.items():
        if len(doc_ids) < 2:
            continue

        # Check if the connection between docs sharing this bridge is weak
        weak_pairs = []
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                pair_key = frozenset([doc_ids[i], doc_ids[j]])
                pair_score = score_index.get(pair_key, 0.0)
                if pair_score < weak_connection_threshold:
                    weak_pairs.append((doc_ids[i], doc_ids[j], pair_score))

        if not weak_pairs:
            continue

        # Validate: not already addressed by explicit gap/limitation entities
        if _already_addressed(bridge_text, all_entities):
            continue

        # Build evidence
        evidence: list[EvidenceTrail] = []
        all_supporting_docs = set()
        for a, b, _ in weak_pairs:
            all_supporting_docs.update([a, b])

        for doc_id in all_supporting_docs:
            doc_entities = [e for e in all_entities if e.doc_id == doc_id]
            for e in doc_entities:
                if bridge_text.lower() in e.text.lower():
                    evidence.append(
                        EvidenceTrail(
                            source_doc_id=doc_id,
                            source_doc_title="",
                            section=e.section,
                            page_number=e.page_number,
                            sentence_span=e.sentence_span,
                        )
                    )
                    break  # one evidence per doc is sufficient

        novelty = _novelty_score(bridge_text, kg, scores)

        description = (
            f"The concept '{bridge_text}' appears across "
            f"{len(all_supporting_docs)} paper(s) but the relationships "
            f"between these papers are weak (avg score < {weak_connection_threshold}), "
            f"suggesting an under-explored connection."
        )

        gaps.append(
            ResearchGap(
                description=description,
                supporting_doc_ids=sorted(all_supporting_docs),
                bridge_entities=[bridge_text],
                novelty_score=novelty,
                evidence=evidence,
                confirmed=True,
            )
        )

    # Rank by novelty score descending
    gaps.sort(key=lambda g: g.novelty_score, reverse=True)

    emit(
        ProgressEvent(
            stage="gap_discovery",
            status=PipelineStageStatus.COMPLETE,
            message=f"Gap discovery complete: {len(gaps)} confirmed research gaps",
            details={"confirmed_gaps": len(gaps)},
        )
    )

    return gaps
