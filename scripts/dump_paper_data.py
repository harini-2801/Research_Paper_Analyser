"""
Run the pipeline over the evaluation corpus and dump what the paper's figures need.

Separated from the plotting so the expensive part happens once. Everything the
figures draw comes out of this file, which means no number in a figure can drift
away from a number in the text without this being re-run.

Usage
-----
    python scripts/dump_paper_data.py [corpus_dir] [out.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rpra.config import Settings  # noqa: E402
from rpra.pipeline import run_pipeline  # noqa: E402

EXPECTED_SECTIONS = [
    "abstract", "introduction", "related_work", "methodology",
    "experiments", "results", "conclusion", "references",
]


def main() -> None:
    corpus = Path(sys.argv[1] if len(sys.argv) > 1 else "dataset/papers")
    out_path = Path(sys.argv[2] if len(sys.argv) > 2 else "paper/figure_data.json")

    manifest = json.loads((ROOT / "dataset" / "corpus_manifest.json").read_text())
    cluster_of = {p["slug"]: p["cluster"] for p in manifest["papers"]}
    title_of = {p["slug"]: p["title"] for p in manifest["papers"]}

    work = ROOT / "paper" / "_run"
    settings = Settings()
    settings.storage.corpus_input_path = str(corpus)
    settings.storage.output_path = str(work)
    settings.storage.graph_path = str(work / "kg.json")
    settings.storage.embeddings_path = str(work / "emb.npz")

    result = run_pipeline(
        settings, extraction_backend="heuristic", use_nli=False, skip_explanation=True
    )

    # Segmentation: how each document was split, and which sections came back.
    seg_counts = {s: 0 for s in EXPECTED_SECTIONS}
    by_headings = 0
    for doc in result.documents:
        if doc.metadata.get("segmentation") == "headings":
            by_headings += 1
        for section in {s.section_type for s in doc.segments}:
            if section in seg_counts:
                seg_counts[section] += 1

    # Pair scores, tagged with whether the two papers share a cluster.
    docs = sorted(result.documents, key=lambda d: (cluster_of.get(d.id, "Z"), d.id))
    order = [d.id for d in docs]
    index = {doc_id: i for i, doc_id in enumerate(order)}

    matrix = [[0.0] * len(order) for _ in order]
    pairs = []
    for score in result.scores:
        a, b = score.doc_id_a, score.doc_id_b
        if a not in index or b not in index:
            continue
        matrix[index[a]][index[b]] = score.composite_score
        matrix[index[b]][index[a]] = score.composite_score
        pairs.append({
            "a": a,
            "b": b,
            "score": score.composite_score,
            "same_cluster": cluster_of.get(a) == cluster_of.get(b),
            "dims": {
                "objective": score.objective_similarity,
                "methodology": score.methodology_similarity,
                "dataset": score.dataset_overlap,
                "results": score.results_metrics_similarity,
                "citation": score.citation_overlap,
            },
        })

    ranked = sorted(pairs, key=lambda p: p["score"], reverse=True)
    precision_at = {}
    for k in (5, 10, 20, 30, 50):
        top = ranked[:k]
        precision_at[k] = sum(1 for p in top if p["same_cluster"]) / len(top)

    within = [p["score"] for p in pairs if p["same_cluster"]]
    cross = [p["score"] for p in pairs if not p["same_cluster"]]

    payload = {
        "n_documents": len(result.documents),
        "n_pairs": len(pairs),
        "segmentation": {
            "by_headings": by_headings,
            "total": len(result.documents),
            "section_counts": seg_counts,
            "expected": EXPECTED_SECTIONS,
        },
        "order": order,
        "clusters": [cluster_of.get(d, "?") for d in order],
        "titles": [title_of.get(d, d) for d in order],
        "matrix": matrix,
        "precision_at": precision_at,
        "baseline": len(within) / len(pairs),
        "within": within,
        "cross": cross,
        "mean_within": sum(within) / len(within),
        "mean_cross": sum(cross) / len(cross),
        "entities": len(result.entities),
        "bridge_concepts": len(result.bridge_entities),
        "gaps": len(result.gaps),
        "graph_nodes": result.knowledge_graph.node_count(),
        "graph_edges": result.knowledge_graph.edge_count(),
        "top_pairs": [
            {"a": p["a"], "b": p["b"], "score": p["score"],
             "same_cluster": p["same_cluster"]}
            for p in ranked[:10]
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Wrote {out_path}")
    print(f"  docs={payload['n_documents']} pairs={payload['n_pairs']}")
    print(f"  segmented by headings: {by_headings}/{len(result.documents)}")
    print(f"  section recall: {sum(seg_counts.values())}/{8 * len(result.documents)}")
    print(f"  p@10={precision_at[10]:.0%}  baseline={payload['baseline']:.0%}")
    print(f"  mean within={payload['mean_within']:.3f} cross={payload['mean_cross']:.3f}")


if __name__ == "__main__":
    main()
