"""
Research Gap Discovery (Requirement 8).

Requirement 8.2 asks for gaps derived from *weak or absent* connections in the
knowledge graph. Three complementary detectors run, because each finds a
different kind of gap and any one alone leaves most of the corpus unexamined:

`stated`
    Gaps the authors declare outright - sentences extracted as `research_gap`
    or `limitation` entities. The highest-precision source available, since a
    domain expert wrote them down.

`absent`
    Combinations that never occur. A methodology and a dataset that each appear
    in the corpus but never together in the same paper is an untried pairing.
    This is the *absent connection* case and the one that produces genuinely
    novel suggestions rather than restating what papers already say.

`weak`
    Papers that share a bridge entity yet score below the weak-connection
    threshold: the concept links them, but nothing else does, so the connection
    is under-explored.

Every gap carries an evidence trail back to verbatim sentences, and gaps are
ranked by novelty so the most under-explored appear first.
"""

from __future__ import annotations

import itertools
import logging
import time
from collections import Counter, defaultdict
from collections.abc import Callable

from rpra.knowledge_graph import KnowledgeGraph
from rpra.models import (
    Entity,
    EntityType,
    EvidenceTrail,
    PipelineStageStatus,
    ProgressEvent,
    RelationshipScore,
    ResearchGap,
)

logger = logging.getLogger(__name__)

# Entity types whose cross-product is worth testing for absent pairings.
_PAIRABLE_LEFT = (EntityType.METHODOLOGY, EntityType.MODEL)
_PAIRABLE_RIGHT = (EntityType.DATASET,)

# A concept must appear in at least this many documents before its absence
# elsewhere is meaningful. A term used once is not an established concept.
_MIN_DOC_SUPPORT = 2

_MAX_ABSENT_GAPS = 40
_MAX_GAPS_RETURNED = 60


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _index_by_doc(entities: list[Entity]) -> dict[str, list[Entity]]:
    index: dict[str, list[Entity]] = defaultdict(list)
    for entity in entities:
        index[entity.doc_id].append(entity)
    return index


def _concept_documents(
    entities: list[Entity], types: tuple[EntityType, ...]
) -> dict[str, set[str]]:
    """Map normalised concept text to the set of documents mentioning it."""
    mapping: dict[str, set[str]] = defaultdict(set)
    for entity in entities:
        if entity.entity_type in types:
            mapping[entity.text.lower().strip()].add(entity.doc_id)
    return mapping


def _display_forms(entities: list[Entity]) -> dict[str, str]:
    """
    Map each normalised concept back to how it is actually written.

    Matching is case-insensitive, but the normalised key is not what a reader
    should see - `CIFAR-10` must not surface in a report as `cifar-10`. The
    most frequent original spelling wins.
    """
    counts: dict[str, Counter] = defaultdict(Counter)
    for entity in entities:
        counts[entity.text.lower().strip()][entity.text.strip()] += 1
    return {key: spellings.most_common(1)[0][0] for key, spellings in counts.items()}


def _first_evidence(
    entities: list[Entity], concept: str, doc_id: str | None = None
) -> EvidenceTrail | None:
    """Find a verbatim sentence supporting *concept*, optionally within a document."""
    for entity in entities:
        if doc_id is not None and entity.doc_id != doc_id:
            continue
        if entity.text.lower().strip() != concept:
            continue
        if not entity.sentence_span.strip():
            continue
        return EvidenceTrail(
            source_doc_id=entity.doc_id,
            source_doc_title="",
            section=entity.section,
            page_number=entity.page_number,
            sentence_span=entity.sentence_span,
        )
    return None


def _already_addressed(concept: str, entities: list[Entity]) -> bool:
    """True when some paper already names *concept* as a gap or limitation."""
    needle = concept.lower()
    return any(
        entity.entity_type in (EntityType.RESEARCH_GAP, EntityType.LIMITATION)
        and needle in entity.text.lower()
        for entity in entities
    )


def _novelty_from_support(support: int, total_docs: int) -> float:
    """
    Novelty falls as more documents cover a concept.

    A pairing absent from a large corpus is more striking than one absent from a
    corpus of three papers, so support is normalised against corpus size.
    """
    if total_docs <= 1:
        return 0.5
    coverage = support / total_docs
    return round(min(max(1.0 - coverage, 0.0), 1.0), 4)


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------


def _stated_gaps(entities: list[Entity], title_index: dict[str, str]) -> list[ResearchGap]:
    """Surface gaps and limitations the authors stated explicitly."""
    gaps: list[ResearchGap] = []
    seen: set[str] = set()

    for entity in entities:
        if entity.entity_type not in (EntityType.RESEARCH_GAP, EntityType.LIMITATION):
            continue
        sentence = entity.sentence_span.strip() or entity.text.strip()
        key = sentence.lower()[:160]
        if not sentence or key in seen:
            continue
        seen.add(key)

        is_gap = entity.entity_type == EntityType.RESEARCH_GAP
        gaps.append(
            ResearchGap(
                description=sentence,
                supporting_doc_ids=[entity.doc_id],
                bridge_entities=[],
                # A declared open problem is a stronger lead than a limitation.
                novelty_score=0.75 if is_gap else 0.55,
                evidence=[
                    EvidenceTrail(
                        source_doc_id=entity.doc_id,
                        source_doc_title=title_index.get(entity.doc_id, ""),
                        section=entity.section,
                        page_number=entity.page_number,
                        sentence_span=sentence,
                    )
                ],
                confirmed=True,
                explanation=(
                    f"Stated directly in {entity.doc_id} "
                    f"({entity.section}, p.{entity.page_number}) as "
                    f"{'an open research gap' if is_gap else 'a limitation of the work'}."
                ),
            )
        )

    return gaps


def _absent_pairing_gaps(
    entities: list[Entity],
    total_docs: int,
    title_index: dict[str, str],
    display: dict[str, str],
) -> list[ResearchGap]:
    """
    Find established concept pairs that never co-occur in any single paper.

    Both halves must be well attested across the corpus; the gap is that nobody
    has combined them.
    """
    left_docs = _concept_documents(entities, _PAIRABLE_LEFT)
    right_docs = _concept_documents(entities, _PAIRABLE_RIGHT)

    left_terms = {t: d for t, d in left_docs.items() if len(d) >= _MIN_DOC_SUPPORT}
    right_terms = {t: d for t, d in right_docs.items() if len(d) >= _MIN_DOC_SUPPORT}

    candidates: list[tuple[float, str, str, set[str]]] = []

    for left, left_set in left_terms.items():
        for right, right_set in right_terms.items():
            if left == right:
                continue
            # Co-occurrence in any one document means the pairing has been tried.
            if left_set & right_set:
                continue
            novelty = _novelty_from_support(len(left_set | right_set), total_docs)
            candidates.append((novelty, left, right, left_set | right_set))

    # Rank by novelty, then by how well attested both halves are.
    candidates.sort(key=lambda c: (-c[0], -len(c[3])))

    gaps: list[ResearchGap] = []
    for novelty, left, right, docs in candidates[:_MAX_ABSENT_GAPS]:
        evidence = [
            trail
            for trail in (
                _first_evidence(entities, left),
                _first_evidence(entities, right),
            )
            if trail is not None
        ]
        if len(evidence) < 2:
            continue
        for trail in evidence:
            trail.source_doc_title = title_index.get(trail.source_doc_id, "")

        left_label = display.get(left, left)
        right_label = display.get(right, right)
        gaps.append(
            ResearchGap(
                description=(
                    f"No paper in the corpus applies '{left_label}' to '{right_label}'. "
                    f"Both are established in this literature - '{left_label}' appears in "
                    f"{len(left_terms[left])} paper(s) and '{right_label}' in "
                    f"{len(right_terms[right])} - but they are never combined, "
                    "leaving the pairing untested."
                ),
                supporting_doc_ids=sorted(docs),
                bridge_entities=[left_label, right_label],
                novelty_score=novelty,
                evidence=evidence,
                confirmed=True,
                explanation=(
                    "Absent connection in the knowledge graph: no document node "
                    f"links '{left_label}' and '{right_label}'."
                ),
            )
        )

    return gaps


def _weak_connection_gaps(
    entities: list[Entity],
    scores: list[RelationshipScore],
    bridge_entities: dict[str, list[str]],
    kg: KnowledgeGraph,
    weak_connection_threshold: float,
    title_index: dict[str, str],
    display: dict[str, str],
) -> list[ResearchGap]:
    """Papers sharing a concept but otherwise barely related."""
    score_index: dict[frozenset[str], float] = {
        frozenset([s.doc_id_a, s.doc_id_b]): s.composite_score for s in scores
    }

    gaps: list[ResearchGap] = []

    for concept, doc_ids in bridge_entities.items():
        unique_docs = sorted(set(doc_ids))
        if len(unique_docs) < 2:
            continue
        if _already_addressed(concept, entities):
            continue

        weak_pairs = [
            (a, b, score_index.get(frozenset([a, b]), 0.0))
            for a, b in itertools.combinations(unique_docs, 2)
            if score_index.get(frozenset([a, b]), 0.0) < weak_connection_threshold
        ]
        if not weak_pairs:
            continue

        involved = sorted({d for a, b, _ in weak_pairs for d in (a, b)})
        evidence = []
        for doc_id in involved:
            trail = _first_evidence(entities, concept, doc_id)
            if trail is not None:
                trail.source_doc_title = title_index.get(doc_id, "")
                evidence.append(trail)
        if len(evidence) < 2:
            continue

        mean_score = sum(s for _, _, s in weak_pairs) / len(weak_pairs)
        novelty = round(min(max(1.0 - mean_score, 0.0), 1.0), 4)

        label = display.get(concept, concept)
        gaps.append(
            ResearchGap(
                description=(
                    f"'{label}' appears in {len(involved)} papers, but they are "
                    f"otherwise weakly related (mean relationship score "
                    f"{mean_score:.2f}, below the {weak_connection_threshold:.2f} "
                    "threshold). The shared concept is not being developed jointly."
                ),
                supporting_doc_ids=involved,
                bridge_entities=[label],
                novelty_score=novelty,
                evidence=evidence,
                confirmed=True,
                explanation=(
                    f"Weak connection: {len(weak_pairs)} document pair(s) share "
                    f"'{label}' while scoring below the weak-connection threshold."
                ),
            )
        )

    return gaps


# ---------------------------------------------------------------------------
# Main discoverer
# ---------------------------------------------------------------------------


def discover_gaps(
    kg: KnowledgeGraph,
    all_entities: list[Entity],
    scores: list[RelationshipScore],
    bridge_entities: dict[str, list[str]],
    weak_connection_threshold: float = 0.20,
    title_index: dict[str, str] | None = None,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> list[ResearchGap]:
    """
    Discover and rank research gaps.

    Returns gaps sorted by novelty, highest first.
    """

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    start = time.perf_counter()
    emit(
        ProgressEvent(
            stage="gap_discovery",
            status=PipelineStageStatus.RUNNING,
            message="Scanning Knowledge Graph for weak and absent connections",
        )
    )

    titles = title_index or {}
    total_docs = len(kg.all_document_ids()) or len(_index_by_doc(all_entities))

    display = _display_forms(all_entities)

    stated = _stated_gaps(all_entities, titles)
    absent = _absent_pairing_gaps(all_entities, total_docs, titles, display)
    weak = _weak_connection_gaps(
        all_entities, scores, bridge_entities, kg,
        weak_connection_threshold, titles, display,
    )

    gaps = stated + absent + weak
    gaps.sort(key=lambda g: g.novelty_score, reverse=True)
    gaps = gaps[:_MAX_GAPS_RETURNED]

    emit(
        ProgressEvent(
            stage="gap_discovery",
            status=PipelineStageStatus.COMPLETE,
            message=(
                f"Gap discovery complete: {len(gaps)} gaps "
                f"({len(stated)} stated, {len(absent)} absent-pairing, {len(weak)} weak)"
            ),
            details={
                "total": len(gaps),
                "stated": len(stated),
                "absent_pairing": len(absent),
                "weak_connection": len(weak),
            },
            elapsed_seconds=round(time.perf_counter() - start, 2),
        )
    )

    return gaps
