"""
Draw the paper network with detected communities, from the saved evaluation data.

Colour is the community that Louvain found; marker shape is the topical cluster we
assigned. If the two agree, every shape has one colour.

Usage
-----
    python scripts/make_graph_figure.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
fig_data = json.loads((ROOT / "paper" / "figure_data.json").read_text(encoding="utf-8"))
ext = json.loads((ROOT / "paper" / "extended_eval.json").read_text(encoding="utf-8"))

ids = fig_data["order"]
clusters = dict(zip(ids, fig_data["clusters"]))
matrix = np.array(fig_data["matrix"])
assign = ext["paper_network"]["full_weighted"]["assignment"]
TAU = 0.50

G = nx.Graph()
G.add_nodes_from(ids)
for i in range(len(ids)):
    for j in range(i + 1, len(ids)):
        if matrix[i, j] >= TAU:
            G.add_edge(ids[i], ids[j], weight=float(matrix[i, j]))

pos = nx.spring_layout(G, weight="weight", seed=7, k=0.9)
palette = ["#2f5d8a", "#b9792b", "#3d7a5c", "#8a4f7d"]
markers = {"A": "o", "B": "s", "C": "^", "D": "D"}

fig, ax = plt.subplots(figsize=(6.4, 5.2))
for a, b, w in G.edges(data="weight"):
    ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]], color="#9aa5b1",
            lw=0.4 + 6 * (w - TAU), alpha=0.7, zorder=1)
for cl, mk in markers.items():
    nodes = [d for d in ids if clusters[d] == cl]
    ax.scatter([pos[d][0] for d in nodes], [pos[d][1] for d in nodes], marker=mk, s=120,
               c=[palette[assign[d] % len(palette)] for d in nodes], edgecolors="#1f2933",
               linewidths=0.8, zorder=2)
ax.set_axis_off()

shape_handles = [plt.Line2D([], [], marker=m, ls="", color="#d0d5db", markeredgecolor="#1f2933",
                            markersize=8, label=f"Cluster {c} (assigned)") for c, m in markers.items()]
n_comm = len(set(assign.values()))
colour_handles = [plt.Line2D([], [], marker="o", ls="", color=palette[i % len(palette)],
                             markeredgecolor="#1f2933", markersize=8,
                             label=f"Community {i + 1} (found)") for i in range(n_comm)]
leg = ax.legend(handles=shape_handles + colour_handles, fontsize=8, loc="upper center",
                bbox_to_anchor=(0.5, -0.01), frameon=False, ncol=3)
fig.savefig(ROOT / "paper" / "figures" / "graph_communities.png", dpi=200, bbox_inches="tight",
            facecolor="white")
print("wrote graph_communities.png with", n_comm, "communities")
