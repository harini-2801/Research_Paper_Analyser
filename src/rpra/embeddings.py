"""
Semantic Embedding and Vector Representation (Requirement 16).

Provides a single `EmbeddingBackend` that turns text into dense vectors.

Two backends are supported, selected automatically:

``sentence-transformers``
    Preferred.  Loads the model named in ``config.embedding.model``.

``tfidf``
    Deterministic pure-NumPy fallback used when the transformer model cannot be
    loaded (no network, no cache, missing package).  It fits a TF-IDF space over
    the corpus itself and reduces it with a seeded random projection, so vectors
    remain comparable within a run and cosine similarity stays meaningful.

The fallback matters: without it a machine with no model cache produces an
all-zero similarity matrix, which silently collapses every relationship score
down to the dataset-overlap term alone.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import time
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

from rpra.models import (
    Document,
    Entity,
    PipelineStageStatus,
    ProgressEvent,
)

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\-_/\.]*")

# Words that carry no discriminative signal between research papers.
_STOPWORDS: frozenset[str] = frozenset(
    (
        "a", "an", "the", "and", "or", "but", "if", "then", "else", "of", "for", "to", "in",
        "on", "at", "by", "with", "from", "as", "is", "are", "was", "were", "be", "been",
        "being", "this", "that", "these", "those", "it", "its", "we", "our", "us", "they",
        "their", "he", "she", "his", "her", "you", "your", "i", "can", "could", "may",
        "might", "shall", "should", "will", "would", "must", "do", "does", "did", "done",
        "have", "has", "had", "not", "no", "nor", "so", "than", "too", "very", "just",
        "also", "more", "most", "other", "some", "such", "only", "own", "same", "which",
        "who", "whom", "what", "when", "where", "why", "how", "all", "any", "both", "each",
        "few", "using", "used", "use", "uses", "based", "paper", "work", "approach",
        "propose", "proposed", "results", "result",
    )
)

_FALLBACK_DIM = 256
_PROJECTION_SEED = 20260915


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens with stopwords and single-character noise removed."""
    return [
        tok
        for tok in _TOKEN_RE.findall(text.lower())
        if len(tok) > 1 and tok not in _STOPWORDS
    ]


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------


class EmbeddingBackend:
    """
    Encodes text into L2-normalised vectors.

    Parameters
    ----------
    model_name:
        sentence-transformers model identifier.
    device:
        ``cpu`` | ``cuda`` | ``mps``.
    batch_size:
        Encoding batch size for the transformer backend.
    prefer_transformer:
        When False, skips the transformer entirely and uses TF-IDF.  Useful for
        fast tests and for air-gapped runs.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
        batch_size: int = 32,
        prefer_transformer: bool = True,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model = None
        self.kind: str = "uninitialised"

        # TF-IDF fallback state
        self._vocab: dict[str, int] = {}
        self._idf: np.ndarray | None = None
        self._projection: np.ndarray | None = None

        if prefer_transformer:
            self._try_load_transformer()
        else:
            self.kind = "tfidf"

    # ------------------------------------------------------------------
    # Backend selection
    # ------------------------------------------------------------------

    def _try_load_transformer(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
            self.kind = "sentence-transformers"
            logger.info("Embedding backend: sentence-transformers (%s)", self.model_name)
        except Exception as exc:
            logger.warning(
                "Could not load embedding model '%s' (%s). "
                "Falling back to the deterministic TF-IDF backend.",
                self.model_name,
                exc,
            )
            self._model = None
            self.kind = "tfidf"

    @property
    def dimension(self) -> int:
        if self._model is not None:
            # sentence-transformers renamed this in v5; support both.
            getter = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
            return int(getter())
        return _FALLBACK_DIM

    # ------------------------------------------------------------------
    # TF-IDF fallback
    # ------------------------------------------------------------------

    def fit(self, corpus: Sequence[str]) -> EmbeddingBackend:
        """
        Fit the TF-IDF vocabulary on *corpus*.

        No-op for the transformer backend.  Safe to call unconditionally.
        """
        if self._model is not None:
            return self

        doc_freq: Counter[str] = Counter()
        for text in corpus:
            doc_freq.update(set(_tokenize(text)))

        # Drop hapax terms only when the corpus is big enough for that to be safe.
        min_df = 2 if len(corpus) >= 20 else 1
        terms = sorted(t for t, df in doc_freq.items() if df >= min_df)

        n_docs = max(len(corpus), 1)
        self._vocab = {term: i for i, term in enumerate(terms)}
        self._idf = np.array(
            [math.log((1.0 + n_docs) / (1.0 + doc_freq[t])) + 1.0 for t in terms],
            dtype=np.float32,
        )

        # Seeded random projection keeps the output dimension fixed and the run
        # reproducible across machines.
        rng = np.random.default_rng(_PROJECTION_SEED)
        self._projection = rng.normal(
            0.0, 1.0 / math.sqrt(_FALLBACK_DIM), size=(len(terms), _FALLBACK_DIM)
        ).astype(np.float32)

        logger.info("TF-IDF backend fitted: %d terms, %d documents", len(terms), n_docs)
        return self

    def _encode_tfidf(self, texts: Sequence[str]) -> np.ndarray:
        if self._idf is None or self._projection is None:
            # Never fitted - fall back to hashing so we still return usable vectors.
            return np.vstack([self._hash_vector(t) for t in texts])

        out = np.zeros((len(texts), _FALLBACK_DIM), dtype=np.float32)
        for row, text in enumerate(texts):
            counts = Counter(tok for tok in _tokenize(text) if tok in self._vocab)
            if not counts:
                out[row] = self._hash_vector(text)
                continue
            sparse = np.zeros(len(self._vocab), dtype=np.float32)
            max_tf = max(counts.values())
            for term, tf in counts.items():
                idx = self._vocab[term]
                sparse[idx] = (0.5 + 0.5 * tf / max_tf) * self._idf[idx]
            out[row] = sparse @ self._projection
        return out

    @staticmethod
    def _hash_vector(text: str) -> np.ndarray:
        """
        Last-resort encoder for text with no in-vocabulary terms.

        Hashes character 4-grams into a fixed-width vector so that identical and
        near-identical strings still land close together.
        """
        vec = np.zeros(_FALLBACK_DIM, dtype=np.float32)
        cleaned = re.sub(r"\s+", " ", text.lower().strip())
        if not cleaned:
            return vec
        for i in range(max(len(cleaned) - 3, 1)):
            gram = cleaned[i : i + 4]
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=4).digest()
            idx = int.from_bytes(digest, "big") % _FALLBACK_DIM
            vec[idx] += 1.0
        return vec

    # ------------------------------------------------------------------
    # Encoding
    # ------------------------------------------------------------------

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return an ``(n, dim)`` array of L2-normalised embeddings."""
        if len(texts) == 0:
            return np.zeros((0, self.dimension), dtype=np.float32)

        if self._model is not None:
            vectors = self._model.encode(
                list(texts),
                batch_size=self.batch_size,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            return np.asarray(vectors, dtype=np.float32)

        return _l2_normalise(self._encode_tfidf(texts))

    def encode_one(self, text: str) -> list[float]:
        """Encode a single string and return it as a plain list."""
        return self.encode([text])[0].tolist()


def _l2_normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return (matrix / norms).astype(np.float32)


# ---------------------------------------------------------------------------
# Pipeline stage
# ---------------------------------------------------------------------------


def _entity_context(entity: Entity) -> str:
    """
    Text used to represent an entity in vector space.

    The sentence it was found in carries far more signal than the span alone, so
    both are included when available.
    """
    span = (entity.sentence_span or "").strip()
    text = entity.text.strip()
    if span and span.lower() != text.lower():
        return f"{text}. {span}"
    return text


def embed_entities(
    entities: list[Entity],
    documents: list[Document] | None = None,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    device: str = "cpu",
    batch_size: int = 32,
    prefer_transformer: bool = True,
    backend: EmbeddingBackend | None = None,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> EmbeddingBackend:
    """
    Populate ``Entity.embedding`` for every entity, in place.

    *documents* is used only to fit the TF-IDF fallback on full section text,
    which gives far better IDF estimates than entity spans alone.

    Returns the backend so later stages can reuse it without reloading a model.
    """

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    start = time.perf_counter()
    emit(
        ProgressEvent(
            stage="embedding",
            status=PipelineStageStatus.RUNNING,
            message=f"Encoding {len(entities)} entities",
        )
    )

    if backend is None:
        backend = EmbeddingBackend(
            model_name=model_name,
            device=device,
            batch_size=batch_size,
            prefer_transformer=prefer_transformer,
        )

    if not entities:
        emit(
            ProgressEvent(
                stage="embedding",
                status=PipelineStageStatus.COMPLETE,
                message="No entities to encode",
                details={"backend": backend.kind, "encoded": 0},
            )
        )
        return backend

    # Fit the fallback vocabulary on the richest text available.
    fit_corpus: list[str] = []
    if documents:
        fit_corpus = [seg.text for doc in documents for seg in doc.segments if seg.text]
    if not fit_corpus:
        fit_corpus = [_entity_context(e) for e in entities]
    backend.fit(fit_corpus)

    contexts = [_entity_context(e) for e in entities]
    try:
        vectors = backend.encode(contexts)
    except Exception as exc:
        elapsed = time.perf_counter() - start
        logger.error("Entity encoding failed: %s", exc)
        emit(
            ProgressEvent(
                stage="embedding",
                status=PipelineStageStatus.FAILED,
                message=f"Embedding failed: {exc}",
                elapsed_seconds=round(elapsed, 2),
            )
        )
        return backend

    for entity, vector in zip(entities, vectors):
        entity.embedding = vector.tolist()

    elapsed = time.perf_counter() - start
    emit(
        ProgressEvent(
            stage="embedding",
            status=PipelineStageStatus.COMPLETE,
            message=(
                f"Encoded {len(entities)} entities "
                f"({backend.dimension}-d, backend={backend.kind})"
            ),
            details={
                "backend": backend.kind,
                "encoded": len(entities),
                "dimension": backend.dimension,
            },
            elapsed_seconds=round(elapsed, 2),
        )
    )
    return backend


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_embeddings(entities: list[Entity], path: str | Path) -> Path | None:
    """Persist entity vectors to a compressed ``.npz`` keyed by entity UUID."""
    vectors = [(str(e.id), e.embedding) for e in entities if e.embedding]
    if not vectors:
        return None

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ids = np.array([vid for vid, _ in vectors], dtype=object)
    matrix = np.array([vec for _, vec in vectors], dtype=np.float32)
    np.savez_compressed(path, ids=ids, vectors=matrix)
    return path


def load_embeddings(path: str | Path) -> dict[str, list[float]]:
    """Load vectors saved by :func:`save_embeddings`, keyed by entity UUID."""
    path = Path(path)
    if not path.exists():
        return {}
    with np.load(path, allow_pickle=True) as data:
        ids = data["ids"]
        vectors = data["vectors"]
    return {str(i): v.tolist() for i, v in zip(ids, vectors)}
