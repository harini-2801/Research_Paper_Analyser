"""
Contradiction Detection (Requirement 7).

Uses NLI (Natural Language Inference) combined with contextual signals
(dataset compatibility, metric comparability, methodology similarity)
to identify genuine scientific contradictions.

Key rule (Req 7.4): A contradiction is CONFIRMED only when:
  NLI label == "contradiction"
  AND (datasets are compatible OR metrics are directly comparable)
  AND methodology_similarity >= threshold (default 0.3)
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from rpra.models import (
    Contradiction,
    ContradictionStatus,
    Document,
    Entity,
    EntityType,
    EvidenceTrail,
    NLILabel,
    ProgressEvent,
    PipelineStageStatus,
    RelationshipScore,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Candidate claim extraction
# ---------------------------------------------------------------------------


def _extract_claims(entities: list[Entity]) -> list[Entity]:
    """Return entities that carry testable claims (results + methodology)."""
    claim_types = {
        EntityType.QUANTITATIVE_RESULT,
        EntityType.METHODOLOGY,
        EntityType.OBJECTIVE,
    }
    return [e for e in entities if e.entity_type in claim_types]


def _datasets_compatible(entities_a: list[Entity], entities_b: list[Entity]) -> bool:
    """True when the two documents share at least one dataset name."""
    ds_a = {e.text.lower().strip() for e in entities_a if e.entity_type == EntityType.DATASET}
    ds_b = {e.text.lower().strip() for e in entities_b if e.entity_type == EntityType.DATASET}
    return bool(ds_a & ds_b)


def _metrics_comparable(entities_a: list[Entity], entities_b: list[Entity]) -> bool:
    """True when both documents use at least one common evaluation metric name."""
    met_a = {e.text.lower().strip() for e in entities_a if e.entity_type == EntityType.EVALUATION_METRIC}
    met_b = {e.text.lower().strip() for e in entities_b if e.entity_type == EntityType.EVALUATION_METRIC}
    return bool(met_a & met_b)


# ---------------------------------------------------------------------------
# NLI inference
# ---------------------------------------------------------------------------


def _run_nli(
    premise: str,
    hypothesis: str,
    nli_pipeline,  # HuggingFace pipeline or compatible
) -> tuple[NLILabel, float]:
    """
    Run NLI and return (label, confidence).
    Handles both three-class (entailment/neutral/contradiction) models.
    """
    try:
        result = nli_pipeline(
            f"{premise} [SEP] {hypothesis}",
            truncation=True,
            max_length=512,
        )
        # result is typically a list of {"label": ..., "score": ...}
        if isinstance(result, list) and result:
            # Support both direct list and nested list formats
            items = result[0] if isinstance(result[0], list) else result
            best = max(items, key=lambda x: x["score"])
            raw_label = best["label"].upper()
            score = float(best["score"])

            if "CONTRADICTION" in raw_label:
                return NLILabel.CONTRADICTION, score
            elif "ENTAIL" in raw_label:
                return NLILabel.ENTAILMENT, score
            else:
                return NLILabel.NEUTRAL, score
    except Exception as exc:  # noqa: BLE001
        logger.warning("NLI inference failed: %s", exc)

    return NLILabel.NEUTRAL, 0.0


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------


def detect_contradictions(
    documents: list[Document],
    entities: list[Entity],
    scores: list[RelationshipScore],
    bridge_entities: dict[str, list[str]],
    nli_model_name: str = "cross-encoder/nli-deberta-v3-small",
    nli_confidence_threshold: float = 0.60,
    methodology_similarity_threshold: float = 0.30,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> list[Contradiction]:
    """
    Detect contradictions across documents.

    Candidates are document pairs that:
    - share a bridge entity, OR
    - have a composite relationship_score > 0.4

    Returns a list of Contradiction objects (confirmed + unconfirmed).
    """
    try:
        from transformers import pipeline as hf_pipeline
        nli_pipe = hf_pipeline(
            "text-classification",
            model=nli_model_name,
            top_k=None,
            device=-1,  # CPU; change to 0 for GPU
        )
    except Exception as exc:
        logger.error("Failed to load NLI model '%s': %s", nli_model_name, exc)
        return []

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    # Index entities by doc_id
    entity_index: dict[str, list[Entity]] = {}
    for e in entities:
        entity_index.setdefault(e.doc_id, []).append(e)

    # Build candidate pair set
    candidate_pairs: set[tuple[str, str]] = set()

    # Pairs linked by bridge entities
    for _text, doc_ids in bridge_entities.items():
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                a, b = sorted([doc_ids[i], doc_ids[j]])
                candidate_pairs.add((a, b))

    # Pairs with high relationship score
    for s in scores:
        if s.composite_score > 0.4:
            a, b = sorted([s.doc_id_a, s.doc_id_b])
            candidate_pairs.add((a, b))

    emit(
        ProgressEvent(
            stage="contradiction_detection",
            status=PipelineStageStatus.RUNNING,
            message=f"Evaluating {len(candidate_pairs)} candidate document pairs",
        )
    )

    contradictions: list[Contradiction] = []

    for pair_a, pair_b in candidate_pairs:
        ents_a = entity_index.get(pair_a, [])
        ents_b = entity_index.get(pair_b, [])

        claims_a = _extract_claims(ents_a)
        claims_b = _extract_claims(ents_b)

        if not claims_a or not claims_b:
            continue

        ds_compat = _datasets_compatible(ents_a, ents_b)
        met_compat = _metrics_comparable(ents_a, ents_b)

        # Find the methodology similarity from scoring results
        meth_sim = 0.0
        for s in scores:
            if {s.doc_id_a, s.doc_id_b} == {pair_a, pair_b}:
                meth_sim = s.methodology_similarity
                break

        # Cross-compare claim pairs (limit to top 5 claims each to bound cost)
        for claim_a in claims_a[:5]:
            for claim_b in claims_b[:5]:
                if claim_a.text.lower().strip() == claim_b.text.lower().strip():
                    continue  # identical claims — not a contradiction

                nli_label, nli_conf = _run_nli(claim_a.sentence_span, claim_b.sentence_span, nli_pipe)

                if nli_label != NLILabel.CONTRADICTION:
                    continue

                # Determine status (Req 7.4 and 7.6)
                if (
                    nli_conf >= nli_confidence_threshold
                    and (ds_compat or met_compat)
                    and meth_sim >= methodology_similarity_threshold
                ):
                    status = ContradictionStatus.CONFIRMED
                    confidence = nli_conf
                elif nli_conf >= 0.4:
                    status = ContradictionStatus.UNCONFIRMED
                    confidence = nli_conf
                else:
                    continue

                evidence = [
                    EvidenceTrail(
                        source_doc_id=claim_a.doc_id,
                        source_doc_title="",
                        section=claim_a.section,
                        page_number=claim_a.page_number,
                        sentence_span=claim_a.sentence_span,
                    ),
                    EvidenceTrail(
                        source_doc_id=claim_b.doc_id,
                        source_doc_title="",
                        section=claim_b.section,
                        page_number=claim_b.page_number,
                        sentence_span=claim_b.sentence_span,
                    ),
                ]

                contradictions.append(
                    Contradiction(
                        doc_id_a=pair_a,
                        doc_id_b=pair_b,
                        claim_a=claim_a.text,
                        claim_b=claim_b.text,
                        nli_label=nli_label,
                        nli_confidence=round(nli_conf, 4),
                        dataset_compatible=ds_compat,
                        metrics_comparable=met_compat,
                        methodology_similarity=round(meth_sim, 4),
                        status=status,
                        confidence=round(confidence, 4),
                        evidence=evidence,
                    )
                )

    confirmed = sum(1 for c in contradictions if c.status == ContradictionStatus.CONFIRMED)
    unconfirmed = sum(1 for c in contradictions if c.status == ContradictionStatus.UNCONFIRMED)

    emit(
        ProgressEvent(
            stage="contradiction_detection",
            status=PipelineStageStatus.COMPLETE,
            message=(
                f"Contradiction detection complete: "
                f"{confirmed} confirmed, {unconfirmed} unconfirmed"
            ),
            details={"confirmed": confirmed, "unconfirmed": unconfirmed},
        )
    )

    return contradictions
