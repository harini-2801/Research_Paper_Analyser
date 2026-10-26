"""
Extended evaluation: baselines, weight ablation, graph analysis, contradiction
gates, threshold sensitivity and a provenance audit.

Every number the report and the papers quote from these experiments is produced
here and written to ``paper/extended_eval.json``, so none of them is typed in by
hand. Nothing below is tuned: the pipeline runs once with its shipped defaults
and every table is a measurement of that run.

Ground truth
------------
* Ranking: two papers are *relevant* to each other when they belong to the same
  topical cluster of the evaluation corpus (the cluster was assigned by us when
  the corpus was built; it is not an independent human judgement).
* Contradictions: the six-paper synthetic corpus has two planted contradictions,
  at document-pair level. The real corpus has no labelled contradictions, so no
  precision or recall is computed for it - only counts.

Usage
-----
    python scripts/extended_evaluation.py
"""

from __future__ import annotations

import itertools
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import networkx as nx  # noqa: E402
import pymupdf  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, roc_auc_score  # noqa: E402

from rpra import contradiction as C  # noqa: E402
from rpra.claims import analyse_claim, comparable_measurements  # noqa: E402
from rpra.config import Settings  # noqa: E402
from rpra.models import ContradictionStatus, EntityType  # noqa: E402
from rpra.pipeline import run_pipeline  # noqa: E402

RNG = np.random.default_rng(2026)
OUT_JSON = ROOT / "paper" / "extended_eval.json"
FIG_DIR = ROOT / "paper" / "figures"
WEIGHTS = {"objective": 0.25, "methodology": 0.25, "dataset": 0.20, "results": 0.20, "citation": 0.10}
DIMS = list(WEIGHTS)
PLANTED = {
    frozenset(["vision_deep_residual_2021", "vision_residual_reproduction_2022"]),
    frozenset(["nlp_attention_reading_2021", "nlp_efficient_transformers_2023"]),
}


# ----------------------------------------------------------------------------
# Running the pipeline
# ----------------------------------------------------------------------------


def run(corpus: Path, work: Path):
    settings = Settings()
    settings.storage.corpus_input_path = str(corpus)
    settings.storage.output_path = str(work)
    settings.storage.graph_path = str(work / "kg.json")
    settings.storage.embeddings_path = str(work / "emb.npz")
    return run_pipeline(settings, extraction_backend="heuristic", use_nli=False, skip_explanation=True)


# ----------------------------------------------------------------------------
# Ranking metrics
# ----------------------------------------------------------------------------


def jitter(scores: np.ndarray, scale: float = 1e-9) -> np.ndarray:
    """Break ties at random so that tied scores cannot flatter or punish a method."""
    return scores + RNG.random(scores.shape) * scale


def global_metrics(score_vec: np.ndarray, rel_vec: np.ndarray, trials: int = 100) -> dict:
    """P@k, recall@30 and ROC-AUC over the single ranking of all document pairs."""
    acc = {"P@10": 0.0, "P@20": 0.0, "P@30": 0.0, "R@30": 0.0, "AUC": 0.0}
    total_rel = rel_vec.sum()
    for _ in range(trials):
        s = jitter(score_vec)
        order = np.argsort(-s)
        r = rel_vec[order]
        for k in (10, 20, 30):
            acc[f"P@{k}"] += r[:k].mean()
        acc["R@30"] += r[:30].sum() / total_rel
        acc["AUC"] += roc_auc_score(rel_vec, s)
    return {k: v / trials for k, v in acc.items()}


def query_metrics(score_mat: np.ndarray, rel_mat: np.ndarray, trials: int = 30) -> tuple[np.ndarray, np.ndarray]:
    """Per-paper average precision and nDCG@10 (each paper queries the other 29)."""
    n = score_mat.shape[0]
    ap = np.zeros(n)
    ndcg = np.zeros(n)
    for q in range(n):
        idx = [j for j in range(n) if j != q]
        rel_q = rel_mat[q, idx].astype(float)
        n_rel = rel_q.sum()
        if n_rel == 0:
            continue
        for _ in range(trials):
            s = jitter(score_mat[q, idx])
            order = np.argsort(-s)
            r = rel_q[order]
            hits = np.cumsum(r)
            ranks = np.arange(1, len(r) + 1)
            ap[q] += (hits[r > 0] / ranks[r > 0]).sum() / n_rel
            gains = r[:10] / np.log2(np.arange(2, min(len(r), 10) + 2))
            ideal = np.ones(int(min(n_rel, 10))) / np.log2(np.arange(2, int(min(n_rel, 10)) + 2))
            ndcg[q] += gains.sum() / ideal.sum()
        ap[q] /= trials
        ndcg[q] /= trials
    return ap, ndcg


def bootstrap_ci(values: np.ndarray, n: int = 2000) -> tuple[float, float]:
    """Percentile interval for the mean of per-query values, resampling queries."""
    means = [values[RNG.integers(0, len(values), len(values))].mean() for _ in range(n)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def pair_bootstrap_ci(score_vec, rel_vec, metric, n: int = 400) -> tuple[float, float]:
    vals = []
    for _ in range(n):
        idx = RNG.integers(0, len(score_vec), len(score_vec))
        if rel_vec[idx].sum() in (0, len(idx)):
            continue
        s = jitter(score_vec[idx])
        order = np.argsort(-s)
        r = rel_vec[idx][order]
        if metric == "P@10":
            vals.append(r[:10].mean())
        elif metric == "P@20":
            vals.append(r[:20].mean())
        elif metric == "P@30":
            vals.append(r[:30].mean())
        else:
            vals.append(roc_auc_score(rel_vec[idx], s))
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def evaluate_matrix(mat: np.ndarray, rel_mat: np.ndarray, iu, with_ci: bool = True) -> dict:
    score_vec = mat[iu]
    rel_vec = rel_mat[iu].astype(float)
    g = global_metrics(score_vec, rel_vec)
    ap, ndcg = query_metrics(mat, rel_mat)
    out = {**g, "MAP": float(ap.mean()), "nDCG@10": float(ndcg.mean())}
    if with_ci:
        out["MAP_ci"] = bootstrap_ci(ap)
        out["nDCG@10_ci"] = bootstrap_ci(ndcg)
        out["AUC_ci"] = pair_bootstrap_ci(score_vec, rel_vec, "AUC")
        for k in (10, 20, 30):
            out[f"P@{k}_ci"] = pair_bootstrap_ci(score_vec, rel_vec, f"P@{k}")
    return out


def random_baseline(rel_mat: np.ndarray, iu, trials: int = 500) -> dict:
    n = rel_mat.shape[0]
    rel_vec = rel_mat[iu].astype(float)
    rows = []
    for _ in range(trials):
        m = RNG.random((n, n))
        m = np.triu(m, 1)
        m = m + m.T
        g = global_metrics(m[iu], rel_vec, trials=1)
        ap, ndcg = query_metrics(m, rel_mat, trials=1)
        rows.append({**g, "MAP": ap.mean(), "nDCG@10": ndcg.mean()})
    out = {}
    for key in rows[0]:
        vals = np.array([r[key] for r in rows])
        out[key] = float(vals.mean())
        out[f"{key}_ci"] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
    return out


# ----------------------------------------------------------------------------
# Contradiction analysis
# ----------------------------------------------------------------------------


def run_detector(result, use_nli: bool, candidate_threshold: float | None = None):
    """Run the shipped detector with permissive thresholds; confirm offline later."""
    old = C._CANDIDATE_SCORE_THRESHOLD
    if candidate_threshold is not None:
        C._CANDIDATE_SCORE_THRESHOLD = candidate_threshold
    try:
        findings = C.detect_contradictions(
            result.documents, result.entities, result.scores, result.bridge_entities,
            nli_confidence_threshold=0.0, methodology_similarity_threshold=0.0,
            use_nli=use_nli,
        )
    finally:
        C._CANDIDATE_SCORE_THRESHOLD = old
    return findings


def confirmed_at(f, t_sim: float, t_conf: float) -> bool:
    return (
        f.confidence >= t_conf
        and (f.dataset_compatible or f.metrics_comparable)
        and f.methodology_similarity >= t_sim
    )


def pair_key(f) -> frozenset:
    return frozenset([f.doc_id_a, f.doc_id_b])


def prf(found: set, planted: set | None) -> dict:
    if planted is None:
        return {}
    tp = len(found & planted)
    fp = len(found - planted)
    fn = len(planted - found)
    p = tp / (tp + fp) if (tp + fp) else None
    r = tp / (tp + fn) if (tp + fn) else None
    f1 = 2 * p * r / (p + r) if (p is not None and r is not None and (p + r) > 0) else None
    return {"TP": tp, "FP": fp, "FN": fn, "precision": p, "recall": r, "F1": f1}


GATES = [
    ("G1", "shared dataset or metric term named in both sentences"),
    ("G2", "same dataset named on both sides"),
    ("G3", "same system named on both sides"),
    ("G4", "both sentences assert a measured result; no cross-reference"),
    ("G5", "comparable measurements (value/change, own/quoted, metric, variant, regime)"),
    ("G6", "relative difference of at least 5%"),
    ("G7", "papers share a dataset or a comparable metric"),
    ("G8", "methodology similarity >= 0.30 and confidence >= 0.60"),
]


def gated_disagreement(claim_a, claim_b, shared, dataset_terms, model_terms, on: set[str]):
    """Re-statement of the numeric detector with switchable gates (see contradiction.py)."""
    text_a, text_b = claim_a.sentence_span, claim_b.sentence_span
    if "G1" in on:
        if not shared:
            return None
        common = {t for t in shared if C._mentions(text_a, t) and C._mentions(text_b, t)}
        if not common:
            return None
    if "G2" in on:
        da = {t for t in dataset_terms if C._mentions(text_a, t)}
        db = {t for t in dataset_terms if C._mentions(text_b, t)}
        if da and db and not (da & db):
            return None
        if not da or not db:
            return None
    if "G3" in on:
        ma = {t for t in model_terms if C._mentions_model(text_a, t)}
        mb = {t for t in model_terms if C._mentions_model(text_b, t)}
        if ma and mb and not (ma & mb):
            return None
    if "G4" in on:
        for text in (text_a, text_b):
            if not C._RESULT_ASSERTION_RE.search(text) or C._CROSS_REFERENCE_RE.search(text):
                return None
    if "G5" in on:
        pair = comparable_measurements(analyse_claim(text_a), analyse_claim(text_b))
        if pair is None:
            return None
        va, vb = pair[0].value, pair[1].value
    else:
        pa, pb = C.parse_reported_values(text_a), C.parse_reported_values(text_b)
        if not pa or not pb:
            return None
        va, vb = max(pa), max(pb)
    denominator = max(va, vb)
    if denominator == 0:
        return None
    gap = abs(va - vb) / denominator
    if "G6" in on and gap < C._NUMERIC_DISAGREEMENT_RATIO:
        return None
    if gap == 0:
        return None
    scaled = min(gap / C._NUMERIC_SATURATION_RATIO, 1.0)
    return round(C._NUMERIC_BASE_CONFIDENCE + (0.99 - C._NUMERIC_BASE_CONFIDENCE) * scaled, 4)


def claim_pairs(result):
    """Every claim pair the shipped detector would compare, with the pair-level context."""
    ent_index: dict[str, list] = {}
    for e in result.entities:
        ent_index.setdefault(e.doc_id, []).append(e)
    meth = {frozenset([s.doc_id_a, s.doc_id_b]): s.methodology_similarity for s in result.scores}
    candidates = C._build_candidate_pairs(result.scores, result.bridge_entities)
    out = []
    for a, b in sorted(candidates):
        ea, eb = ent_index.get(a, []), ent_index.get(b, [])
        ca, cb = C._extract_claims(ea), C._extract_claims(eb)
        if not ca or not cb:
            continue
        ctx = {
            "ds": C._datasets_compatible(ea, eb),
            "met": C._metrics_comparable(ea, eb),
            "shared": C._shared_terms(ea, eb),
            "dsets": C._dataset_names(ea) | C._dataset_names(eb),
            "models": C._model_names(ea) | C._model_names(eb),
            "meth": meth.get(frozenset([a, b]), 0.0),
        }
        n = 0
        for x in ca:
            if n >= C._MAX_PAIRS_PER_DOC_PAIR:
                break
            for y in cb:
                if n >= C._MAX_PAIRS_PER_DOC_PAIR:
                    break
                if x.text.lower().strip() == y.text.lower().strip():
                    continue
                n += 1
                out.append((a, b, x, y, ctx))
    return out, len(candidates)


def verify_restatement(pairs) -> tuple[int, int]:
    """Count claim pairs the shipped detector flags against my gate restatement."""
    shipped = mine = 0
    all_gates = {"G1", "G2", "G3", "G4", "G5", "G6"}
    for a, b, x, y, ctx in pairs:
        ref = C._numeric_disagreement(x, y, ctx["shared"], ctx["dsets"], ctx["models"])
        got = gated_disagreement(x, y, ctx["shared"], ctx["dsets"], ctx["models"], all_gates)
        shipped += ref is not None
        mine += got is not None
        assert (ref is None) == (got is None), "gate restatement diverges from the shipped detector"
    return shipped, mine


def gate_table(result, planted: set | None) -> list[dict]:
    pairs, n_candidates = claim_pairs(result)
    print("   restatement check (shipped, mine):", verify_restatement(pairs))
    configs = [("No gates", set(), False, False)]
    on: set[str] = set()
    for g, _ in GATES[:6]:
        on = on | {g}
        configs.append((f"+ {g}" if g != "G1" else "G1", set(on), False, False))
    configs.append(("+ G7", set(on), True, False))
    configs.append(("+ G8 (all gates)", set(on), True, True))
    rows = []
    for name, gates, g7, g8 in configs:
        findings = 0
        found_pairs: set = set()
        for a, b, x, y, ctx in pairs:
            conf = gated_disagreement(x, y, ctx["shared"], ctx["dsets"], ctx["models"], gates)
            if conf is None:
                continue
            if g7 and not (ctx["ds"] or ctx["met"]):
                continue
            if g8 and not (ctx["meth"] >= 0.30 and conf >= 0.60):
                continue
            findings += 1
            found_pairs.add(frozenset([a, b]))
        row = {"config": name, "candidate_pairs": n_candidates, "claim_pairs": len(pairs),
               "findings": findings, "doc_pairs": len(found_pairs)}
        row.update(prf(found_pairs, planted))
        rows.append(row)
    return rows


# ----------------------------------------------------------------------------
# Provenance audit (automatic)
# ----------------------------------------------------------------------------


def norm(text: str) -> str:
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def audit_trails(trails, docs_by_id: dict, pdf_dir: Path) -> dict:
    ok_doc = ok_sec = ok_page = ok_quote = ok_all = 0
    cache: dict[str, pymupdf.Document] = {}
    for t in trails:
        doc = docs_by_id.get(t.source_doc_id)
        if doc is not None:
            ok_doc += 1
        path = pdf_dir / f"{t.source_doc_id}.pdf"
        quote = norm(t.sentence_span)[:80]
        page_ok = quote_ok = False
        if path.exists():
            pdf = cache.setdefault(str(path), pymupdf.open(path))
            if 1 <= t.page_number <= len(pdf):
                page_ok = quote in norm(pdf[t.page_number - 1].get_text())
            quote_ok = page_ok or any(quote in norm(p.get_text()) for p in pdf)
        sec_ok = False
        if doc is not None:
            for seg in doc.segments:
                if seg.section_type == t.section and quote in norm(seg.text):
                    sec_ok = True
                    break
        ok_page += page_ok
        ok_quote += quote_ok
        ok_sec += sec_ok
        ok_all += bool(doc is not None and sec_ok and page_ok and quote_ok)
    n = len(trails)
    return {"trails": n, "document": ok_doc, "section": ok_sec, "page": ok_page, "quote": ok_quote,
            "all_four": ok_all}


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def main() -> None:
    t0 = time.time()
    manifest = json.loads((ROOT / "dataset" / "corpus_manifest.json").read_text())
    cluster_of = {p["slug"]: p["cluster"] for p in manifest["papers"]}

    print("Running the pipeline on the 30-paper corpus ...")
    real = run(ROOT / "dataset" / "papers", ROOT / "paper" / "_run_ext")
    docs = sorted(real.documents, key=lambda d: (cluster_of.get(d.id, "Z"), d.id))
    ids = [d.id for d in docs]
    n = len(ids)
    idx = {d: i for i, d in enumerate(ids)}
    clusters = np.array([cluster_of[d] for d in ids])
    rel = clusters[:, None] == clusters[None, :]
    np.fill_diagonal(rel, False)
    iu = np.triu_indices(n, 1)

    comp = {k: np.zeros((n, n)) for k in DIMS}
    stored = np.zeros((n, n))
    for s in real.scores:
        i, j = idx[s.doc_id_a], idx[s.doc_id_b]
        vals = {"objective": s.objective_similarity, "methodology": s.methodology_similarity,
                "dataset": s.dataset_overlap, "results": s.results_metrics_similarity,
                "citation": s.citation_overlap}
        for k, v in vals.items():
            comp[k][i, j] = comp[k][j, i] = v
        stored[i, j] = stored[j, i] = s.composite_score

    # Consistency with the figures already in the paper.
    fig_data = json.loads((ROOT / "paper" / "figure_data.json").read_text())
    old_order = fig_data["order"]
    old = np.array(fig_data["matrix"])
    perm = [old_order.index(d) for d in ids]
    reproduces = float(np.abs(old[np.ix_(perm, perm)] - stored).max())
    print(f"  max |new - paper figure matrix| = {reproduces:.6f}")

    def full(w):
        return sum(w[k] * comp[k] for k in DIMS)

    full_mat = full(WEIGHTS)
    print("  recomputed composite vs stored: max diff", float(np.abs(full_mat - stored).max()))

    # ------------------------------------------------------------------ baselines
    print("Baselines ...")
    texts = ["\n".join(s.text for s in d.segments) for d in docs]
    abstracts = []
    for d in docs:
        a = " ".join(s.text for s in d.segments if s.section_type == "abstract")
        abstracts.append(a if a.strip() else " ".join(s.text for s in d.segments)[:1500])

    tf = TfidfVectorizer(stop_words="english", sublinear_tf=True, min_df=2, max_df=0.95)
    X = tf.fit_transform(texts)
    tfidf_mat = (X @ X.T).toarray()
    np.fill_diagonal(tfidf_mat, 0)

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device="cpu")
    emb = model.encode(abstracts, normalize_embeddings=True, show_progress_bar=False)
    sbert_mat = emb @ emb.T
    np.fill_diagonal(sbert_mat, 0)

    methods = {
        "TF-IDF (full text)": tfidf_mat,
        "SBERT (abstract)": sbert_mat,
        "Bibliographic similarity": comp["citation"],
        "Methodology only": comp["methodology"],
        "Dataset only": comp["dataset"],
        "Results/metrics only": comp["results"],
        "Full weighted score (proposed)": full_mat,
    }
    ranking = {"Random ranking": random_baseline(rel, iu)}
    for name, mat in methods.items():
        ranking[name] = evaluate_matrix(mat, rel, iu)
        print(f"  {name:34s} P@10={ranking[name]['P@10']:.3f} MAP={ranking[name]['MAP']:.3f} "
              f"nDCG@10={ranking[name]['nDCG@10']:.3f} AUC={ranking[name]['AUC']:.3f}")
    extra = {"Objective only": evaluate_matrix(comp["objective"], rel, iu, with_ci=False)}

    n_rel = int(rel[iu].sum())

    # ------------------------------------------------------------------ ablation
    print("Weight ablation ...")
    ablation = []

    def run_weights(label, w):
        vec = np.array([w[k] for k in DIMS])
        m = evaluate_matrix(full(w), rel, iu, with_ci=False)
        ablation.append({"config": label, "weights": vec.tolist(), "P@10": m["P@10"],
                         "nDCG@10": m["nDCG@10"], "MAP": m["MAP"], "AUC": m["AUC"]})

    run_weights("Equal weights", {k: 0.2 for k in DIMS})
    for drop in DIMS:
        w = {k: (0.0 if k == drop else WEIGHTS[k]) for k in DIMS}
        total = sum(w.values())
        run_weights(f"Drop {drop}", {k: v / total for k, v in w.items()})
    run_weights("Full weighted score", WEIGHTS)
    singles = {}
    trials = []
    for _ in range(300):
        w = RNG.dirichlet(np.ones(5))
        wd = dict(zip(DIMS, w))
        m = evaluate_matrix(full(wd), rel, iu, with_ci=False)
        trials.append((m["P@10"], m["nDCG@10"], m["MAP"]))
    arr = np.array(trials)
    random_weights = {"trials": len(arr), "P@10_mean": float(arr[:, 0].mean()), "P@10_sd": float(arr[:, 0].std()),
                      "P@10_min": float(arr[:, 0].min()), "P@10_max": float(arr[:, 0].max()),
                      "nDCG@10_mean": float(arr[:, 1].mean()), "nDCG@10_sd": float(arr[:, 1].std()),
                      "nDCG@10_min": float(arr[:, 1].min()), "nDCG@10_max": float(arr[:, 1].max()),
                      "MAP_mean": float(arr[:, 2].mean()), "MAP_sd": float(arr[:, 2].std())}
    # share of random weightings that beat the shipped weights
    full_p10 = ablation[-1]["P@10"]
    full_ndcg = ablation[-1]["nDCG@10"]
    random_weights["share_beating_default_nDCG"] = float((arr[:, 1] > full_ndcg + 1e-9).mean())
    random_weights["share_beating_default_P10"] = float((arr[:, 0] > full_p10 + 1e-9).mean())

    # ------------------------------------------------------------------ graph
    print("Graph analysis ...")
    kg = real.knowledge_graph.graph
    node_types: dict[str, int] = {}
    for _, a in kg.nodes(data=True):
        node_types[a.get("node_type", "?")] = node_types.get(a.get("node_type", "?"), 0) + 1
    edge_types: dict[str, int] = {}
    for _, _, a in kg.edges(data=True):
        edge_types[a.get("edge_type", "?")] = edge_types.get(a.get("edge_type", "?"), 0) + 1
    und = nx.Graph(kg.to_undirected())

    def purity(labels, truth):
        groups: dict = {}
        for l, t in zip(labels, truth):
            groups.setdefault(l, []).append(t)
        return sum(max(v.count(x) for x in set(v)) for v in groups.values()) / len(labels)

    def community_report(G: nx.Graph, seed=42):
        comms = nx.community.louvain_communities(G, weight="weight", seed=seed)
        label = {}
        for ci, members in enumerate(comms):
            for m in members:
                label[m] = ci
        lab = [label[d] for d in ids]
        truth = list(clusters)
        return {
            "communities": len(comms),
            "sizes": sorted((len(c) for c in comms), reverse=True),
            "modularity": nx.community.modularity(G, comms, weight="weight"),
            "ARI": float(adjusted_rand_score(truth, lab)),
            "NMI": float(normalized_mutual_info_score(truth, lab)),
            "purity": purity(lab, truth),
            "assignment": {d: label[d] for d in ids},
        }, comms

    def paper_graph(tau: float | None) -> nx.Graph:
        G = nx.Graph()
        G.add_nodes_from(ids)
        for i, j in zip(*iu):
            w = float(stored[i, j])
            if tau is None or w >= tau:
                G.add_edge(ids[i], ids[j], weight=w)
        return G

    paper_net = {}
    G_full = paper_graph(None)
    rep, comms_full = community_report(G_full)
    paper_net["full_weighted"] = {"edges": G_full.number_of_edges(), **rep}
    for tau in (0.40, 0.45, 0.50, 0.55):
        G = paper_graph(tau)
        degs = [d for _, d in G.degree()]
        ccs = list(nx.connected_components(G))
        row = {
            "tau": tau, "edges": G.number_of_edges(),
            "density": nx.density(G), "mean_degree": float(np.mean(degs)),
            "isolated": int(sum(1 for d in degs if d == 0)),
            "components": len(ccs), "largest_component": max(len(c) for c in ccs),
            "avg_clustering": nx.average_clustering(G),
        }
        within_edges = sum(1 for a, b in G.edges if cluster_of[a] == cluster_of[b])
        row["within_cluster_edge_share"] = within_edges / max(G.number_of_edges(), 1)
        if G.number_of_edges() > 0:
            rep, _ = community_report(G)
            row.update({k: v for k, v in rep.items() if k != "assignment"})
        paper_net[f"tau_{tau:.2f}"] = row

    strength = {d: sum(stored[idx[d], j] for j in range(n) if j != idx[d]) for d in ids}
    hubs = sorted(strength.items(), key=lambda kv: -kv[1])[:5]
    # per-cluster mean within/cross score
    cl_names = sorted(set(clusters))
    cluster_matrix = {}
    for a in cl_names:
        for b in cl_names:
            sel = [(i, j) for i, j in zip(*iu) if {clusters[i], clusters[j]} == {a, b}] if a != b else \
                  [(i, j) for i, j in zip(*iu) if clusters[i] == a and clusters[j] == a]
            if sel and a <= b:
                cluster_matrix[f"{a}-{b}"] = float(np.mean([stored[i, j] for i, j in sel]))

    spreads = {c: len(set(docs_)) for c, docs_ in real.bridge_entities.items()}
    spread_hist: dict[int, int] = {}
    for s in spreads.values():
        spread_hist[s] = spread_hist.get(s, 0) + 1
    cross_cluster = 0
    for c, docs_ in real.bridge_entities.items():
        if len({cluster_of.get(d) for d in set(docs_)}) > 1:
            cross_cluster += 1
    top_concepts = sorted(spreads.items(), key=lambda kv: (-kv[1], kv[0]))[:10]

    # Whole knowledge graph: communities and their agreement with topical clusters.
    ent_doc = {}
    for nid, a in kg.nodes(data=True):
        if a.get("node_type") == "entity":
            ent_doc[nid] = a.get("doc_id")
        elif a.get("node_type") == "document":
            ent_doc[nid] = nid
    Gk = nx.Graph()
    for u, v in und.edges():
        Gk.add_edge(u, v, weight=1.0)
    kcomms = nx.community.louvain_communities(Gk, seed=42)
    klab = {}
    for ci, members in enumerate(kcomms):
        for m in members:
            klab[m] = ci
    owned = [nid for nid in Gk.nodes if nid in ent_doc and ent_doc[nid] in cluster_of]
    kg_purity = purity([klab[n_] for n_ in owned], [cluster_of[ent_doc[n_]] for n_ in owned])
    kg_ari = adjusted_rand_score([cluster_of[ent_doc[n_]] for n_ in owned], [klab[n_] for n_ in owned])
    graph_stats = {
        "nodes": kg.number_of_nodes(), "edges": kg.number_of_edges(),
        "node_types": node_types, "edge_types": edge_types,
        "weak_components": nx.number_connected_components(und),
        "density_undirected": nx.density(und),
        "mean_degree": float(np.mean([d for _, d in und.degree()])),
        "kg_communities": len(kcomms),
        "kg_modularity": nx.community.modularity(Gk, kcomms),
        "kg_purity": kg_purity, "kg_ARI": float(kg_ari),
        "kg_largest_communities": sorted((len(c) for c in kcomms), reverse=True)[:6],
    }
    bridges = {
        "count": len(spreads), "spread_histogram": {str(k): v for k, v in sorted(spread_hist.items())},
        "mean_spread": float(np.mean(list(spreads.values()))),
        "cross_cluster_share": cross_cluster / max(len(spreads), 1),
        "top_concepts": top_concepts,
    }

    # ------------------------------------------------------------------ figure
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        tau = 0.50
        G = paper_graph(tau)
        pos = nx.spring_layout(G, weight="weight", seed=7, k=0.9)
        palette = ["#2f5d8a", "#b9792b", "#3d7a5c", "#8a4f7d", "#6b7785", "#a03a3a"]
        markers = {"A": "o", "B": "s", "C": "^", "D": "D"}
        assign = paper_net["full_weighted"]["assignment"]
        fig, ax = plt.subplots(figsize=(6.4, 5.0))
        for a, b, w in G.edges(data="weight"):
            ax.plot([pos[a][0], pos[b][0]], [pos[a][1], pos[b][1]], color="#9aa5b1",
                    lw=0.4 + 5 * (w - tau), alpha=0.7, zorder=1)
        for cl, mk in markers.items():
            nodes = [d for d in ids if cluster_of[d] == cl]
            ax.scatter([pos[d][0] for d in nodes], [pos[d][1] for d in nodes], marker=mk, s=110,
                       c=[palette[assign[d] % len(palette)] for d in nodes], edgecolors="#1f2933",
                       linewidths=0.8, zorder=2, label=f"Cluster {cl}")
        ax.set_axis_off()
        handles = [plt.Line2D([], [], marker=m, ls="", color="#6b7785", markeredgecolor="#1f2933",
                              label=f"Cluster {c} (truth)") for c, m in markers.items()]
        handles += [plt.Line2D([], [], marker="o", ls="", color=palette[i], markeredgecolor="#1f2933",
                               label=f"Community {i + 1} (found)") for i in range(len(comms_full))
                    if i < len(palette)]
        ax.legend(handles=handles, fontsize=7, loc="lower left", frameon=False, ncol=2)
        ax.set_title(f"Paper network (score ≥ {tau:.2f}): detected communities against topical clusters",
                     fontsize=9)
        fig.savefig(FIG_DIR / "graph_communities.png", dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print("  wrote graph_communities.png")
    except Exception as exc:  # the figure is a nicety; the numbers are what matter
        print("  figure skipped:", exc)

    # ------------------------------------------------------------------ contradictions
    print("Contradiction analysis (real corpus) ...")
    real_num = run_detector(real, use_nli=False)
    pairs_real, n_cand_real = claim_pairs(real)
    gates_real = gate_table(real, None)
    check = sum(1 for f in real_num if confirmed_at(f, 0.30, 0.60))
    print(f"  shipped detector (numeric): {len(real_num)} findings, {check} confirmed at defaults")
    print("  gate table (real):", [(r['config'], r['findings']) for r in gates_real])

    # The inference model over every real-corpus claim pair takes about twenty minutes on a
    # laptop CPU and the real corpus has no labels to score it against, so it is not run.
    real_nli = []

    print("Synthetic corpus ...")
    synth = run(ROOT / "data" / "papers", ROOT / "paper" / "_run_synth")
    synth_num = run_detector(synth, use_nli=False)
    synth_nli = run_detector(synth, use_nli=True)
    gates_synth = gate_table(synth, PLANTED)

    def summarise(findings, label_planted: set | None):
        conf = [f for f in findings if confirmed_at(f, 0.30, 0.60)]
        found = {pair_key(f) for f in conf}
        return {"findings": len(findings), "confirmed_findings": len(conf), "confirmed_pairs": len(found),
                **prf(found, label_planted)}

    detectors = {
        "real_numeric": summarise(real_num, None),
        "synthetic_numeric": summarise(synth_num, PLANTED),
        "synthetic_numeric_nli": summarise(synth_nli, PLANTED),
    }
    print("  detectors:", json.dumps(detectors, indent=1, default=str)[:1500])

    sims = [0.1, 0.2, 0.3, 0.4, 0.5]
    confs = [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    def grid(findings, planted):
        rows = []
        for s in sims:
            for c in confs:
                conf_f = [f for f in findings if confirmed_at(f, s, c)]
                found = {pair_key(f) for f in conf_f}
                row = {"sim": s, "conf": c, "findings": len(conf_f), "pairs": len(found)}
                row.update(prf(found, planted))
                rows.append(row)
        return rows

    sensitivity = {
        "real_numeric": grid(real_num, None),
        "synthetic_numeric": grid(synth_num, PLANTED),
        "synthetic_numeric_nli": grid(synth_nli, PLANTED),
    }

    cand_sweep = []
    for thr in (0.20, 0.30, 0.35, 0.40, 0.50, 0.60):
        r_f = run_detector(real, use_nli=False, candidate_threshold=thr)
        s_f = run_detector(synth, use_nli=False, candidate_threshold=thr)
        old = C._CANDIDATE_SCORE_THRESHOLD
        C._CANDIDATE_SCORE_THRESHOLD = thr
        n_real = len(C._build_candidate_pairs(real.scores, real.bridge_entities))
        n_synth = len(C._build_candidate_pairs(synth.scores, synth.bridge_entities))
        C._CANDIDATE_SCORE_THRESHOLD = old
        s_conf = {pair_key(f) for f in s_f if confirmed_at(f, 0.30, 0.60)}
        cand_sweep.append({
            "threshold": thr, "candidate_pairs_real": n_real, "candidate_pairs_synth": n_synth,
            "real_findings": len(r_f), "real_confirmed": sum(1 for f in r_f if confirmed_at(f, 0.30, 0.60)),
            "synth_findings": len(s_f), **prf(s_conf, PLANTED),
        })

    # ------------------------------------------------------------------ provenance
    print("Provenance audit ...")
    docs_real = {d.id: d for d in real.documents}
    gap_trails = [t for g in real.gaps for t in g.evidence]
    prov_gaps = audit_trails(gap_trails, docs_real, ROOT / "dataset" / "papers")
    docs_synth = {d.id: d for d in synth.documents}
    synth_conf = [f for f in synth_nli if confirmed_at(f, 0.30, 0.60)]
    synth_conf_num = [f for f in synth_num if confirmed_at(f, 0.30, 0.60)]
    con_trails = [t for f in synth_conf_num for t in f.evidence]
    prov_con = audit_trails(con_trails, docs_synth, ROOT / "data" / "papers")

    payload = {
        "n_papers": n, "n_pairs": int(len(iu[0])), "n_relevant_pairs": n_rel,
        "reproduces_paper_matrix_max_abs_diff": reproduces,
        "ranking": ranking, "extra_baselines": extra,
        "ablation": ablation, "random_weights": random_weights,
        "paper_network": paper_net, "hubs": hubs, "cluster_means": cluster_matrix,
        "graph": graph_stats, "bridges": bridges,
        "contradictions": {
            "gates_real": gates_real, "gates_synth": gates_synth,
            "gate_definitions": GATES, "detectors": detectors,
            "sensitivity": sensitivity, "candidate_sweep": cand_sweep,
            "real_claim_pairs": len(pairs_real), "real_candidate_pairs": n_cand_real,
        },
        "provenance": {"gaps": prov_gaps, "planted_contradictions": prov_con},
        "seconds": time.time() - t0,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=1, default=float), encoding="utf-8")
    print(f"wrote {OUT_JSON} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
