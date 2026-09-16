"""
The arXiv evaluation corpus: 30 real papers in four topical clusters.

Papers are fetched from arXiv at runtime rather than committed to this
repository. They are third-party copyrighted works - redistributing 48 MB of
other people's PDFs through a public repo is not ours to do, and it would make
a 3 MB repository fifteen times larger. Downloading them on demand is what a
reader would do anyway.

Why these thirty, and why clustered, is explained in
:mod:`rpra.sample_corpus`'s counterpart: a random sample cannot evaluate this
system, because contradiction detection only fires on shared benchmarks and
relationship scoring needs both pairs that should rank high and pairs that
should rank low. The four clusters supply both, plus real cross-citations.

arXiv asks automated clients to identify themselves and to leave a few seconds
between requests. Both are honoured here, and anything already on disk is
skipped, so a re-run downloads nothing.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

USER_AGENT = "RPRA/0.1 (student research project; +https://github.com/harini-2801/Research_Paper_Analyser)"
REQUEST_DELAY_SECONDS = 3.0
PDF_URL = "https://arxiv.org/pdf/{arxiv_id}"

# Below this a file is a truncated download or an error page, not a paper.
_MIN_PDF_BYTES = 10_000


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


def known_slugs() -> set[str]:
    """Filenames (without extension) this module writes, for cross-cleanup."""
    return {paper["slug"] for paper in PAPERS}


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def _is_complete(path: Path) -> bool:
    return path.exists() and path.stat().st_size > _MIN_PDF_BYTES


def local_dataset_dir() -> Path | None:
    """
    The checked-in copy of the corpus, if this is running from the repository.

    Downloading thirty papers takes about two minutes and needs arXiv to be
    reachable, which makes a first run look broken on a slow connection and
    impossible offline. When the repository's own `dataset/papers` directory is
    present it is used as the source instead, so loading the full corpus is a
    file copy.
    """
    candidate = Path(__file__).resolve().parents[2] / "dataset" / "papers"
    return candidate if candidate.is_dir() else None


def _copy_from_local_dataset(slug: str, destination: Path) -> bool:
    """Satisfy one paper from the bundled dataset. False if it is not there."""
    source_dir = local_dataset_dir()
    if source_dir is None:
        return False
    source = source_dir / f"{slug}.pdf"
    if not _is_complete(source):
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return True


def download_paper(arxiv_id: str, destination: Path, slug: str | None = None) -> tuple[bool, str]:
    """
    Fetch one PDF, skipping anything already on disk.

    Returns ``(ok, message)`` rather than raising, so one unavailable paper
    cannot abort the rest of the corpus.
    """
    if _is_complete(destination):
        return True, "cached"

    if slug and _copy_from_local_dataset(slug, destination):
        return True, "from bundled dataset"

    request = urllib.request.Request(
        PDF_URL.format(arxiv_id=arxiv_id), headers={"User-Agent": USER_AGENT}
    )
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


def missing_papers(out_dir: str | Path) -> list[dict]:
    """Which papers still need fetching over the network."""
    out_dir = Path(out_dir)
    source_dir = local_dataset_dir()
    return [
        p
        for p in PAPERS
        if not _is_complete(out_dir / f"{p['slug']}.pdf")
        and not (source_dir and _is_complete(source_dir / f"{p['slug']}.pdf"))
    ]


def fetch_corpus(
    out_dir: str | Path,
    on_progress: Callable[[int, int, str, bool], None] | None = None,
    delay_seconds: float = REQUEST_DELAY_SECONDS,
) -> dict:
    """
    Download the corpus into *out_dir*.

    *on_progress* receives ``(index, total, slug, ok)`` after each paper so a
    caller can report progress; a download of this length with no feedback looks
    like a hang.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    succeeded: list[dict] = []
    failed: list[dict] = []
    downloaded = 0

    for index, paper in enumerate(PAPERS, start=1):
        target = out_dir / f"{paper['slug']}.pdf"
        was_cached = _is_complete(target)

        ok, message = download_paper(paper["id"], target, slug=paper["slug"])
        if ok:
            succeeded.append({**paper, "file": target.name})
        else:
            failed.append({**paper, "reason": message})
            logger.warning("Could not fetch %s: %s", paper["slug"], message)

        if on_progress:
            on_progress(index, len(PAPERS), paper["slug"], ok)

        # Only pause after a real request; cached papers cost nothing.
        if ok and not was_cached:
            downloaded += 1
            if message != "from bundled dataset" and index < len(PAPERS):
                time.sleep(delay_seconds)

    manifest = {
        "source": "arXiv",
        "clusters": CLUSTER_NAMES,
        "papers": succeeded,
        "failed": failed,
        "counts": {
            "requested": len(PAPERS),
            "available": len(succeeded),
            "failed": len(failed),
            "downloaded_this_run": downloaded,
        },
    }
    (out_dir / "corpus_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest
