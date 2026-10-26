"""
Table rows for the extended evaluation, read from paper/extended_eval.json.

The report and both conference papers import this module, so a number can only
reach a table by being measured by scripts/extended_evaluation.py first.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "paper" / "extended_eval.json").read_text(encoding="utf-8"))

ORDER = [
    "Random ranking",
    "TF-IDF (full text)",
    "SBERT (abstract)",
    "Bibliographic similarity",
    "Methodology only",
    "Dataset only",
    "Results/metrics only",
    "Full weighted score (proposed)",
]


def f3(x, d: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{d}f}"


def pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def ci(pair, d: int = 2) -> str:
    return f"{pair[0]:.{d}f}–{pair[1]:.{d}f}"


def baseline_rows(with_ci: bool = True, bold_best: bool = True) -> list[list[str]]:
    ranking = DATA["ranking"]
    cols = ["P@10", "P@20", "P@30", "MAP", "nDCG@10", "AUC"]
    best = {c: max(ranking[m][c] for m in ORDER) for c in cols}
    rows = []
    for name in ORDER:
        r = ranking[name]
        cells = []
        for c in cols:
            txt = f3(r[c])
            if bold_best and abs(r[c] - best[c]) < 1e-9:
                txt = f"**{txt}**"
            cells.append(txt)
        row = [name.replace(" (proposed)", "") if False else name] + cells
        if with_ci:
            row.append(ci(r["MAP_ci"]))
        rows.append(row)
    return rows


def ablation_rows() -> list[list[str]]:
    rows = []
    for a in DATA["ablation"]:
        w = a["weights"]
        rows.append([a["config"]] + [f"{x:.3f}".rstrip("0").rstrip(".") if x else "0" for x in w]
                    + [f3(a["P@10"]), f3(a["nDCG@10"])])
    rw = DATA["random_weights"]
    rows.append([f"Random weights (mean of {rw['trials']})", "–", "–", "–", "–", "–",
                 f"{rw['P@10_mean']:.3f} ± {rw['P@10_sd']:.3f}",
                 f"{rw['nDCG@10_mean']:.3f} ± {rw['nDCG@10_sd']:.3f}"])
    return rows


def gate_labels() -> dict[str, str]:
    return {g: d for g, d in DATA["contradictions"]["gate_definitions"]}


def gates_real_rows() -> list[list[str]]:
    rows = []
    for r in DATA["contradictions"]["gates_real"]:
        rows.append([r["config"], str(r["claim_pairs"]), str(r["findings"]), str(r["doc_pairs"])])
    return rows


def gates_synth_rows() -> list[list[str]]:
    rows = []
    for r in DATA["contradictions"]["gates_synth"]:
        rows.append([r["config"], str(r["findings"]), str(r["TP"]), str(r["FP"]), str(r["FN"]),
                     f3(r["precision"], 2), f3(r["recall"], 2), f3(r["F1"], 2)])
    return rows


def sensitivity_matrix(kind: str, field: str) -> list[list[str]]:
    """Rows = similarity threshold, columns = confidence threshold."""
    rows_data = DATA["contradictions"]["sensitivity"][kind]
    sims = sorted({r["sim"] for r in rows_data})
    confs = sorted({r["conf"] for r in rows_data})
    out = []
    for s in sims:
        row = [f"{s:.1f}"]
        for c in confs:
            r = next(x for x in rows_data if x["sim"] == s and x["conf"] == c)
            if field == "tpfp":
                row.append(f"{r['TP']}/{r['FP']}" if "TP" in r else str(r["findings"]))
            else:
                row.append(str(r[field]))
        out.append(row)
    return out


def sensitivity_headers() -> list[str]:
    rows_data = DATA["contradictions"]["sensitivity"]["real_numeric"]
    confs = sorted({r["conf"] for r in rows_data})
    return ["Similarity \\ confidence"] + [f"{c:.1f}" for c in confs]


def candidate_rows() -> list[list[str]]:
    rows = []
    for r in DATA["contradictions"]["candidate_sweep"]:
        rows.append([f"{r['threshold']:.2f}", str(r["candidate_pairs_real"]), str(r["real_findings"]),
                     str(r["real_confirmed"]), str(r["candidate_pairs_synth"]), str(r["TP"]),
                     str(r["FP"]), f3(r["precision"], 2), f3(r["recall"], 2)])
    return rows


def graph_threshold_rows() -> list[list[str]]:
    rows = []
    for key, r in DATA["paper_network"].items():
        if not key.startswith("tau_"):
            continue
        rows.append([f"{r['tau']:.2f}", str(r["edges"]), f3(r["density"], 2), f3(r["mean_degree"], 1),
                     str(r["isolated"]), str(r["components"]), f3(r["avg_clustering"], 2),
                     pct(r["within_cluster_edge_share"]),
                     str(r.get("communities", "–")), f3(r.get("modularity"), 2), f3(r.get("ARI"), 2)])
    return rows
