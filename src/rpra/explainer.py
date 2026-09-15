"""
RAG-Grounded LLM Explanation (Requirements 9 & 10).

Builds an Evidence Graph for each finding and generates plain-language
explanations grounded exclusively in the retrieved evidence.
"""

from __future__ import annotations

import logging
from typing import Any

from rpra.models import (
    Contradiction,
    EvidenceTrail,
    ResearchGap,
)

logger = logging.getLogger(__name__)

_CONTRADICTION_PROMPT = """You are a scientific analysis assistant.
Based ONLY on the evidence provided below, explain why the following two claims from different papers may contradict each other.
Cite specific sources inline using [DocID, Section, Page].
Do NOT invent any facts not present in the evidence.

Claim A (from {doc_a}): {claim_a}
Claim B (from {doc_b}): {claim_b}

Evidence:
{evidence_text}

Provide a concise explanation (3–5 sentences).
"""

_GAP_PROMPT = """You are a scientific analysis assistant.
Based ONLY on the evidence provided below, explain why the following represents an unexplored research gap.
Cite specific sources inline using [DocID, Section, Page].
Do NOT invent any facts not present in the evidence.

Gap Description: {description}

Evidence:
{evidence_text}

Provide a concise explanation (3–5 sentences).
"""


def _format_evidence(evidence_list: list[EvidenceTrail]) -> str:
    lines = []
    for i, e in enumerate(evidence_list, start=1):
        lines.append(
            f"[{i}] [{e.source_doc_id}, {e.section}, p.{e.page_number}]: "
            f'"{e.sentence_span}"'
        )
    return "\n".join(lines)


def explain_contradiction(
    contradiction: Contradiction,
    client: Any,   # openai.OpenAI
    model: str,
    temperature: float = 0.0,
) -> str:
    """Generate a grounded explanation for a contradiction."""
    if len(contradiction.evidence) < 2:
        contradiction.explanation = (
            "[low-confidence] Insufficient evidence to generate a reliable explanation."
        )
        return contradiction.explanation

    evidence_text = _format_evidence(contradiction.evidence)
    prompt = _CONTRADICTION_PROMPT.format(
        doc_a=contradiction.doc_id_a,
        claim_a=contradiction.claim_a,
        doc_b=contradiction.doc_id_b,
        claim_b=contradiction.claim_b,
        evidence_text=evidence_text,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        explanation = response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("Explanation generation failed for contradiction %s: %s", contradiction.id, exc)
        explanation = "[error] Explanation generation failed."

    contradiction.explanation = explanation
    return explanation


def explain_gap(
    gap: ResearchGap,
    client: Any,
    model: str,
    temperature: float = 0.0,
) -> str:
    """Generate a grounded explanation for a research gap."""
    if len(gap.evidence) < 2:
        gap.explanation = (
            "[low-confidence] Insufficient evidence to generate a reliable explanation."
        )
        return gap.explanation

    evidence_text = _format_evidence(gap.evidence)
    prompt = _GAP_PROMPT.format(
        description=gap.description,
        evidence_text=evidence_text,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        explanation = response.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("Explanation generation failed for gap %s: %s", gap.id, exc)
        explanation = "[error] Explanation generation failed."

    gap.explanation = explanation
    return explanation


def generate_explanations(
    contradictions: list[Contradiction],
    gaps: list[ResearchGap],
    llm_settings: Any,  # rpra.config.LLMConfig
) -> None:
    """
    Generate explanations for all confirmed findings in-place.
    Only processes findings with status=CONFIRMED / confirmed=True.
    """
    try:
        import os

        import openai
        api_key = os.environ.get(llm_settings.api_key_env, "")
        client = openai.OpenAI(api_key=api_key)
    except ImportError:
        logger.error("openai package not installed — skipping explanation generation.")
        return

    from rpra.models import ContradictionStatus

    for c in contradictions:
        if c.status == ContradictionStatus.CONFIRMED:
            explain_contradiction(c, client, llm_settings.model, llm_settings.temperature)

    for g in gaps:
        if g.confirmed:
            explain_gap(g, client, llm_settings.model, llm_settings.temperature)
