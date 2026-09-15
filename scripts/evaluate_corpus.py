"""
Measure pipeline quality against the clustered arXiv corpus.

The corpus manifest written by `fetch_eval_corpus.py` records which topical
cluster each paper belongs to. That assignment is the ground truth here: two
papers in the same cluster study the same problem on the same benchmarks and
*should* score as related; two papers in different clusters should not.

Three things are measured.

Segmentation
    What fraction of papers were split by detected headings rather than falling
    back to page chunks, and how many of the eight expected sections were
    recovered. This is the metric that moved when heading detection was rebuilt:
    detection used to produce 0 sections on some templates and 186 on others.

Relationship ranking
    Precision@k over document pairs, where a pair is correct if both papers are
    in the same cluster. Also reported as the separation between mean
    within-cluster and mean cross-cluster score, which says whether the score is
    actually discriminative rather than merely ordered.

Findings
    Counts of contradictions and gaps, with the confirmed contradictions listed
    so they can be judged by eye. There is no ground truth for these, so they
    are reported rather than scored - the honest thing to do.

Usage
-----
    python scripts/evaluate_corpus.py [corpus_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rpra.config import Settings
from rpra.models import ContradictionStatus
from rpra.pipeline import run_pipeline

EXPECTED_SECTIONS = [
    "abstract", "introduction", "related_work", "methodology",
    "experiments", "results", "conclusion", "references",
]


def load_clusters(corpus: Path) -> dict[str, str]:
    """Map doc_id to cluster letter from the manifest."""
    manifest_path = corpus / "corpus_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(
            f"No corpus_manifest.json in {corpus}. "
            "Run scripts/fetch_eval_corpus.py first."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {p["slug"]: p["cluster"] for p in manifest["papers"]}


def rule(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def main() -> int:
    corpus = Path(sys.argv[1] if len(sys.argv) > 1 else "./data/eval_corpus")
    clusters = load_clusters(corpus)

    settings = Settings()
    settings.storage.corpus_input_path = str(corpus)
    settings.storage.output_path = "./output/evaluation"
    settings.storage.graph_path = "./output/evaluation/knowledge_graph.json"
    settings.storage.embeddings_path = "./output/evaluation/embeddings.npz"

    print(f"Evaluating {corpus.resolve()}")
    result = run_pipeline(settings, extraction_backend="heuristic", use_nli=False)

    # ---------------- Segmentation ----------------
    rule("Segmentation")

    by_mode: dict[str, int] = {}
    section_hits: dict[str, int] = {s: 0 for s in EXPECTED_SECTIONS}
    empty_docs = []

    for doc in result.documents:
        mode = doc.metadata.get("segmentation", "unknown")
        by_mode[mode] = by_mode.get(mode, 0) + 1
        present = {s.section_type for s in doc.segments}
        for name in EXPECTED_SECTIONS:
            if name in present:
                section_hits[name] += 1
        if not doc.segments:
            empty_docs.append(doc.id)

    total = len(result.documents)
    structured = by_mode.get("headings", 0)
    print(f"  documents                {total}")
    print(f"  split by headings        {structured}/{total} "
          f"({100 * structured / max(total, 1):.0f}%)")
    print(f"  fell back to page chunks {by_mode.get('fallback_pages', 0)}")
    print(f"  produced no segments     {len(empty_docs)} {empty_docs or ''}")

    recovered = sum(section_hits.values())
    possible = len(EXPECTED_SECTIONS) * total
    print(f"  section recall           {recovered}/{possible} "
          f"({100 * recovered / max(possible, 1):.0f}%)")
    for name in EXPECTED_SECTIONS:
        bar = "#" * round(20 * section_hits[name] / max(total, 1))
        print(f"    {name:<14} {section_hits[name]:>3}/{total}  {bar}")

    # ---------------- Relationship ranking ----------------
    rule("Relationship ranking (ground truth: topical cluster)")

    scored = []
    for score in result.scores:
        a = clusters.get(score.doc_id_a)
        b = clusters.get(score.doc_id_b)
        if a is None or b is None:
            continue
        scored.append((score.composite_score, a == b, score.doc_id_a, score.doc_id_b))

    scored.sort(key=lambda row: -row[0])
    if not scored:
        print("  no scored pairs with known clusters")
        return 1

    within = [s for s, same, _, _ in scored if same]
    across = [s for s, same, _, _ in scored if not same]

    print(f"  pairs scored             {len(scored)} "
          f"({len(within)} within-cluster, {len(across)} cross-cluster)")

    for k in (5, 10, 20, 30):
        if k > len(scored):
            break
        correct = sum(1 for _, same, _, _ in scored[:k] if same)
        print(f"  precision@{k:<3}            {correct}/{k}  ({100 * correct / k:.0f}%)")

    if within and across:
        mean_within = sum(within) / len(within)
        mean_across = sum(across) / len(across)
        print(f"  mean within-cluster      {mean_within:.3f}")
        print(f"  mean cross-cluster       {mean_across:.3f}")
        print(f"  separation               {mean_within - mean_across:+.3f}")

        # A random-baseline comparison keeps precision@k honest: with this many
        # within-cluster pairs, some hits are expected by chance alone.
        baseline = len(within) / len(scored)
        print(f"  random baseline          {100 * baseline:.0f}% "
              "(share of pairs that are within-cluster)")

    print("\n  Top 10 pairs:")
    for score, same, a, b in scored[:10]:
        mark = "OK  " if same else "MISS"
        print(f"    {mark} {score:.3f}  {a[:26]:26s} <-> {b[:26]}")

    # ---------------- Findings ----------------
    rule("Findings (reported, not scored - no ground truth)")

    confirmed = [
        c for c in result.contradictions
        if c.status == ContradictionStatus.CONFIRMED
    ]
    print(f"  contradictions           {len(result.contradictions)} "
          f"({len(confirmed)} confirmed)")
    print(f"  research gaps            {len(result.gaps)}")
    print(f"  entities                 {len(result.entities)}")
    print(f"  bridge concepts          {len(result.bridge_entities)}")
    print(f"  graph                    {result.knowledge_graph.node_count()} nodes, "
          f"{result.knowledge_graph.edge_count()} edges")

    if confirmed:
        print("\n  Confirmed contradictions (judge these by eye):")
        for c in confirmed[:6]:
            same_cluster = clusters.get(c.doc_id_a) == clusters.get(c.doc_id_b)
            tag = "same-cluster" if same_cluster else "CROSS-CLUSTER"
            print(f"    [{c.confidence:.2f}] {tag}  {c.doc_id_a[:24]} vs {c.doc_id_b[:24]}")
            print(f"        A: {c.claim_a[:88]}")
            print(f"        B: {c.claim_b[:88]}")

    print(f"\nElapsed {result.elapsed_seconds}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
