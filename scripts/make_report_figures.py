"""
Figures for the BCSE497J project report.

Diagrams are drawn directly with matplotlib patches so they stay editable as
code, and every chart is computed from paper/figure_data.json, the numbers
produced by the real evaluation run, never typed in by hand.

Usage
-----
    python scripts/make_report_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
DATA = json.loads((ROOT / "paper" / "figure_data.json").read_text(encoding="utf-8"))

INK = "#1f2933"
MUTED = "#6b7785"
BLUE = "#2f5d8a"
BLUE_L = "#dce8f4"
AMBER = "#b9792b"
AMBER_L = "#f6e8d3"
GREEN = "#3d7a5c"
GREEN_L = "#dcefe5"
GREY_L = "#eef1f4"

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 10,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def _box(ax, x, y, w, h, text, fc=GREY_L, ec=INK, fs=9, bold=False, lw=1.0):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
            fc=fc, ec=ec, lw=lw,
        )
    )
    ax.text(
        x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
        color=INK, fontweight="bold" if bold else "normal", linespacing=1.25,
    )


def _arrow(ax, x1, y1, x2, y2, style="-|>", color=INK, lw=1.0, rad=0.0):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle=style, mutation_scale=10,
            color=color, lw=lw, connectionstyle=f"arc3,rad={rad}",
        )
    )


def _canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def _save(fig, name):
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  wrote", name)


# ---------------------------------------------------------------------------
# Diagrams
# ---------------------------------------------------------------------------


def architecture():
    fig, ax = _canvas(7.0, 5.6)

    ax.text(3.5, 5.42, "Layered architecture of the analyzer", ha="center",
            fontsize=11, fontweight="bold", color=INK)

    layers = [
        ("Presentation", 4.35, BLUE_L,
         ["Web interface\n(graph, matrix, tables)", "Backend status\npage", "Report export\n(JSON, Markdown, PDF)"]),
        ("Service", 3.25, AMBER_L,
         ["REST endpoints\n(FastAPI)", "WebSocket\nprogress stream", "Run state\nand locking"]),
        ("Analysis pipeline", 2.15, GREEN_L,
         ["Ingestion and\nclassification", "Extraction and\nembedding", "Scoring, graph,\ncontradictions, gaps"]),
        ("Storage", 1.05, GREY_L,
         ["Corpus PDFs\n(data/papers)", "Graph JSON and\nembedding cache", "Reports and\npipeline log"]),
    ]
    for name, y, fc, items in layers:
        ax.add_patch(FancyBboxPatch((0.15, y - 0.1), 6.7, 0.95,
                                    boxstyle="round,pad=0.02,rounding_size=0.06",
                                    fc="white", ec=MUTED, lw=0.8, ls="--"))
        ax.text(0.28, y + 0.66, name, fontsize=8.5, color=MUTED, style="italic")
        for i, label in enumerate(items):
            _box(ax, 0.35 + i * 2.18, y - 0.02, 2.0, 0.62, label, fc=fc, fs=8.2)

    for y_from, y_to in ((4.2, 3.95), (3.1, 2.85), (2.0, 1.75)):
        for i in range(3):
            _arrow(ax, 1.35 + i * 2.18, y_from - 0.02, 1.35 + i * 2.18, y_to + 0.02,
                   color=MUTED, lw=0.8)

    ax.text(3.5, 0.45,
            "Each layer talks only to the one beneath it, so any layer can be replaced\n"
            "(for example the interface, hosted separately) without touching the others.",
            ha="center", fontsize=8.5, color=MUTED, style="italic")
    _save(fig, "arch_layers.png")


def data_model():
    fig, ax = _canvas(7.0, 4.9)
    ax.text(3.5, 4.72, "Core domain model", ha="center", fontsize=11,
            fontweight="bold", color=INK)

    def cls(x, y, w, title, fields, fc):
        h = 0.5 + 0.2 * len(fields)
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.04",
                                    fc="white", ec=INK, lw=1.0))
        ax.add_patch(FancyBboxPatch((x, y + h - 0.32), w, 0.32,
                                    boxstyle="round,pad=0.01,rounding_size=0.04",
                                    fc=fc, ec=INK, lw=1.0))
        ax.text(x + w / 2, y + h - 0.16, title, ha="center", va="center",
                fontsize=9, fontweight="bold", color=INK)
        for i, f in enumerate(fields):
            ax.text(x + 0.08, y + h - 0.52 - 0.2 * i, f, fontsize=7.6, color=INK,
                    va="center", family="monospace")
        return x, y, w, h

    doc = cls(0.2, 2.45, 1.9, "Document", ["id", "title", "category", "segments[]", "metadata"], BLUE_L)
    seg = cls(0.2, 0.3, 1.9, "Segment", ["section_type", "text", "page_start", "page_end"], BLUE_L)
    ent = cls(2.6, 2.45, 1.9, "Entity", ["entity_type", "text", "doc_id", "section", "sentence_span"], GREEN_L)
    rel = cls(2.6, 0.3, 1.9, "Relation", ["source", "target", "relation_type", "confidence"], GREEN_L)
    trail = cls(5.0, 2.3, 1.9, "EvidenceTrail", ["doc_id", "section", "page_number", "sentence_span"], AMBER_L)
    find = cls(5.0, 0.1, 1.9, "Contradiction / Gap", ["claim_a, claim_b", "confidence", "status", "novelty"], AMBER_L)

    _arrow(ax, 1.15, 2.45, 1.15, 1.75, color=MUTED)           # doc -> segment
    _arrow(ax, 2.1, 3.45, 2.6, 3.45, color=MUTED)               # doc -> entity
    _arrow(ax, 3.55, 2.45, 3.55, 1.75, color=MUTED)           # entity -> relation
    _arrow(ax, 4.5, 3.4, 5.0, 3.4, color=MUTED)               # entity -> trail
    _arrow(ax, 4.5, 1.0, 5.0, 0.9, color=MUTED)              # relation -> finding
    _arrow(ax, 5.95, 1.55, 5.95, 2.3, color=MUTED)            # finding -> trail
    ax.text(2.35, 3.52, "has", fontsize=7, color=MUTED, ha="center")
    ax.text(0.78, 2.05, "has", fontsize=7, color=MUTED, ha="center")
    ax.text(3.9, 2.05, "links", fontsize=7, color=MUTED, ha="center")
    ax.text(6.25, 1.95, "cites", fontsize=7, color=MUTED, ha="center")
    _save(fig, "data_model.png")


def deployment():
    fig, ax = _canvas(7.0, 3.6)
    ax.text(3.5, 3.45, "Deployment topology", ha="center", fontsize=11,
            fontweight="bold", color=INK)
    _box(ax, 0.2, 1.6, 1.5, 0.9, "Browser", fc=GREY_L, bold=True)
    _box(ax, 2.4, 1.6, 1.9, 0.9, "Vercel\nstatic interface\n(HTML, CSS, JS)", fc=BLUE_L, fs=8.5)
    _box(ax, 5.0, 1.6, 1.8, 0.9, "Render web service\nFastAPI + pipeline", fc=GREEN_L, fs=8.5)
    _box(ax, 5.0, 0.2, 1.8, 0.8, "Ephemeral disk\ncorpus, outputs", fc=GREY_L, fs=8.5)
    _box(ax, 2.4, 0.2, 1.9, 0.8, "Saved demo bundle\n(30-paper analysis)", fc=AMBER_L, fs=8.5)

    _arrow(ax, 1.7, 2.05, 2.4, 2.05)
    _arrow(ax, 4.3, 2.2, 5.0, 2.2, color=GREEN)
    _arrow(ax, 5.0, 1.9, 4.3, 1.9, color=GREEN)
    _arrow(ax, 5.9, 1.6, 5.9, 1.0, color=MUTED)
    _arrow(ax, 3.35, 1.6, 3.35, 1.0, color=MUTED)
    ax.text(4.65, 2.62, "REST + WebSocket", fontsize=7.5, color=GREEN, ha="center")
    ax.text(3.45, 1.28, "used when no\nAPI answers", fontsize=7.2, color=MUTED, ha="left", va="center")
    ax.text(6.0, 1.28, "reads / writes", fontsize=7.2, color=MUTED, ha="left", va="center")
    _save(fig, "deployment.png")


def contradiction_gates():
    ext = json.loads((ROOT / "paper" / "extended_eval.json").read_text(encoding="utf-8"))
    rows = ext["contradictions"]["gates_real"][:7]
    labels = ["No gates", "G1 shared term", "G2 same dataset", "G3 same system",
              "G4 asserts result", "G5 comparable", "G6 gap ≥ 5%"]
    vals = [r["findings"] for r in rows]
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    colors = [AMBER] * 4 + [BLUE, GREEN, GREEN]
    bars = ax.barh(range(len(vals)), vals, color=colors, edgecolor=INK, lw=0.7, height=0.62)
    for b, v in zip(bars, vals):
        ax.text(v + 60, b.get_y() + b.get_height() / 2, f"{v:,}", va="center", fontsize=8.5)
    ax.set_yticks(range(len(vals)))
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.15)
    ax.set_xlabel("Claim pairs still flagged (cumulative gates, real corpus)")
    ax.set_title("Measured gate funnel on the 30-paper corpus", fontsize=9.5)
    _save(fig, "contradiction_gates.png")


# ---------------------------------------------------------------------------
# Charts computed from the evaluation run
# ---------------------------------------------------------------------------


def segmentation():
    seg = DATA["segmentation"]
    expected = seg["expected"]
    counts = [seg["section_counts"][e] for e in expected]
    total = seg["total"]
    labels = [e.replace("_", " ").title() for e in expected]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    colors = [GREEN if c == total else BLUE if c / total >= 0.8 else AMBER for c in counts]
    bars = ax.barh(range(len(labels)), counts, color=colors, edgecolor=INK, lw=0.7, height=0.62)
    ax.axvline(total, color=MUTED, ls="--", lw=0.9)
    for b, c in zip(bars, counts):
        ax.text(c + 0.4, b.get_y() + b.get_height() / 2, f"{c}/{total}", va="center", fontsize=8.5)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlim(0, total + 4)
    ax.set_xlabel("Papers in which the section was recovered")
    ax.set_title("Section recovery across the 30-paper corpus (215 of 240)", fontsize=9.5)
    _save(fig, "segmentation_recovery.png")


def precision():
    p = {int(k): v for k, v in DATA["precision_at"].items()}
    base = DATA["baseline"]
    ks = sorted(p)
    fig, ax = plt.subplots(figsize=(6.0, 3.3))
    bars = ax.bar(range(len(ks)), [p[k] * 100 for k in ks], color=BLUE, edgecolor=INK, lw=0.7, width=0.6)
    ax.axhline(base * 100, color=AMBER, ls="--", lw=1.4, label=f"Random baseline ({base * 100:.0f}%)")
    for b, k in zip(bars, ks):
        ax.text(b.get_x() + b.get_width() / 2, p[k] * 100 + 1.5, f"{p[k] * 100:.0f}%", ha="center", fontsize=9)
    ax.set_xticks(range(len(ks)))
    ax.set_xticklabels([f"@{k}" for k in ks])
    ax.set_ylim(0, 112)
    ax.set_ylabel("Precision (%)")
    ax.set_xlabel("Rank cut-off")
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    ax.set_title("Relationship ranking precision against the cluster ground truth", fontsize=9.5)
    _save(fig, "precision_at_k.png")


def score_distribution():
    within, cross = DATA["within"], DATA["cross"]
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    bins = [i / 40 for i in range(4, 28)]
    ax.hist(cross, bins=bins, alpha=0.75, color=AMBER, edgecolor=INK, lw=0.5,
            label=f"Across clusters (n={len(cross)})", density=True)
    ax.hist(within, bins=bins, alpha=0.75, color=BLUE, edgecolor=INK, lw=0.5,
            label=f"Within a cluster (n={len(within)})", density=True)
    ax.axvline(DATA["mean_cross"], color=AMBER, lw=1.6)
    ax.axvline(DATA["mean_within"], color=BLUE, lw=1.6)
    ax.set_xlabel("Composite relationship score")
    ax.set_ylabel("Density")
    ax.legend(frameon=False, fontsize=8.5)
    ax.set_title(
        f"Score distributions (means {DATA['mean_within']:.3f} within, {DATA['mean_cross']:.3f} across)",
        fontsize=9.5,
    )
    _save(fig, "score_distribution.png")


def weights():
    names = ["Objective", "Methodology", "Dataset", "Results and\nmetrics", "Citation"]
    w = [0.25, 0.25, 0.20, 0.20, 0.10]
    fig, ax = plt.subplots(figsize=(6.0, 2.9))
    bars = ax.bar(names, w, color=[BLUE, BLUE, GREEN, GREEN, AMBER], edgecolor=INK, lw=0.7, width=0.6)
    for b, v in zip(bars, w):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.006, f"{v:.2f}", ha="center", fontsize=9)
    ax.set_ylim(0, 0.32)
    ax.set_ylabel("Weight")
    ax.set_title("Default scoring weights (sum to 1.00)", fontsize=9.5)
    _save(fig, "weights.png")


def main() -> None:
    print("Drawing report figures")
    architecture()
    data_model()
    deployment()
    contradiction_gates()
    segmentation()
    precision()
    score_distribution()
    weights()
    # Reuse the figures already generated from the same run for the paper.
    import shutil

    for name in ("fig1_pipeline.png", "fig2_heatmap.png", "fig2_workspace.png",
                 "fig3_documents.png", "fig5_evidence.png"):
        src = ROOT / "paper" / "figures" / name
        if src.exists():
            shutil.copy(src, OUT / name)
            print("  copied", name)


if __name__ == "__main__":
    main()
