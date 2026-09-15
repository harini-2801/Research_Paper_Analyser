"""
Document Classification (Requirement 2).

Assigns each document one of three categories:
  - Experimental   – hypothesis, datasets, performance results
  - Survey/Review  – topic coverage, trends, chronology
  - Methodological – algorithms, architectures, complexity

Classification is keyword/heuristic-based (no model required) with a
confidence score.  The LLM can optionally be used for uncertain documents.
Emits ProgressEvents on completion.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

from rpra.models import (
    Document,
    DocumentCategory,
    PipelineStageStatus,
    ProgressEvent,
)

# ---------------------------------------------------------------------------
# Signal keyword banks
# ---------------------------------------------------------------------------

_EXPERIMENTAL_SIGNALS: list[str] = [
    r"\bhypothes[ie]s\b",
    r"\bbaseline\b",
    r"\baccuracy\b",
    r"\bf1[\s\-]?score\b",
    r"\bprecision\b",
    r"\brecall\b",
    r"\bbleu\b",
    r"\bauc\b",
    r"\bperformance\b",
    r"\bexperiment(al|s)?\b",
    r"\bdataset\b",
    r"\bbenchmark\b",
    r"\btrain(ing)?\s+set\b",
    r"\btest\s+set\b",
    r"\bvalidation\s+set\b",
    r"\bstate[\s\-]of[\s\-]the[\s\-]art\b",
]

_SURVEY_SIGNALS: list[str] = [
    r"\bsurvey\b",
    r"\breview\b",
    r"\btaxonom(y|ies)\b",
    r"\boverview\b",
    r"\bsystematic\s+review\b",
    r"\bliterature\s+review\b",
    r"\bcategoris(e|ation)\b",
    r"\bclassif(y|ication)\s+of\s+(?:methods|approaches|works)\b",
    r"\bcomparative\s+study\b",
    r"\bexisting\s+(approaches|methods|work)\b",
    r"\bchronolog(y|ical)\b",
]

_METHODOLOGICAL_SIGNALS: list[str] = [
    r"\balgorithm\b",
    r"\barchitecture\b",
    r"\bframework\b",
    r"\bnovel\s+(method|approach|technique)\b",
    r"\bwe\s+propose\b",
    r"\bwe\s+introduce\b",
    r"\bcomplexity\b",
    r"\bproof\b",
    r"\btheorem\b",
    r"\blemma\b",
    r"\bconvergence\b",
    r"\boptimis(ation|e)\b",
    r"\bgradient\b",
]

_COMPILED_EXP = [re.compile(p, re.IGNORECASE) for p in _EXPERIMENTAL_SIGNALS]
_COMPILED_SRV = [re.compile(p, re.IGNORECASE) for p in _SURVEY_SIGNALS]
_COMPILED_MTH = [re.compile(p, re.IGNORECASE) for p in _METHODOLOGICAL_SIGNALS]


def _score_text(text: str, patterns: list[re.Pattern]) -> int:
    """Count distinct pattern matches in *text*."""
    return sum(1 for p in patterns if p.search(text))


def classify_document(doc: Document) -> tuple[DocumentCategory, float]:
    """
    Assign a category and confidence score to *doc*.

    Returns
    -------
    category : DocumentCategory
    confidence : float  in [0, 1]
    """
    # Concatenate abstract + intro + conclusion for signal detection
    # (these sections carry the strongest categorical signals)
    relevant_sections = {"abstract", "introduction", "conclusion", "related_work", "results"}
    text_parts: list[str] = []
    for seg in doc.segments:
        if seg.section_type in relevant_sections:
            text_parts.append(seg.text)
    if not text_parts:
        # Fallback: use all segments
        text_parts = [seg.text for seg in doc.segments]

    combined = " ".join(text_parts)

    exp_score = _score_text(combined, _COMPILED_EXP)
    srv_score = _score_text(combined, _COMPILED_SRV)
    mth_score = _score_text(combined, _COMPILED_MTH)

    total = exp_score + srv_score + mth_score
    if total == 0:
        return DocumentCategory.EXPERIMENTAL, 0.0  # default with 0 confidence

    scores = {
        DocumentCategory.EXPERIMENTAL: exp_score,
        DocumentCategory.SURVEY_REVIEW: srv_score,
        DocumentCategory.METHODOLOGICAL: mth_score,
    }

    best_cat = max(scores, key=lambda k: scores[k])
    best_score = scores[best_cat]

    # Confidence: proportion of the winning category's raw score vs total
    confidence = round(best_score / total, 4)

    return best_cat, confidence


def classify_corpus(
    documents: list[Document],
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> list[Document]:
    """
    Classify every document in *documents* in-place and return the list.

    Parameters
    ----------
    documents:
        Documents from the ingestion stage (segments already populated).
    on_progress:
        Optional callback for progress events.

    Returns
    -------
    The same list, each document mutated with category and confidence.
    """

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    for doc in documents:
        start = time.perf_counter()
        try:
            category, confidence = classify_document(doc)

            # Requirement 2.4 — default to Experimental when confidence < 0.5
            if confidence < 0.5:
                flagged_cat = DocumentCategory.EXPERIMENTAL
                doc.metadata["needs_manual_review"] = True
            else:
                flagged_cat = category

            doc.category = flagged_cat
            doc.category_confidence = confidence

            elapsed = time.perf_counter() - start
            emit(
                ProgressEvent(
                    stage="classification",
                    doc_id=doc.id,
                    status=PipelineStageStatus.COMPLETE,
                    message=(
                        f"{doc.id} -> {doc.category.value} "
                        f"(confidence={confidence:.2f})"
                    ),
                    details={
                        "category": doc.category.value,
                        "confidence": confidence,
                        "flagged_for_review": doc.metadata.get("needs_manual_review", False),
                    },
                    elapsed_seconds=round(elapsed, 3),
                )
            )

        except Exception as exc:
            elapsed = time.perf_counter() - start
            doc.metadata["classification_error"] = str(exc)
            emit(
                ProgressEvent(
                    stage="classification",
                    doc_id=doc.id,
                    status=PipelineStageStatus.FAILED,
                    message=f"Classification failed for {doc.id}: {exc}",
                    elapsed_seconds=round(elapsed, 3),
                )
            )

    return documents
