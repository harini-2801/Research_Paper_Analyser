"""
Download a real evaluation corpus of 30 papers from arXiv.

Why a curated list rather than a random sample
----------------------------------------------
A random sample of 30 papers cannot evaluate this system. Contradiction
detection only fires when two papers report values for the same metric on the
same dataset; relationship scoring can only be judged if the corpus contains
both pairs that *should* score high and pairs that *should* score low. A random
draw gives you almost no shared benchmarks and no negative controls.

So the corpus is built as four topical clusters:

    A  Convolutional image classification   - shared: ImageNet, CIFAR, top-1/top-5
    B  Pretrained language models           - shared: GLUE, SQuAD, F1/EM
    C  Vision transformers & self-supervised- shared: ImageNet, linear-probe acc
    D  Retrieval, IE and knowledge graphs   - shared: retrieval and IE benchmarks

This yields, by construction:

  * true positives  - within-cluster pairs share a task and a benchmark
  * true negatives  - cross-cluster pairs (A vs D) share almost nothing
  * real citations  - these papers cite each other densely
  * real contradictions - independent papers report different numbers for the
    same baseline on the same dataset. This is a genuine and well-documented
    phenomenon in this literature, not something planted.

`corpus_manifest.json` records the intended cluster of each paper, which is the
ground truth for the relationship-ranking evaluation in `evaluate_corpus.py`.

Politeness
----------
arXiv asks automated clients to identify themselves and to leave a few seconds
between requests. This script does both and caches, so re-running it downloads
nothing. Please do not lower the delay.

Usage
-----
    python scripts/fetch_eval_corpus.py [output_dir]

Defaults to ./data/eval_corpus.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "RPRA-eval/0.1 (student research project; contact via repository)"
REQUEST_DELAY_SECONDS = 3.0
PDF_URL = "https://arxiv.org/pdf/{arxiv_id}"


# ---------------------------------------------------------------------------
# The corpus
# ---------------------------------------------------------------------------

PAPERS: list[dict] = [
    # -- Cluster A: convolutional image classification ----------------------
    # All report ImageNet top-1/top-5 and most report CIFAR. They cite each
    # other heavily, and their reported baselines for the *same* architecture
    # disagree - which is exactly what contradiction detection should surface.
    {"id": "1409.1556", "cluster": "A", "slug": "vgg_very_deep_2014",
     "title": "Very Deep Convolutional Networks for Large-Scale Image Recognition"},
    {"id": "1502.03167", "cluster": "A", "slug": "batchnorm_2015",
     "title": "Batch Normalization: Accelerating Deep Network Training"},
    {"id": "1512.03385", "cluster": "A", "slug": "resnet_2015",
     "title": "Deep Residual Learning for Image Recognition"},
    {"id": "1605.07146", "cluster": "A", "slug": "wide_resnet_2016",
     "title": "Wide Residual Networks"},
    {"id": "1608.06993", "cluster": "A", "slug": "densenet_2016",
     "title": "Densely Connected Convolutional Networks"},
    {"id": "1704.04861", "cluster": "A", "slug": "mobilenets_2017",
     "title": "MobileNets: Efficient Convolutional Neural Networks for Mobile Vision"},
    {"id": "1709.01507", "cluster": "A", "slug": "squeeze_excitation_2017",
     "title": "Squeeze-and-Excitation Networks"},
    {"id": "1905.11946", "cluster": "A", "slug": "efficientnet_2019",
     "title": "EfficientNet: Rethinking Model Scaling for Convolutional Neural Networks"},

    # -- Cluster B: pretrained language models ------------------------------
    # Shared benchmarks: GLUE, SQuAD. RoBERTa explicitly reports that BERT was
    # undertrained and gives different numbers for the same setup - a textbook
    # cross-paper contradiction.
    {"id": "1706.03762", "cluster": "B", "slug": "attention_is_all_you_need_2017",
     "title": "Attention Is All You Need"},
    {"id": "1810.04805", "cluster": "B", "slug": "bert_2018",
     "title": "BERT: Pre-training of Deep Bidirectional Transformers"},
    {"id": "1906.08237", "cluster": "B", "slug": "xlnet_2019",
     "title": "XLNet: Generalized Autoregressive Pretraining for Language Understanding"},
    {"id": "1907.11692", "cluster": "B", "slug": "roberta_2019",
     "title": "RoBERTa: A Robustly Optimized BERT Pretraining Approach"},
    {"id": "1909.11942", "cluster": "B", "slug": "albert_2019",
     "title": "ALBERT: A Lite BERT for Self-supervised Learning"},
    {"id": "1910.01108", "cluster": "B", "slug": "distilbert_2019",
     "title": "DistilBERT, a distilled version of BERT"},
    {"id": "1910.10683", "cluster": "B", "slug": "t5_2019",
     "title": "Exploring the Limits of Transfer Learning with a Unified Text-to-Text Transformer"},
    {"id": "2003.10555", "cluster": "B", "slug": "electra_2020",
     "title": "ELECTRA: Pre-training Text Encoders as Discriminators"},

    # -- Cluster C: vision transformers and self-supervised vision ----------
    # Shared: ImageNet, linear-probe and fine-tune accuracy. Overlaps cluster A
    # on dataset but differs on method, which tests whether scoring separates
    # "same benchmark" from "same approach".
    {"id": "1911.05722", "cluster": "C", "slug": "moco_2019",
     "title": "Momentum Contrast for Unsupervised Visual Representation Learning"},
    {"id": "2002.05709", "cluster": "C", "slug": "simclr_2020",
     "title": "A Simple Framework for Contrastive Learning of Visual Representations"},
    {"id": "2006.07733", "cluster": "C", "slug": "byol_2020",
     "title": "Bootstrap Your Own Latent: A New Approach to Self-Supervised Learning"},
    {"id": "2010.11929", "cluster": "C", "slug": "vit_2020",
     "title": "An Image is Worth 16x16 Words: Transformers for Image Recognition"},
    {"id": "2012.12877", "cluster": "C", "slug": "deit_2020",
     "title": "Training data-efficient image transformers & distillation"},
    {"id": "2103.00020", "cluster": "C", "slug": "clip_2021",
     "title": "Learning Transferable Visual Models From Natural Language Supervision"},
    {"id": "2103.14030", "cluster": "C", "slug": "swin_transformer_2021",
     "title": "Swin Transformer: Hierarchical Vision Transformer using Shifted Windows"},
    {"id": "2111.06377", "cluster": "C", "slug": "mae_2021",
     "title": "Masked Autoencoders Are Scalable Vision Learners"},

    # -- Cluster D: retrieval, information extraction, knowledge graphs -----
    # Closest to this project's own subject. Shares almost nothing with
    # cluster A, so A-vs-D pairs are the negative control.
    {"id": "1903.10676", "cluster": "D", "slug": "scibert_2019",
     "title": "SciBERT: A Pretrained Language Model for Scientific Text"},
    {"id": "1906.06127", "cluster": "D", "slug": "docred_2019",
     "title": "DocRED: A Large-Scale Document-Level Relation Extraction Dataset"},
    {"id": "2004.04906", "cluster": "D", "slug": "dpr_2020",
     "title": "Dense Passage Retrieval for Open-Domain Question Answering"},
    {"id": "2004.07180", "cluster": "D", "slug": "specter_2020",
     "title": "SPECTER: Document-level Representation Learning using Citation-informed Transformers"},
    {"id": "2005.11401", "cluster": "D", "slug": "rag_2020",
     "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"},
    {"id": "2002.00388", "cluster": "D", "slug": "kg_survey_2020",
     "title": "A Survey on Knowledge Graphs: Representation, Acquisition and Applications"},
]

CLUSTER_NAMES = {
    "A": "Convolutional image classification",
    "B": "Pretrained language models",
    "C": "Vision transformers and self-supervised vision",
    "D": "Retrieval, information extraction and knowledge graphs",
}


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def download_pdf(arxiv_id: str, destination: Path) -> tuple[bool, str]:
    """
    Fetch one PDF. Returns (ok, message).

    A file already on disk is left alone, so the script is safe to re-run and
    does not re-hit arXiv for papers it already has.
    """
    if destination.exists() and destination.stat().st_size > 10_000:
        return True, "cached"

    url = PDF_URL.format(arxiv_id=arxiv_id)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

    if not payload.startswith(b"%PDF"):
        return False, "response was not a PDF"

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return True, f"{len(payload) // 1024} KB"


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "./data/eval_corpus")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {len(PAPERS)} papers from arXiv into {out_dir.resolve()}")
    print(f"Delay between requests: {REQUEST_DELAY_SECONDS}s (please do not lower)\n")

    succeeded: list[dict] = []
    failed: list[dict] = []
    fetched_this_run = 0

    for index, paper in enumerate(PAPERS, start=1):
        target = out_dir / f"{paper['slug']}.pdf"
        was_cached = target.exists() and target.stat().st_size > 10_000

        ok, message = download_pdf(paper["id"], target)
        marker = "ok " if ok else "FAIL"
        print(f"  [{index:2d}/{len(PAPERS)}] {marker} {paper['slug']:38s} {message}")

        if ok:
            succeeded.append({**paper, "file": target.name})
        else:
            failed.append({**paper, "reason": message})

        if ok and not was_cached:
            fetched_this_run += 1
            if index < len(PAPERS):
                time.sleep(REQUEST_DELAY_SECONDS)

    manifest = {
        "source": "arXiv",
        "clusters": CLUSTER_NAMES,
        "papers": succeeded,
        "failed": failed,
        "counts": {
            "requested": len(PAPERS),
            "available": len(succeeded),
            "failed": len(failed),
            "downloaded_this_run": fetched_this_run,
        },
    }
    manifest_path = out_dir / "corpus_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n{len(succeeded)}/{len(PAPERS)} available, {fetched_this_run} newly downloaded")
    print(f"Manifest: {manifest_path}")
    if failed:
        print("\nFailed:")
        for item in failed:
            print(f"  {item['slug']} ({item['id']}): {item['reason']}")

    print("\nNext:")
    print(f"  python scripts/evaluate_corpus.py {out_dir}")
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
