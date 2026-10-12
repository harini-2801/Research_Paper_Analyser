"""
Draw the paper's figures from the dumped pipeline output.

Every figure here reads paper/figure_data.json, which is written by
dump_paper_data.py from an actual run. Nothing is hand-entered, so a figure
cannot quietly disagree with the numbers in the prose.

Design notes, since proceedings are often printed in black and white:
the heatmap uses a single hue from light to dark, which survives grayscale
conversion by construction; the two-series figure pairs colours that differ in
lightness as well as hue and direct-labels both series, so identity never rests
on colour alone. Palette slots are the validated categorical blue and orange
(CVD separation dE 24.7 protan, 33.6 normal).

Usage
-----
    python scripts/make_paper_figures.py [figure_data.json] [out_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
SECOND = "#52514e"
MUTED = "#898781"
GRID = "#dededa"

# The blue sequential ramp, 100 -> 700, used for magnitude.
SEQ = LinearSegmentedColormap.from_list(
    "seq_blue",
    ["#ffffff", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
)

CLUSTER_NAMES = {
    "A": "Convolutional\nimage classification",
    "B": "Pretrained\nlanguage models",
    "C": "Vision transformers,\nself-supervised",
    "D": "Retrieval, IE,\nknowledge graphs",
}

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 8,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": SECOND,
    "ytick.color": SECOND,
    "axes.linewidth": 0.6,
    "savefig.dpi": 300,
    "figure.dpi": 150,
})


def despine(ax, keep=("left", "bottom")) -> None:
    for side, spine in ax.spines.items():
        spine.set_visible(side in keep)


# ---------------------------------------------------------------------------


def fig_pipeline(out: Path) -> None:
    """The eleven stages, as a schematic. No data; this is the system diagram."""
    stages = [
        ("1 Ingestion", "PDF to\nsegmented text"),
        ("2 Citations", "reference lists\nparsed"),
        ("3 Classification", "paper category"),
        ("4 Extraction", "typed entities\nand relations"),
        ("5 Embedding", "entity vectors"),
        ("6 Scoring", "435 pairs,\n5 dimensions"),
        ("7 Graph", "documents, entities,\nbridge concepts"),
        ("8 Contradictions", "numeric + NLI,\n4-condition gate"),
        ("9 Gaps", "stated, weak,\nabsent"),
        ("10 Explanation", "optional,\nevidence-grounded"),
        ("11 Export", "JSON, Markdown,\nPDF"),
    ]

    fig, ax = plt.subplots(figsize=(6.6, 2.7))
    ax.set_xlim(0, 12)
    # Rows descend from y=3.2 in steps of (bh + gy); with three rows the lowest
    # box bottom sits just below zero, so the limit has to go below it too.
    ax.set_ylim(-0.32, 4.55)
    ax.axis("off")

    per_row = 4
    bw, bh = 2.65, 1.12
    gx, gy = 0.33, 0.52

    centres = []
    for i, (name, detail) in enumerate(stages):
        row, col = divmod(i, per_row)
        x = 0.2 + col * (bw + gx)
        y = 3.2 - row * (bh + gy)
        ax.add_patch(Rectangle((x, y), bw, bh, facecolor="#f4f6fa",
                               edgecolor=MUTED, linewidth=0.6))
        ax.add_patch(Rectangle((x, y + bh - 0.07), bw, 0.07,
                               facecolor=BLUE, edgecolor="none"))
        ax.text(x + 0.11, y + bh - 0.30, name, fontsize=7.4, fontweight="bold")
        ax.text(x + 0.11, y + bh - 0.56, detail, fontsize=6.3, color=SECOND,
                va="top", linespacing=1.3)
        centres.append((x, y, bw, bh))

    # Arrows only within a row. Routing them across the wrap drew long diagonals
    # straight through the boxes; the stage numbers carry the order anyway.
    for i in range(len(stages) - 1):
        if (i + 1) % per_row == 0:
            continue
        x0, y0, w0, h0 = centres[i]
        x1, y1, _, h1 = centres[i + 1]
        ax.add_patch(FancyArrowPatch(
            (x0 + w0 + 0.03, y0 + h0 / 2), (x1 - 0.03, y1 + h1 / 2),
            arrowstyle="-|>", mutation_scale=7, color=MUTED, linewidth=0.7))

    fig.tight_layout(pad=0.2)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_heatmap(data: dict, out: Path) -> None:
    """The pair-score matrix, ordered by cluster, so block structure is visible."""
    matrix = data["matrix"]
    clusters = data["clusters"]
    n = len(matrix)

    # A document's score against itself is not computed; leaving it as 0 drew a
    # white diagonal that reads as "unrelated to itself". Mask it instead, and
    # scale the ramp to the range the data actually occupies so the block
    # structure uses the full range rather than the middle third of it.
    import numpy as np

    grid = np.array(matrix, dtype=float)
    np.fill_diagonal(grid, np.nan)
    masked = np.ma.masked_invalid(grid)
    lo, hi = float(masked.min()), float(masked.max())

    cmap = SEQ.copy()
    cmap.set_bad("#e8e8e4")

    fig, ax = plt.subplots(figsize=(3.9, 3.5))
    im = ax.imshow(masked, cmap=cmap, vmin=lo, vmax=hi, interpolation="nearest")

    # Rule off the cluster blocks so the diagonal structure is unmissable.
    edges, start = [], 0
    for i in range(1, n + 1):
        if i == n or clusters[i] != clusters[start]:
            edges.append((start, i))
            start = i
    for a, b in edges:
        ax.add_patch(Rectangle((a - 0.5, a - 0.5), b - a, b - a, fill=False,
                               edgecolor=ORANGE, linewidth=1.1))

    ax.set_xticks([(a + b - 1) / 2 for a, b in edges])
    ax.set_xticklabels([clusters[a] for a, _ in edges], fontsize=8)
    ax.set_yticks([(a + b - 1) / 2 for a, b in edges])
    ax.set_yticklabels([clusters[a] for a, _ in edges], fontsize=8)
    ax.set_xlabel("Topical cluster", fontsize=8)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    bar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    bar.set_label("Composite relationship score", fontsize=7.5)
    bar.ax.tick_params(labelsize=7, length=2)
    bar.outline.set_visible(False)

    fig.tight_layout(pad=0.2)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_separation(data: dict, out: Path) -> None:
    """Score distributions for within- and cross-cluster pairs."""
    within, cross = data["within"], data["cross"]
    mw, mc = data["mean_within"], data["mean_cross"]

    fig, ax = plt.subplots(figsize=(3.9, 2.5))
    bins = [i / 40 for i in range(0, 32)]
    ax.hist(cross, bins=bins, density=True, color=ORANGE, alpha=0.75,
            edgecolor="white", linewidth=0.4, label="Cross-cluster")
    ax.hist(within, bins=bins, density=True, color=BLUE, alpha=0.75,
            edgecolor="white", linewidth=0.4, label="Within-cluster")

    for mean, colour, label in ((mc, ORANGE, "Cross"), (mw, BLUE, "Within")):
        ax.axvline(mean, color=colour, linewidth=1.4, linestyle=(0, (4, 2)))
        ax.text(mean, ax.get_ylim()[1] * 0.80, f" {label} {mean:.3f}",
                fontsize=7, color=colour, va="top", fontweight="bold",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.2, alpha=0.85))

    ax.set_xlabel("Composite relationship score", fontsize=8)
    ax.set_ylabel("Density", fontsize=8)
    ax.set_xlim(0.1, 0.72)
    ax.grid(axis="y", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    despine(ax)
    leg = ax.legend(frameon=False, fontsize=7.5, loc="upper left")
    for text in leg.get_texts():
        text.set_color(SECOND)

    fig.tight_layout(pad=0.2)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def fig_sections(data: dict, out: Path) -> None:
    """How many of the thirty documents yielded each expected section."""
    seg = data["segmentation"]
    total = seg["total"]
    labels = [s.replace("_", " ") for s in seg["expected"]]
    values = [seg["section_counts"][s] for s in seg["expected"]]

    fig, ax = plt.subplots(figsize=(3.9, 2.4))
    ypos = list(range(len(labels)))[::-1]
    ax.barh(ypos, values, height=0.62, color=BLUE)
    ax.axvline(total, color=MUTED, linewidth=0.7, linestyle=(0, (3, 2)))
    ax.text(total, len(labels) - 0.2, f" n={total}", fontsize=7, color=MUTED)

    for y, value in zip(ypos, values):
        ax.text(value + 0.4, y, str(value), va="center", fontsize=7, color=SECOND)

    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_xlabel("Documents in which the section was recovered", fontsize=8)
    ax.set_xlim(0, total + 3)
    ax.grid(axis="x", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    despine(ax)
    ax.tick_params(length=0)

    fig.tight_layout(pad=0.2)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    data_path = Path(sys.argv[1] if len(sys.argv) > 1 else "paper/figure_data.json")
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "paper/figures")
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(data_path.read_text(encoding="utf-8"))

    jobs = [
        ("fig1_pipeline.png", lambda p: fig_pipeline(p)),
        ("fig2_heatmap.png", lambda p: fig_heatmap(data, p)),
        ("fig3_separation.png", lambda p: fig_separation(data, p)),
        ("fig4_sections.png", lambda p: fig_sections(data, p)),
    ]
    for name, draw in jobs:
        path = out_dir / name
        draw(path)
        print(f"Wrote {path}  ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
