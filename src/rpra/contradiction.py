"""
Contradiction Detection (Requirement 7).

Combines NLI stance classification with contextual signals - dataset
compatibility, metric comparability, methodology similarity - to separate
genuine scientific disagreement from claims that merely sound different.

Confirmation rule (Req 7.4):

    NLI label == contradiction
    AND nli_confidence >= threshold
    AND (datasets compatible OR metrics comparable)
    AND methodology_similarity >= threshold

Two detectors run and their results are merged:

`nli`
    A cross-encoder NLI model scores claim pairs. Requires the model to load.

`numeric`
    A domain rule: two papers reporting materially different values for the
    same metric on the same dataset are contradicting each other, whatever the
    surface wording. This runs unconditionally - it is cheap, needs no model,
    and catches the most consequential class of disagreement in empirical work.
    It is also the only detector available when the NLI model cannot be loaded.
"""

from __future__ import annotations

import itertools
import logging
import re
import time
from collections.abc import Callable

from rpra.claims import (
    analyse_claim,
    comparable_measurements,
    repair_spaced_decimals,
)
from rpra.models import (
    Contradiction,
    ContradictionStatus,
    Document,
    Entity,
    EntityType,
    EvidenceTrail,
    NLILabel,
    PipelineStageStatus,
    ProgressEvent,
    RelationshipScore,
)

logger = logging.getLogger(__name__)

# Bound the work: claim pairs grow quadratically with corpus size.
_MAX_CLAIMS_PER_DOC = 8
_MAX_PAIRS_PER_DOC_PAIR = 24
_CANDIDATE_SCORE_THRESHOLD = 0.35
# Keyed by model name. Loading transformers weights costs several seconds and
# the result is identical across runs, so - like the embedding model - it is
# shared for the life of the process instead of reloaded on every analysis.
_NLI_MODEL_CACHE: dict[str, object] = {}

# One disagreement restated across several sentences is still one finding.
_MAX_FINDINGS_PER_DOC_PAIR = 3

# Two reported values are treated as disagreeing past this relative difference.
_NUMERIC_DISAGREEMENT_RATIO = 0.05
# Confidence floor for a numeric disagreement that clears the threshold, and the
# relative gap at which confidence saturates.
_NUMERIC_BASE_CONFIDENCE = 0.62
_NUMERIC_SATURATION_RATIO = 0.30

# A claim only counts if the sentence actually asserts a measured outcome.
# Discursive sentences ("In Sec. 4.2, we apply Batch Normalization to ...")
# mention a dataset and a number without stating a result, and were the main
# source of false positives on real papers.
_RESULT_ASSERTION_RE = re.compile(
    r"\b(achiev\w*|reach\w*|obtain\w*|attain\w*|yield\w*|report\w*|scores?|scored|"
    r"improv\w*|outperform\w*|surpass\w*|exceed\w*|"
    r"accuracy\s+of|error\s+rate\s+of|performance\s+of|results?\s+in)",
    re.IGNORECASE,
)

# Metrics where lower is better. Comparing an error rate against an accuracy is
# comparing inverted scales, so any gap between them is meaningless.
_LOWER_IS_BETTER_RE = re.compile(
    r"\b(error\s+rate|error|perplexity|loss|wer|cer|mae|rmse|mse|latency)\b",
    re.IGNORECASE,
)
_HIGHER_IS_BETTER_RE = re.compile(
    r"\b(accuracy|f1|precision|recall|bleu|rouge|auc|map|miou|iou|ndcg|mrr|"
    r"exact\s+match|dice)\b",
    re.IGNORECASE,
)

# Sentences pointing elsewhere in the paper are describing, not claiming.
_CROSS_REFERENCE_RE = re.compile(
    r"\b(see|in)\s+(sec\.|sec\b|section|table|fig\.|fig\b|figure|appendix)|"
    r"\bas\s+(detailed|described|shown|discussed)\b",
    re.IGNORECASE,
)

_VALUE_RE = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%|"          # 92.4%
    r"\b(0\.\d{2,4})\b|"                  # 0.923
    r"\b(\d{1,3}\.\d{1,2})\b"             # 92.4
)


# ---------------------------------------------------------------------------
# Candidate claim extraction
# ---------------------------------------------------------------------------


def _extract_claims(entities: list[Entity]) -> list[Entity]:
    """
    Return entities carrying testable claims, most comparable first.

    Quantitative results lead because they are the claims a contradiction can
    actually be adjudicated on; objectives and methodologies follow.
    """
    priority = {
        EntityType.QUANTITATIVE_RESULT: 0,
        EntityType.METHODOLOGY: 1,
        EntityType.OBJECTIVE: 2,
    }
    claims = [e for e in entities if e.entity_type in priority and e.sentence_span.strip()]
    claims.sort(key=lambda e: (priority[e.entity_type], -len(e.sentence_span)))
    return claims[:_MAX_CLAIMS_PER_DOC]


def _datasets_compatible(entities_a: list[Entity], entities_b: list[Entity]) -> bool:
    """True when the two documents share at least one dataset name."""
    ds_a = {e.text.lower().strip() for e in entities_a if e.entity_type == EntityType.DATASET}
    ds_b = {e.text.lower().strip() for e in entities_b if e.entity_type == EntityType.DATASET}
    return bool(ds_a & ds_b)


def _metrics_comparable(entities_a: list[Entity], entities_b: list[Entity]) -> bool:
    """True when both documents use at least one common evaluation metric."""
    met_a = {
        e.text.lower().strip()
        for e in entities_a
        if e.entity_type == EntityType.EVALUATION_METRIC
    }
    met_b = {
        e.text.lower().strip()
        for e in entities_b
        if e.entity_type == EntityType.EVALUATION_METRIC
    }
    return bool(met_a & met_b)


def _shared_terms(entities_a: list[Entity], entities_b: list[Entity]) -> set[str]:
    """Dataset and metric names present in both documents."""
    comparable = {EntityType.DATASET, EntityType.EVALUATION_METRIC}
    a = {e.text.lower().strip() for e in entities_a if e.entity_type in comparable}
    b = {e.text.lower().strip() for e in entities_b if e.entity_type in comparable}
    return a & b


def _dataset_names(entities: list[Entity]) -> set[str]:
    return {
        e.text.lower().strip()
        for e in entities
        if e.entity_type == EntityType.DATASET
    }


def _model_names(entities: list[Entity]) -> set[str]:
    return {
        e.text.lower().strip()
        for e in entities
        if e.entity_type == EntityType.MODEL
    }


# ---------------------------------------------------------------------------
# Numeric claim comparison
# ---------------------------------------------------------------------------


def parse_reported_values(sentence: str) -> list[float]:
    """
    Pull reported scores out of a sentence, normalised to the 0-1 range.

    Percentages are divided by 100 so that "92.4%" and "0.924" compare equal.
    Values that cannot be a score once normalised are dropped. Decimal points
    that PDF extraction split with spaces are rejoined first, so "82 . 9%" reads
    as 82.9% rather than 9%.
    """
    sentence = repair_spaced_decimals(sentence)
    values: list[float] = []
    for match in _VALUE_RE.finditer(sentence):
        percent, decimal, bare = match.groups()
        if percent is not None:
            value = float(percent) / 100.0
        elif decimal is not None:
            value = float(decimal)
        else:
            value = float(bare)
            if value > 1.0:
                value /= 100.0
        if 0.0 < value <= 1.0:
            values.append(round(value, 4))
    return values


def _value_polarity(sentence: str) -> tuple[float, str | None] | None:
    """
    Return the headline value in *sentence* and whether higher or lower is better.

    Polarity is read from the words immediately around the number, not from the
    sentence as a whole. That distinction matters: "reaching 4.9% top-5
    validation error (and 4.8% test error), exceeding the accuracy of human
    raters" contains both "error" and "accuracy", so a whole-sentence test
    cannot tell which one the 4.9% belongs to.
    """
    best: tuple[float, str | None] | None = None

    for match in _VALUE_RE.finditer(sentence):
        percent, decimal, bare = match.groups()
        if percent is not None:
            value = float(percent) / 100.0
        elif decimal is not None:
            value = float(decimal)
        else:
            value = float(bare)
            if value > 1.0:
                value /= 100.0
        if not 0.0 < value <= 1.0:
            continue

        window = sentence[max(0, match.start() - 45) : match.end() + 45]
        lower = _LOWER_IS_BETTER_RE.search(window)
        higher = _HIGHER_IS_BETTER_RE.search(window)
        if lower and not higher:
            polarity = "lower"
        elif higher and not lower:
            polarity = "higher"
        else:
            polarity = None

        if best is None or value > best[0]:
            best = (value, polarity)

    return best


def _mentions_model(text: str, term: str) -> bool:
    """
    Whole-term match that tolerates a model-variant suffix.

    Models are named by family and then specialised: ViT-B/16, ResNet-101,
    BERT-base. For deciding *which system* a claim is about, the family is
    what matters, so `ViT` must match `ViT-B/16`. Datasets are matched
    strictly instead, because CIFAR-10 and CIFAR-100 genuinely differ - which
    is why this is a separate function rather than a relaxation of the other.
    """
    pattern = rf"(?<![\w-]){re.escape(term)}(?:[-/][A-Za-z0-9./]+)?(?![\w])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _mentions(text: str, term: str) -> bool:
    """
    Whole-term containment test.

    Plain substring matching is wrong here: `CIFAR-10` is a substring of
    `CIFAR-100`, so a result on one dataset would be compared against a result
    on the other and reported as a contradiction. The lookarounds reject a match
    that is only part of a longer identifier.
    """
    return re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text, re.IGNORECASE) is not None


def _numeric_disagreement(
    claim_a: Entity,
    claim_b: Entity,
    shared: set[str],
    dataset_terms: set[str],
    model_terms: set[str],
) -> float | None:
    """
    Score a numeric disagreement between two result claims.

    Both claims must mention the same dataset or metric, and both must report a
    value. Returns a confidence in [0, 1] scaled by the size of the gap, or
    None when the claims are not comparable or do not disagree.
    """
    if not shared:
        return None

    text_a = claim_a.sentence_span
    text_b = claim_b.sentence_span

    common = {
        term for term in shared if _mentions(text_a, term) and _mentions(text_b, term)
    }
    if not common:
        return None

    # Both sentences must agree on which dataset they are talking about. A claim
    # naming a dataset the other does not name is measuring something else.
    datasets_a = {t for t in dataset_terms if _mentions(text_a, t)}
    datasets_b = {t for t in dataset_terms if _mentions(text_b, t)}
    if datasets_a and datasets_b and not (datasets_a & datasets_b):
        return None

    # They must also be about the same *system*. Two papers reporting different
    # BLEU on WMT for two different models are not in conflict - they are simply
    # describing different things. Requiring a shared subject is what separates
    # a contradiction from a comparison.
    models_a = {t for t in model_terms if _mentions_model(text_a, t)}
    models_b = {t for t in model_terms if _mentions_model(text_b, t)}
    if models_a and models_b and not (models_a & models_b):
        return None

    # A claim that names no dataset at all is too vague to adjudicate.
    if not datasets_a or not datasets_b:
        return None

    # Requiring *both* sides to name a system was tried and rejected: result
    # sentences routinely say "our model", and the gate silently removed every
    # true finding along with the false ones. Where both do name systems, the
    # mismatch check above still applies.

    # Both sides must assert a measured outcome rather than narrate one.
    for text in (text_a, text_b):
        if not _RESULT_ASSERTION_RE.search(text):
            return None
        if _CROSS_REFERENCE_RE.search(text):
            return None

    # Decide what each sentence actually measures, then compare like with like.
    # This rejects setup descriptions, run-together extraction blobs, deltas,
    # figures quoted from other papers, mismatched metrics (exact-match against
    # F1), mismatched variants (top-1 against top-5) and mismatched regimes
    # (linear-probe against fine-tuned).
    facts_a = analyse_claim(text_a)
    facts_b = analyse_claim(text_b)

    pair = comparable_measurements(facts_a, facts_b)
    if pair is None:
        return None
    measure_a, measure_b = pair

    best_a, best_b = measure_a.value, measure_b.value
    denominator = max(best_a, best_b)
    if denominator == 0:
        return None

    gap = abs(best_a - best_b) / denominator
    if gap < _NUMERIC_DISAGREEMENT_RATIO:
        return None

    # Any gap past the materiality threshold, on a matched dataset and metric,
    # is already a confident disagreement - so the scale starts above the
    # confirmation threshold rather than at the midpoint, and widening gaps
    # push it towards certainty. Whether the finding is actually confirmed is
    # then decided by the Req 7.4 conditions, not by this number alone.
    scaled = min(gap / _NUMERIC_SATURATION_RATIO, 1.0)
    return round(_NUMERIC_BASE_CONFIDENCE + (0.99 - _NUMERIC_BASE_CONFIDENCE) * scaled, 4)


# ---------------------------------------------------------------------------
# NLI inference
# ---------------------------------------------------------------------------


def load_nli_pipeline(model_name: str):
    """
    Load the NLI pipeline, returning None when it is unavailable.

    A missing model is not fatal: the numeric detector still runs, so the stage
    degrades rather than returning nothing.
    """
    cached = _NLI_MODEL_CACHE.get(model_name)
    if cached is not None:
        return cached

    try:
        from transformers import pipeline as hf_pipeline

        nli_pipe = hf_pipeline(
            "text-classification",
            model=model_name,
            top_k=None,
            device=-1,
        )
        _NLI_MODEL_CACHE[model_name] = nli_pipe
        return nli_pipe
    except Exception as exc:
        logger.warning(
            "NLI model '%s' unavailable (%s). "
            "Falling back to numeric claim comparison only.",
            model_name,
            exc,
        )
        return None


def _interpret_nli_result(items) -> tuple[NLILabel, float]:
    """Turn one pipeline result (a list of {label, score} dicts) into a verdict."""
    if isinstance(items, list) and items and isinstance(items[0], list):
        items = items[0]
    if not isinstance(items, list) or not items:
        return NLILabel.NEUTRAL, 0.0

    best = max(items, key=lambda x: x.get("score", 0.0))
    raw_label = str(best.get("label", "")).upper()
    score = float(best.get("score", 0.0))

    if "CONTRADICT" in raw_label:
        return NLILabel.CONTRADICTION, score
    if "ENTAIL" in raw_label:
        return NLILabel.ENTAILMENT, score
    return NLILabel.NEUTRAL, score


def _run_nli(premise: str, hypothesis: str, nli_pipeline) -> tuple[NLILabel, float]:
    """
    Classify the stance of *hypothesis* with respect to *premise*.

    A cross-encoder needs the two sentences as a genuine pair; concatenating
    them into one string makes the model score a single malformed sequence and
    return meaningless labels. Prefer :func:`_run_nli_batch` for more than a
    couple of pairs - calling a transformers pipeline one pair at a time pays
    its per-call overhead on every single claim comparison, which is what made
    contradiction detection with NLI enabled take minutes instead of seconds.
    """
    if nli_pipeline is None:
        return NLILabel.NEUTRAL, 0.0

    try:
        result = nli_pipeline(
            {"text": premise, "text_pair": hypothesis},
            truncation=True,
            max_length=512,
        )
    except Exception as exc:
        logger.warning("NLI inference failed: %s", exc)
        return NLILabel.NEUTRAL, 0.0

    return _interpret_nli_result(result)


def _run_nli_batch(
    pairs: list[tuple[str, str]], nli_pipeline
) -> list[tuple[NLILabel, float]]:
    """
    Classify every (premise, hypothesis) pair in one batched pass.

    A transformers pipeline batches internally when given a list, which is far
    cheaper per pair than a Python-level loop of single calls - the fixed
    per-call cost (tokenization, dispatch) is paid once for the whole list
    instead of once per claim pair, and this stage compares dozens to hundreds
    of pairs on a real corpus.
    """
    if nli_pipeline is None or not pairs:
        return [(NLILabel.NEUTRAL, 0.0)] * len(pairs)

    try:
        results = nli_pipeline(
            [{"text": p, "text_pair": h} for p, h in pairs],
            truncation=True,
            max_length=512,
            batch_size=32,
        )
    except Exception as exc:
        logger.warning("Batched NLI inference failed: %s", exc)
        return [(NLILabel.NEUTRAL, 0.0)] * len(pairs)

    return [_interpret_nli_result(item) for item in results]


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------


def _build_candidate_pairs(
    scores: list[RelationshipScore],
    bridge_entities: dict[str, list[str]],
) -> set[tuple[str, str]]:
    """
    Select document pairs worth comparing.

    A pair qualifies if it shares a bridge entity or scores above the candidate
    threshold. Comparing every pair would be quadratic in corpus size for very
    little extra yield - unrelated papers do not contradict each other.
    """
    pairs: set[tuple[str, str]] = set()

    for doc_ids in bridge_entities.values():
        for a, b in itertools.combinations(sorted(set(doc_ids)), 2):
            pairs.add((a, b))

    for score in scores:
        if score.composite_score >= _CANDIDATE_SCORE_THRESHOLD:
            a, b = sorted([score.doc_id_a, score.doc_id_b])
            pairs.add((a, b))

    return pairs


def detect_contradictions(
    documents: list[Document],
    entities: list[Entity],
    scores: list[RelationshipScore],
    bridge_entities: dict[str, list[str]],
    nli_model_name: str = "cross-encoder/nli-deberta-v3-small",
    nli_confidence_threshold: float = 0.60,
    methodology_similarity_threshold: float = 0.30,
    use_nli: bool = True,
    on_progress: Callable[[ProgressEvent], None] | None = None,
) -> list[Contradiction]:
    """
    Detect contradictions across documents.

    Parameters
    ----------
    use_nli:
        When False, skips loading the NLI model entirely and relies on numeric
        claim comparison. Useful for fast runs and offline environments.

    Returns
    -------
    Both confirmed and unconfirmed contradictions, highest confidence first.
    """

    def emit(event: ProgressEvent) -> None:
        if on_progress:
            on_progress(event)

    start = time.perf_counter()
    nli_pipe = load_nli_pipeline(nli_model_name) if use_nli else None
    detector = "nli+numeric" if nli_pipe is not None else "numeric"

    entity_index: dict[str, list[Entity]] = {}
    for entity in entities:
        entity_index.setdefault(entity.doc_id, []).append(entity)

    title_index = {doc.id: doc.title for doc in documents}

    methodology_index: dict[frozenset[str], float] = {
        frozenset([s.doc_id_a, s.doc_id_b]): s.methodology_similarity for s in scores
    }

    candidate_pairs = _build_candidate_pairs(scores, bridge_entities)

    emit(
        ProgressEvent(
            stage="contradiction_detection",
            status=PipelineStageStatus.RUNNING,
            message=(
                f"Evaluating {len(candidate_pairs)} candidate document pairs "
                f"(detector={detector})"
            ),
            details={"candidate_pairs": len(candidate_pairs), "detector": detector},
        )
    )

    # Pass 1: gather every claim pair worth comparing, and the numeric verdict
    # for each, without touching the NLI model yet.
    pending: list[dict] = []
    for doc_a, doc_b in sorted(candidate_pairs):
        ents_a = entity_index.get(doc_a, [])
        ents_b = entity_index.get(doc_b, [])
        claims_a = _extract_claims(ents_a)
        claims_b = _extract_claims(ents_b)
        if not claims_a or not claims_b:
            continue

        ds_compat = _datasets_compatible(ents_a, ents_b)
        met_compat = _metrics_comparable(ents_a, ents_b)
        shared = _shared_terms(ents_a, ents_b)
        dataset_terms = _dataset_names(ents_a) | _dataset_names(ents_b)
        model_terms = _model_names(ents_a) | _model_names(ents_b)
        meth_sim = methodology_index.get(frozenset([doc_a, doc_b]), 0.0)

        compared = 0
        for claim_a in claims_a:
            if compared >= _MAX_PAIRS_PER_DOC_PAIR:
                break
            for claim_b in claims_b:
                if compared >= _MAX_PAIRS_PER_DOC_PAIR:
                    break
                if claim_a.text.lower().strip() == claim_b.text.lower().strip():
                    continue
                compared += 1

                # Numeric comparison first: it is cheap and more reliable than
                # NLI on sentences dense with figures.
                numeric_conf = _numeric_disagreement(
                    claim_a, claim_b, shared, dataset_terms, model_terms
                )
                pending.append(
                    {
                        "doc_a": doc_a,
                        "doc_b": doc_b,
                        "claim_a": claim_a,
                        "claim_b": claim_b,
                        "ds_compat": ds_compat,
                        "met_compat": met_compat,
                        "shared": shared,
                        "meth_sim": meth_sim,
                        "numeric_conf": numeric_conf,
                    }
                )

    # Pass 2: one batched NLI call for every pending pair, instead of one
    # transformers-pipeline call per pair. This is the change that turns
    # minutes of per-pair overhead into a handful of forward passes.
    if nli_pipe is not None and pending:
        nli_results = _run_nli_batch(
            [(item["claim_a"].sentence_span, item["claim_b"].sentence_span) for item in pending],
            nli_pipe,
        )
    else:
        nli_results = [(NLILabel.NEUTRAL, 0.0)] * len(pending)

    # Pass 3: combine the numeric and NLI verdicts exactly as the single-pass
    # version did, and build the findings.
    contradictions: list[Contradiction] = []
    for item, (nli_label, nli_conf) in zip(pending, nli_results):
        claim_a, claim_b = item["claim_a"], item["claim_b"]
        numeric_conf = item["numeric_conf"]

        label = NLILabel.NEUTRAL
        confidence = 0.0
        source = ""

        if numeric_conf is not None:
            label = NLILabel.CONTRADICTION
            confidence = numeric_conf
            source = "numeric"

        if nli_pipe is not None:
            if nli_label == NLILabel.CONTRADICTION and nli_conf > confidence:
                label = NLILabel.CONTRADICTION
                confidence = nli_conf
                source = "numeric+nli" if numeric_conf is not None else "nli"
            elif nli_label == NLILabel.ENTAILMENT and numeric_conf is None:
                continue

        if label != NLILabel.CONTRADICTION or confidence < 0.4:
            continue

        if (
            confidence >= nli_confidence_threshold
            and (item["ds_compat"] or item["met_compat"])
            and item["meth_sim"] >= methodology_similarity_threshold
        ):
            status = ContradictionStatus.CONFIRMED
        else:
            status = ContradictionStatus.UNCONFIRMED

        shared = item["shared"]
        contradictions.append(
            Contradiction(
                doc_id_a=item["doc_a"],
                doc_id_b=item["doc_b"],
                claim_a=claim_a.text,
                claim_b=claim_b.text,
                nli_label=label,
                nli_confidence=round(confidence, 4),
                dataset_compatible=item["ds_compat"],
                metrics_comparable=item["met_compat"],
                methodology_similarity=round(item["meth_sim"], 4),
                status=status,
                confidence=round(confidence, 4),
                evidence=[
                    EvidenceTrail(
                        source_doc_id=claim_a.doc_id,
                        source_doc_title=title_index.get(claim_a.doc_id, ""),
                        section=claim_a.section,
                        page_number=claim_a.page_number,
                        sentence_span=claim_a.sentence_span,
                    ),
                    EvidenceTrail(
                        source_doc_id=claim_b.doc_id,
                        source_doc_title=title_index.get(claim_b.doc_id, ""),
                        section=claim_b.section,
                        page_number=claim_b.page_number,
                        sentence_span=claim_b.sentence_span,
                    ),
                ],
                explanation=(
                    f"Detected by {source} comparison over shared terms: "
                    f"{', '.join(sorted(shared)) or 'none'}."
                ),
            )
        )

    contradictions.sort(key=lambda c: c.confidence, reverse=True)

    # Keep only the strongest findings for each document pair.
    per_pair: dict[frozenset[str], int] = {}
    kept: list[Contradiction] = []
    for item in contradictions:
        key = frozenset([item.doc_id_a, item.doc_id_b])
        if per_pair.get(key, 0) >= _MAX_FINDINGS_PER_DOC_PAIR:
            continue
        per_pair[key] = per_pair.get(key, 0) + 1
        kept.append(item)
    contradictions = kept

    confirmed = sum(1 for c in contradictions if c.status == ContradictionStatus.CONFIRMED)
    unconfirmed = len(contradictions) - confirmed

    emit(
        ProgressEvent(
            stage="contradiction_detection",
            status=PipelineStageStatus.COMPLETE,
            message=(
                f"Contradiction detection complete: "
                f"{confirmed} confirmed, {unconfirmed} unconfirmed"
            ),
            details={
                "confirmed": confirmed,
                "unconfirmed": unconfirmed,
                "detector": detector,
            },
            elapsed_seconds=round(time.perf_counter() - start, 2),
        )
    )

    return contradictions
