"""
Core domain models (Pydantic dataclasses).

These are the canonical data structures shared across all pipeline stages.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DocumentCategory(str, Enum):
    EXPERIMENTAL = "Experimental"
    SURVEY_REVIEW = "Survey/Review"
    METHODOLOGICAL = "Methodological"
    UNKNOWN = "Unknown"


class EntityType(str, Enum):
    OBJECTIVE = "objective"
    METHODOLOGY = "methodology"
    DATASET = "dataset"
    MODEL = "model"
    EVALUATION_METRIC = "evaluation_metric"
    QUANTITATIVE_RESULT = "quantitative_result"
    LIMITATION = "limitation"
    RESEARCH_GAP = "research_gap"


class RelationType(str, Enum):
    USES = "uses"
    EVALUATES_ON = "evaluates-on"
    OUTPERFORMS = "outperforms"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    CITES = "cites"
    ADDRESSES = "addresses"
    IDENTIFIES_GAP_IN = "identifies-gap-in"


class NLILabel(str, Enum):
    ENTAILMENT = "entailment"
    CONTRADICTION = "contradiction"
    NEUTRAL = "neutral"


class ContradictionStatus(str, Enum):
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    REJECTED = "rejected"


class PipelineStageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Evidence Trail
# ---------------------------------------------------------------------------


class EvidenceTrail(BaseModel):
    """Provenance record attached to every relation and finding."""

    source_doc_id: str
    source_doc_title: str
    section: str
    page_number: int
    sentence_span: str  # verbatim sentence


# ---------------------------------------------------------------------------
# Segment and Document models
# ---------------------------------------------------------------------------


class Segment(BaseModel):
    """A single logical section extracted from a PDF."""

    id: UUID = Field(default_factory=uuid4)
    doc_id: str
    section_type: str  # abstract | introduction | methodology | …
    page_start: int
    page_end: int
    text: str


class Document(BaseModel):
    """A processed research paper."""

    id: str  # typically the stem of the filename
    title: str = ""
    file_path: str
    category: DocumentCategory = DocumentCategory.UNKNOWN
    category_confidence: float = 0.0
    segments: list[Segment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Entity and Relation models
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    """A typed concept extracted from a document segment."""

    id: UUID = Field(default_factory=uuid4)
    doc_id: str
    entity_type: EntityType
    text: str
    section: str
    page_number: int
    sentence_span: str
    embedding: list[float] = Field(default_factory=list)


class Relation(BaseModel):
    """A typed, directed edge between two entities or documents."""

    id: UUID = Field(default_factory=uuid4)
    source_id: str           # entity UUID or doc_id
    target_id: str           # entity UUID or doc_id
    relation_type: RelationType
    evidence: EvidenceTrail
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    is_cross_document: bool = False


# ---------------------------------------------------------------------------
# Relationship Score
# ---------------------------------------------------------------------------


class RelationshipScore(BaseModel):
    """Pairwise weighted relatedness score between two documents."""

    doc_id_a: str
    doc_id_b: str
    objective_similarity: float = Field(0.0, ge=0.0, le=1.0)
    methodology_similarity: float = Field(0.0, ge=0.0, le=1.0)
    dataset_overlap: float = Field(0.0, ge=0.0, le=1.0)
    results_metrics_similarity: float = Field(0.0, ge=0.0, le=1.0)
    citation_overlap: float = Field(0.0, ge=0.0, le=1.0)
    composite_score: float = Field(0.0, ge=0.0, le=1.0)
    weights_used: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Contradiction
# ---------------------------------------------------------------------------


class Contradiction(BaseModel):
    """A confirmed or unconfirmed contradiction between two claims."""

    id: UUID = Field(default_factory=uuid4)
    doc_id_a: str
    doc_id_b: str
    claim_a: str
    claim_b: str
    nli_label: NLILabel
    nli_confidence: float = Field(0.0, ge=0.0, le=1.0)
    dataset_compatible: bool = False
    metrics_comparable: bool = False
    methodology_similarity: float = Field(0.0, ge=0.0, le=1.0)
    status: ContradictionStatus = ContradictionStatus.UNCONFIRMED
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    evidence: list[EvidenceTrail] = Field(default_factory=list)
    explanation: str = ""


# ---------------------------------------------------------------------------
# Research Gap
# ---------------------------------------------------------------------------


class ResearchGap(BaseModel):
    """A candidate or confirmed research gap discovered from KG analysis."""

    id: UUID = Field(default_factory=uuid4)
    description: str
    supporting_doc_ids: list[str] = Field(default_factory=list)
    bridge_entities: list[str] = Field(default_factory=list)
    novelty_score: float = Field(0.0, ge=0.0, le=1.0)
    evidence: list[EvidenceTrail] = Field(default_factory=list)
    confirmed: bool = False
    explanation: str = ""


# ---------------------------------------------------------------------------
# Pipeline Progress Event
# ---------------------------------------------------------------------------


class ProgressEvent(BaseModel):
    """Emitted by pipeline stages to the Progress Panel."""

    stage: str
    doc_id: str | None = None
    status: PipelineStageStatus
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    elapsed_seconds: float = 0.0
