"""
Results Export and Reporting (Requirement 17).

Exports findings to JSON and Markdown formats.
"""

from __future__ import annotations

import json
from pathlib import Path

from rpra.models import (
    Contradiction,
    ContradictionStatus,
    Document,
    RelationshipScore,
    ResearchGap,
)


def _contradiction_to_dict(c: Contradiction) -> dict:
    return {
        "id": str(c.id),
        "doc_a": c.doc_id_a,
        "doc_b": c.doc_id_b,
        "claim_a": c.claim_a,
        "claim_b": c.claim_b,
        "status": c.status.value,
        "nli_confidence": c.nli_confidence,
        "methodology_similarity": c.methodology_similarity,
        "dataset_compatible": c.dataset_compatible,
        "metrics_comparable": c.metrics_comparable,
        "confidence": c.confidence,
        "explanation": c.explanation,
        "evidence": [e.model_dump() for e in c.evidence],
    }


def _gap_to_dict(g: ResearchGap) -> dict:
    return {
        "id": str(g.id),
        "description": g.description,
        "novelty_score": g.novelty_score,
        "supporting_docs": g.supporting_doc_ids,
        "bridge_entities": g.bridge_entities,
        "explanation": g.explanation,
        "evidence": [e.model_dump() for e in g.evidence],
    }


def export_json(
    documents: list[Document],
    contradictions: list[Contradiction],
    gaps: list[ResearchGap],
    scores: list[RelationshipScore],
    output_path: str | Path,
    top_n_scores: int = 20,
) -> Path:
    """Export all findings to a single JSON report file."""
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    report_file = output_path / "report.json"

    confirmed_contradictions = [c for c in contradictions if c.status == ContradictionStatus.CONFIRMED]
    top_scores = sorted(scores, key=lambda s: s.composite_score, reverse=True)[:top_n_scores]

    report = {
        "summary": {
            "total_documents": len(documents),
            "confirmed_contradictions": len(confirmed_contradictions),
            "unconfirmed_contradictions": sum(
                1 for c in contradictions if c.status == ContradictionStatus.UNCONFIRMED
            ),
            "confirmed_gaps": len(gaps),
            "relationship_pairs_scored": len(scores),
        },
        "confirmed_contradictions": [_contradiction_to_dict(c) for c in confirmed_contradictions],
        "research_gaps": [_gap_to_dict(g) for g in gaps],
        "top_related_pairs": [
            {
                "doc_a": s.doc_id_a,
                "doc_b": s.doc_id_b,
                "composite_score": s.composite_score,
            }
            for s in top_scores
        ],
    }

    with report_file.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    return report_file


def export_markdown(
    documents: list[Document],
    contradictions: list[Contradiction],
    gaps: list[ResearchGap],
    scores: list[RelationshipScore],
    output_path: str | Path,
    top_n_scores: int = 20,
) -> Path:
    """Export findings to a human-readable Markdown report."""
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    md_file = output_path / "report.md"

    confirmed = [c for c in contradictions if c.status == ContradictionStatus.CONFIRMED]
    top_scores = sorted(scores, key=lambda s: s.composite_score, reverse=True)[:top_n_scores]

    lines = [
        "# Research Paper Relationship Analyzer — Report",
        "",
        "## Summary",
        f"- **Documents analysed:** {len(documents)}",
        f"- **Confirmed contradictions:** {len(confirmed)}",
        f"- **Confirmed research gaps:** {len(gaps)}",
        f"- **Document pairs scored:** {len(scores)}",
        "",
    ]

    # ---- Top related pairs ------------------------------------------------
    lines += ["## Top Related Document Pairs", ""]
    if top_scores:
        lines += ["| Doc A | Doc B | Composite Score |", "|---|---|---|"]
        for s in top_scores:
            lines.append(f"| {s.doc_id_a} | {s.doc_id_b} | {s.composite_score:.3f} |")
    else:
        lines.append("_No pairs scored._")
    lines.append("")

    # ---- Contradictions ---------------------------------------------------
    lines += ["## Confirmed Contradictions", ""]
    if confirmed:
        for i, c in enumerate(confirmed, start=1):
            lines += [
                f"### Contradiction {i}",
                f"- **Papers:** [{c.doc_id_a}] vs [{c.doc_id_b}]",
                f"- **Claim A:** {c.claim_a}",
                f"- **Claim B:** {c.claim_b}",
                f"- **Confidence:** {c.confidence:.2f}",
                f"- **Explanation:** {c.explanation or '_Not yet generated._'}",
                "",
            ]
            for e in c.evidence:
                lines.append(
                    f"  > [{e.source_doc_id}, {e.section}, p.{e.page_number}] "
                    f'"{e.sentence_span}"'
                )
            lines.append("")
    else:
        lines.append("_No confirmed contradictions found._")
    lines.append("")

    # ---- Research Gaps ----------------------------------------------------
    lines += ["## Research Gaps", ""]
    if gaps:
        for i, g in enumerate(gaps, start=1):
            lines += [
                f"### Gap {i} (novelty={g.novelty_score:.2f})",
                f"{g.description}",
                f"- **Supporting papers:** {', '.join(g.supporting_doc_ids)}",
                f"- **Bridge concepts:** {', '.join(g.bridge_entities)}",
                f"- **Explanation:** {g.explanation or '_Not yet generated._'}",
                "",
            ]
    else:
        lines.append("_No research gaps identified._")

    with md_file.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    return md_file
