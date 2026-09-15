"""
Claim analysis: what a reported number actually measures.

Contradiction detection compares numbers across papers. Deciding whether two
numbers are *comparable* is most of the problem, and it cannot be done from the
number alone. This module turns a sentence into a set of
:class:`Measurement` records, so the detector can compare like with like and
reject pairs that merely look similar.

Five distinctions matter, each learned from a false positive on real papers:

value vs change
    "Swin-T yields +1.2% top-1 accuracy" reports a *delta*; "ViT-B/16 achieves
    79.9% accuracy" reports a *level*. Comparing one against the other is
    meaningless.

own result vs quoted comparison
    "reaches an exact match of 81.3% on SQuAD, against 88.5% reported elsewhere"
    contains two figures, and only the first belongs to this paper. Taking the
    larger one silently compared a paper against itself.

which metric
    A sentence often reports several ("an exact match of 88.5% and an F1 of
    93.7%"). Each value is bound to the metric named nearest it, so exact-match
    is compared against exact-match rather than against F1.

which variant of the metric
    top-1 and top-5 accuracy are different quantities. 85.8% top-5 and 79.9%
    top-1 are not in conflict.

under which regime
    Linear-probe, fine-tuned, zero-shot, from-scratch and supervised numbers are
    not interchangeable. Two papers reporting different values for the same
    model under different regimes agree perfectly.

A sentence carrying many numbers is usually not one sentence at all but several
run together by imperfect PDF extraction, so those are rejected outright.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A number that could be a reported score.
_VALUE_RE = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%"       # 92.4%
    r"|\b(0\.\d{2,4})\b"             # 0.923
    r"|\b(\d{1,3}\.\d{1,2})\b"       # 92.4
)

# PDF extraction routinely puts spaces around a decimal point: "82 . 9%",
# "74 . 3%". Left alone, the parser matches only the fractional part and reads
# 82.9% as 9% - so a correct figure silently becomes a wrong one, and two
# papers agreeing at 82.9 and 82.7 look like a tenfold disagreement.
_SPACED_DECIMAL_RE = re.compile(r"(\d)\s*\.\s*(\d)")


def repair_spaced_decimals(text: str) -> str:
    """Rejoin decimal points that PDF extraction split with spaces."""
    return _SPACED_DECIMAL_RE.sub(r"\1.\2", text)


# Metric vocabulary, longest first so "top-1 accuracy" wins over "accuracy".
_METRIC_TERMS: tuple[tuple[str, str], ...] = (
    (r"top[-\s]?(\d+)\s+accuracy", "top-{}"),
    (r"top[-\s]?(\d+)\s+error", "top-{} error"),
    (r"top[-\s]?(\d+)", "top-{}"),
    (r"exact\s+match|\bem\b", "exact-match"),
    (r"word\s+error\s+rate|\bwer\b", "wer"),
    (r"character\s+error\s+rate|\bcer\b", "cer"),
    (r"error\s+rate|\berror\b", "error"),
    (r"perplexity|\bppl\b", "perplexity"),
    (r"macro[-\s]?f1|micro[-\s]?f1|f1[-\s]?score|\bf1\b", "f1"),
    (r"\baccuracy\b|\bacc\b", "accuracy"),
    (r"\bbleu\b", "bleu"),
    (r"rouge[-\w]*", "rouge"),
    (r"\bmap\b|mean\s+average\s+precision", "map"),
    (r"\bmiou\b|\biou\b", "iou"),
    (r"\bndcg\b", "ndcg"),
    (r"\bmrr\b", "mrr"),
    (r"\bauc\b|\bauroc\b", "auc"),
    (r"\bprecision\b", "precision"),
    (r"\brecall\b", "recall"),
    (r"\bdice\b", "dice"),
    (r"\bloss\b", "loss"),
    (r"\blatency\b", "latency"),
)
_COMPILED_METRICS = [(re.compile(p, re.IGNORECASE), tmpl) for p, tmpl in _METRIC_TERMS]

# Metrics where a lower number is better.
_LOWER_IS_BETTER = frozenset(
    {"error", "perplexity", "loss", "wer", "cer", "latency"}
)

# Text before a number that marks it as a change rather than a level.
# Bare "of" and "by" are deliberately absent: "an accuracy of 92%" is a level,
# and treating "of" as a delta cue removed most genuine claims.
# The window between the verb and the figure has to be generous: "increases its
# ImageNet accuracy by 9.2%" puts 34 characters between them, and a tighter
# window let that delta through as though it were a level.
_DELTA_BEFORE_RE = re.compile(
    r"(?:[+±]|(?<![\w.])-)\s*$"
    r"|\b(?:improv\w*|increas\w*|decreas\w*|gain\w*|drop\w*|reduc\w*|boost\w*|"
    r"lose|loses|losing|lost|outperform\w*|surpass\w*|exceed\w*|"
    r"better|worse|higher|lower)\b[^.]{0,40}?\bby\s+$"
    r"|\b(?:improv\w*|increas\w*|decreas\w*|gain\w*|drop\w*|reduc\w*|boost\w*)\b"
    r"[^.]{0,16}$",
    re.IGNORECASE,
)

# Text after a number that marks it as a change.
_DELTA_AFTER_RE = re.compile(
    r"^\s*(?:points?|pp|%)?\s*"
    r"\b(?:improvement|gain|increase|decrease|reduction|drop|better|worse|"
    r"higher|lower|absolute|relative)\b",
    re.IGNORECASE,
)

# A value introduced as somebody else's number, quoted for comparison.
_REFERENCE_BEFORE_RE = re.compile(
    r"\b(?:against|versus|vs\.?|compared\s+(?:to|with)|relative\s+to|"
    r"over\s+the|than)\s*$",
    re.IGNORECASE,
)
_REFERENCE_AFTER_RE = re.compile(
    r"^\s*(?:\)|,)?\s*"
    r"\b(?:reported\s+(?:elsewhere|previously|in)|previously\s+reported|"
    r"of\s+(?:the\s+)?(?:previous|prior|original)|baseline|in\s+the\s+literature)\b",
    re.IGNORECASE,
)

# A range such as "0.1-0.4 F1" is a spread, not a single measurement.
_RANGE_RE = re.compile(r"\d\s*(?:-|–|to)\s*\d")

_REGIME_PATTERNS: list[tuple[str, str]] = [
    ("zero-shot", r"zero[-\s]?shot"),
    ("few-shot", r"(?:few|one|\d+)[-\s]?shot"),
    ("linear-probe", r"linear\s+(?:evaluation|probe|probing|classifier|protocol|readout)"),
    ("fine-tuned", r"fine[-\s]?tun"),
    ("from-scratch", r"from\s+scratch"),
    ("self-supervised", r"self[-\s]?supervised|unsupervised\s+pre[-\s]?training"),
    ("distillation", r"distillation|distilled|\bteacher\b"),
    ("ensemble", r"\bensemble\b"),
]
_COMPILED_REGIMES = [(name, re.compile(p, re.IGNORECASE)) for name, p in _REGIME_PATTERNS]

# "supervised" only counts when it is not part of "self-supervised".
_SUPERVISED_RE = re.compile(r"(?<!self-)(?<!self )\bsupervised\b", re.IGNORECASE)

# Beyond this, the text is almost certainly several sentences run together by
# PDF extraction rather than one claim.
_MAX_VALUES_PER_CLAIM = 5

# Sentences that describe the setup or the data rather than assert an outcome.
_NON_CLAIM_RE = re.compile(
    r"^\s*(?:implementation|setup|dataset|task)\b\s*[:.]"
    r"|\bthe\s+task\s+is\s+to\b"
    r"|\bwe\s+(?:use|follow|adopt)\s+the\b.{0,40}\b(?:protocol|setting|split)\b",
    re.IGNORECASE,
)

# A bare top-k reference, which carries no direction on its own.
_BARE_TOP_K_RE = re.compile(r"top-\d+")
_ERROR_WORD_RE = re.compile(r"\b(error|err\.)\b", re.IGNORECASE)
_ACCURACY_WORD_RE = re.compile(r"\b(accuracy|acc\.)\b", re.IGNORECASE)

_METRIC_WINDOW = 60


@dataclass(frozen=True)
class Measurement:
    """One reported figure, with what it measures."""

    value: float
    metric: str | None
    polarity: str | None


@dataclass
class ClaimFacts:
    """What a sentence reports, in comparable form."""

    measurements: list[Measurement] = field(default_factory=list)
    variants: set[str] = field(default_factory=set)
    regimes: set[str] = field(default_factory=set)
    is_non_claim: bool = False
    is_blob: bool = False

    def usable(self) -> bool:
        """Whether this claim can take part in a comparison at all."""
        return bool(self.measurements) and not self.is_non_claim and not self.is_blob

    def by_metric(self, metric: str) -> Measurement | None:
        """
        This claim's own figure for *metric*.

        The first match wins: a paper states its own result before quoting
        anyone else's, and quoted figures are excluded during parsing anyway.
        """
        for measurement in self.measurements:
            if measurement.metric == metric:
                return measurement
        return None

    def metrics(self) -> set[str]:
        return {m.metric for m in self.measurements if m.metric}


def _metric_near(sentence: str, start: int, end: int) -> str | None:
    """
    Name the metric this value reports.

    The metric usually precedes the figure ("an exact match of 88.5%"), so text
    before the number is searched first and the closest match wins.
    """
    before = sentence[max(0, start - _METRIC_WINDOW) : start]
    after = sentence[end : end + _METRIC_WINDOW]

    best: tuple[int, str] | None = None
    for pattern, template in _COMPILED_METRICS:
        for match in pattern.finditer(before):
            distance = len(before) - match.end()
            name = template.format(*match.groups()) if match.groups() else template
            if best is None or distance < best[0]:
                best = (distance, name)
    if best is not None:
        return best[1]

    for pattern, template in _COMPILED_METRICS:
        match = pattern.search(after)
        if match:
            name = template.format(*match.groups()) if match.groups() else template
            if best is None or match.start() < best[0]:
                best = (match.start(), name)

    if best is None:
        return None

    # A bare "top-5" says nothing about direction: "top-5 accuracy" and "top-5
    # validation error" both reduce to it, because a qualifier can sit between
    # the two words. Resolve the direction from the wider context.
    name = best[1]
    if _BARE_TOP_K_RE.fullmatch(name):
        context = before + after
        if _ERROR_WORD_RE.search(context) and not _ACCURACY_WORD_RE.search(context):
            return f"{name} error"
    return name


def _polarity_for(metric: str | None) -> str | None:
    if metric is None:
        return None
    root = metric.split()[-1] if " " in metric else metric
    if root in _LOWER_IS_BETTER or metric in _LOWER_IS_BETTER:
        return "lower"
    if metric.endswith("error"):
        return "lower"
    return "higher"


def _is_delta(sentence: str, start: int, end: int) -> bool:
    """Whether the value at *start:end* expresses a change rather than a level."""
    before = sentence[max(0, start - 60) : start]
    after = sentence[end : end + 30]
    if _DELTA_BEFORE_RE.search(before):
        return True
    return bool(_DELTA_AFTER_RE.search(after))


def _is_reference(sentence: str, start: int, end: int) -> bool:
    """Whether the value belongs to another system, quoted for comparison."""
    before = sentence[max(0, start - 40) : start]
    after = sentence[end : end + 40]
    if _REFERENCE_BEFORE_RE.search(before):
        return True
    return bool(_REFERENCE_AFTER_RE.search(after))


def _normalise(percent: str | None, decimal: str | None, bare: str | None) -> float | None:
    if percent is not None:
        value = float(percent) / 100.0
    elif decimal is not None:
        value = float(decimal)
    elif bare is not None:
        value = float(bare)
        if value > 1.0:
            value /= 100.0
    else:
        return None
    return round(value, 4) if 0.0 < value <= 1.0 else None


def analyse_claim(raw_sentence: str) -> ClaimFacts:
    """Extract the comparable facts from a claim sentence."""
    sentence = repair_spaced_decimals(raw_sentence)
    facts = ClaimFacts()

    if _NON_CLAIM_RE.search(sentence):
        facts.is_non_claim = True

    total_values = 0
    for match in _VALUE_RE.finditer(sentence):
        value = _normalise(*match.groups())
        if value is None:
            continue
        total_values += 1

        if _is_delta(sentence, match.start(), match.end()):
            continue
        if _is_reference(sentence, match.start(), match.end()):
            continue
        if _RANGE_RE.search(sentence[max(0, match.start() - 8) : match.end() + 8]):
            continue

        metric = _metric_near(sentence, match.start(), match.end())
        facts.measurements.append(
            Measurement(value=value, metric=metric, polarity=_polarity_for(metric))
        )

    if total_values > _MAX_VALUES_PER_CLAIM:
        facts.is_blob = True

    for match in re.finditer(r"\btop[-\s]?(\d+)\b", sentence, re.IGNORECASE):
        facts.variants.add(f"top-{match.group(1)}")

    for name, pattern in _COMPILED_REGIMES:
        if pattern.search(sentence):
            facts.regimes.add(name)
    if _SUPERVISED_RE.search(sentence) and "self-supervised" not in facts.regimes:
        facts.regimes.add("supervised")

    return facts


def conditions_conflict(a: ClaimFacts, b: ClaimFacts) -> bool:
    """
    Whether two claims describe incompatible experimental conditions.

    A conflict means the two numbers are not measuring the same thing, so any
    difference between them is expected rather than contradictory.
    """
    # top-1 against top-5 is a different quantity. Treated strictly: if either
    # side names a variant, both must name the same one, because an unqualified
    # "accuracy" cannot safely be assumed to match.
    if (a.variants or b.variants) and a.variants != b.variants:
        return True

    # Regimes are compared only when both sides state one; a claim that names no
    # regime is not evidence of a different regime.
    return bool(a.regimes and b.regimes and not (a.regimes & b.regimes))


def comparable_measurements(
    a: ClaimFacts, b: ClaimFacts
) -> tuple[Measurement, Measurement] | None:
    """
    Find a figure in each claim that measures the same thing.

    Returns None when the two claims share no metric, which means there is
    nothing to disagree about.
    """
    if not a.usable() or not b.usable():
        return None
    if conditions_conflict(a, b):
        return None

    shared = a.metrics() & b.metrics()
    if not shared:
        return None

    # Prefer the metric whose figures differ most, since that is the candidate
    # disagreement; ties are resolved by name for determinism.
    best: tuple[float, Measurement, Measurement] | None = None
    for metric in sorted(shared):
        left = a.by_metric(metric)
        right = b.by_metric(metric)
        if left is None or right is None:
            continue
        if left.polarity != right.polarity:
            continue
        spread = abs(left.value - right.value)
        if best is None or spread > best[0]:
            best = (spread, left, right)

    return (best[1], best[2]) if best else None
