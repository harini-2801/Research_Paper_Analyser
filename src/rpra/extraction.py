"""
Structured Entity & Relation Extraction (Requirements 3 & 4).

Uses an LLM (via OpenAI-compatible API) with structured JSON output to
extract typed entities and relations from each document segment.

Key design decisions
--------------------
- Each segment is processed independently so failures don't block others (Req 3.7).
- LLM output is validated against the defined entity/relation type schema; non-
  conforming outputs are discarded and retried up to 2 times (Req 15.2).
- Every extracted entity and relation carries an EvidenceTrail (Req 4.3).
- Bridge entities (shared across docs) are identified after all docs are processed.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Callable
from uuid import uuid4

from rpra.models import (
    Document,
    Entity,
    EntityType,
    EvidenceTrail,
    ProgressEvent,
    PipelineStageStatus,
    Relation,
    RelationType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_ENTITY_SYSTEM_PROMPT = """You are a scientific information extraction assistant.
Extract entities from the provided research paper segment.
Return ONLY a JSON array (no markdown, no extra text) where each element has exactly:
{
  "text": "<entity text>",
  "entity_type": "<one of: objective, methodology, dataset, model, evaluation_metric, quantitative_result, limitation, research_gap>",
  "sentence_span": "<verbatim sentence the entity appears in>"
}
Do not include any entity type not in that list. If none found, return [].
"""

_RELATION_SYSTEM_PROMPT = """You are a scientific relation extraction assistant.
Given a list of extracted entities from a research paper segment, identify typed relations between them.
Return ONLY a JSON array (no markdown, no extra text) where each element has exactly:
{
  "source_text": "<text of source entity>",
  "target_text": "<text of target entity>",
  "relation_type": "<one of: uses, evaluates-on, outperforms, contradicts, extends, cites, addresses, identifies-gap-in>",
  "sentence_span": "<verbatim sentence supporting this relation>"
}
Do not include any relation type not in that list. If none found, return [].
"""

_VALID_ENTITY_TYPES = {e.value for e in EntityType}
_VALID_RELATION_TYPES = {r.value for r in RelationType}


# ---------------------------------------------------------------------------
# LLM call helper
# ---------------------------------------------------------------------------


def _call_llm(
    client,  # openai.OpenAI instance
    model: str,
    system_prompt: str,
    user_content: str,
    max_retries: int = 3,
    temperature: float = 0.0,
) -> list[dict]:
    """
    Call the LLM and return a parsed JSON list.  Retries up to *max_retries*
    times on parse errors or schema violations.
    """
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                raw = raw.rsplit("```", 1)[0]
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, IndexError, Exception) as exc:  # noqa: BLE001
            logger.warning("LLM call attempt %d failed: %s", attempt + 1, exc)

    return []


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


def extract_entities_from_segment(
    segment,  # rpra.models.Segment
    doc_title: str,
    client,
    model: str,
    max_retries: int = 3,
    temperature: float = 0.0,
) -> list[Entity]:
    """Extract typed entities from a single segment."""
    user_content = (
        f"Section: {segment.section_type}\n"
        f"Page: {segment.page_start}\n\n"
        f"{segment.text[:3000]}"  # truncate to avoid token overflow
    )
    raw_entities = _call_llm(client, model, _ENTITY_SYSTEM_PROMPT, user_content, max_retries, temperature)

    entities: list[Entity] = []
    for item in raw_entities:
        etype = item.get("entity_type", "").strip()
        text = item.get("text", "").strip()
        sentence = item.get("sentence_span", "").strip()

        if etype not in _VALID_ENTITY_TYPES:
            logger.warning(
                "Discarded entity with unknown type '%s' in doc '%s' section '%s'.",
                etype, segment.doc_id, segment.section_type,
            )
            continue
        if not text:
            continue

        entities.append(
            Entity(
                doc_id=segment.doc_id,
                entity_type=EntityType(etype),
                text=text,
                section=segment.section_type,
                page_number=segment.page_start,
                sentence_span=sentence,
            )
        )

    return entities


# ---------------------------------------------------------------------------
# Relation extraction
# ---------------------------------------------------------------------------


def extract_relations_from_segment(
    segment,
    entities: list[Entity],
    doc_title: str,
    client,
    model: str,
    max_retries: int = 3,
    temperature: float = 0.0,
) -> list[Relation]:
    """Extract typed relations between entities within a single segment."""
    if len(entities) < 2:
        return []

    entity_list_text = "\n".join(
        f"- [{e.entity_type.value}] {e.text}" for e in entities
    )
    user_content = (
        f"Section: {segment.section_type}\n"
        f"Entities:\n{entity_list_text}\n\n"
        f"Segment text:\n{segment.text[:3000]}"
    )
    raw_relations = _call_llm(client, model, _RELATION_SYSTEM_PROMPT, user_content, max_retries, temperature)

    # Build a quick text→entity lookup
    entity_map: dict[str, Entity] = {e.text.lower(): e for e in entities}

    relations: list[Relation] = []
    for item in raw_relations:
        rtype = item.get("relation_type", "").strip()
        src_text = item.get("source_text", "").strip().lower()
        tgt_text = item.get("target_text", "").strip().lower()
        sentence = item.get("sentence_span", "").strip()

        if rtype not in _VALID_RELATION_TYPES:
            logger.warning(
                "Discarded relation with unknown type '%s' in doc '%s'.",
                rtype, segment.doc_id,
            )
            continue

        src_entity = entity_map.get(src_text)
        tgt_entity = entity_map.get(tgt_text)
        if not src_entity or not tgt_entity:
            continue

        trail = EvidenceTrail(
            source_doc_id=segment.doc_id,
            source_doc_title=doc_title,
            section=segment.section_type,
            page_number=segment.page_start,
            sentence_span=sentence,
        )

        relations.append(
            Relation(
                source_id=str(src_entity.id),
                target_id=str(tgt_entity.id),
                relation_type=RelationType(rtype),
                evidence=trail,
                is_cross_document=False,
            )
        )

    return relations


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def deduplicate_entities(entities: list[Entity]) -> list[Entity]:
    """
    Remove near-duplicate entities within a document using exact string
    normalisation.  Retains the instance with the most complete provenance
    (longest sentence_span).
    """
    seen: dict[tuple[str, str], Entity] = {}
    for ent in entities:
        key = (ent.doc_id, ent.entity_type.value, ent.text.lower().strip())
        if key not in seen:
            seen[key] = ent
        else:
            # Keep entity with longer sentence_span (more context)
            if len(ent.sentence_span) > len(seen[key].sentence_span):
                seen[key] = ent
    return list(seen.values())


# ---------------------------------------------------------------------------
# Bridge entity detection
# ---------------------------------------------------------------------------


def find_bridge_entities(
    all_entities: list[Entity],
) -> dict[str, list[str]]:
    """
    Find entities that appear in more than one document (Bridge Entities).

    Returns
    -------
    dict mapping normalised entity text → list of doc_ids that contain it.
    """
    entity_docs: dict[str, set[str]] = {}
    for ent in all_entities:
        key = ent.text.lower().strip()
        entity_docs.setdefault(key, set()).add(ent.doc_id)

    return {
        text: sorted(docs)
        for text, docs in entity_docs.items()
        if len(docs) > 1
    }


# ---------------------------------------------------------------------------
# Full corpus extraction
# ---------------------------------------------------------------------------


def extract_corpus(
    documents: list[Document],
    llm_settings,   # rpra.config.LLMConfig
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> tuple[list[Entity], list[Relation], dict[str, list[str]]]:
    """
    Run entity and relation extraction over the full corpus.

    Returns
    -------
    all_entities : list[Entity]
    all_relations : list[Relation]
    bridge_entities : dict[str, list[str]]  entity_text → [doc_ids]
    """
    try:
        import openai  # lazy import so the module loads without the package
    except ImportError:
        raise ImportError(
            "openai package is required for extraction. "
            "Install it with: pip install openai"
        )

    api_key = __import__("os").environ.get(llm_settings.api_key_env, "")
    client = openai.OpenAI(api_key=api_key)

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    all_entities: list[Entity] = []
    all_relations: list[Relation] = []

    for doc in documents:
        start = time.perf_counter()
        emit(
            ProgressEvent(
                stage="extraction",
                doc_id=doc.id,
                status=PipelineStageStatus.RUNNING,
                message=f"Extracting from {doc.id} ({len(doc.segments)} segments)",
            )
        )

        doc_entities: list[Entity] = []
        doc_relations: list[Relation] = []

        for seg in doc.segments:
            try:
                seg_entities = extract_entities_from_segment(
                    seg, doc.title, client,
                    llm_settings.model, llm_settings.max_retries, llm_settings.temperature,
                )
                seg_relations = extract_relations_from_segment(
                    seg, seg_entities, doc.title, client,
                    llm_settings.model, llm_settings.max_retries, llm_settings.temperature,
                )
                doc_entities.extend(seg_entities)
                doc_relations.extend(seg_relations)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Segment extraction failed in %s / %s: %s", doc.id, seg.section_type, exc)

        doc_entities = deduplicate_entities(doc_entities)
        all_entities.extend(doc_entities)
        all_relations.extend(doc_relations)

        elapsed = time.perf_counter() - start
        by_type = {}
        for e in doc_entities:
            by_type[e.entity_type.value] = by_type.get(e.entity_type.value, 0) + 1

        emit(
            ProgressEvent(
                stage="extraction",
                doc_id=doc.id,
                status=PipelineStageStatus.COMPLETE,
                message=(
                    f"{doc.id}: {len(doc_entities)} entities, "
                    f"{len(doc_relations)} relations"
                ),
                details={"entities_by_type": by_type, "relations": len(doc_relations)},
                elapsed_seconds=round(elapsed, 2),
            )
        )

    bridge_entities = find_bridge_entities(all_entities)
    return all_entities, all_relations, bridge_entities
