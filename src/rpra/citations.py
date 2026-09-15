"""
Reference-list parsing and citation overlap.

The relationship score reserves a `citation` dimension (Requirement 6), but it
can only contribute once something actually populates the reference data.  This
module parses the `references` segment of each document into normalised
citation keys, stores them on ``doc.metadata['cited_titles']``, and detects
`cites` edges between documents in the corpus.

Reference formatting varies wildly between venues, so parsing is done in two
passes: split the block into individual reference entries, then reduce each
entry to a comparable key.  The key is the reference title where one can be
isolated, otherwise the first-author surname plus year - which is still enough
for overlap comparison between two papers' bibliographies.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from rpra.models import (
    Document,
    EvidenceTrail,
    Relation,
    RelationType,
)

logger = logging.getLogger(__name__)

# A numbered reference marker: "[12]" or "12." at the start of an entry.
_NUMBERED_MARKER_RE = re.compile(r"(?:^|\s)(?:\[(\d{1,3})\]|(\d{1,3})\.)\s+(?=[A-Z])")

# "Surname, A." / "Surname A." author patterns at the head of an entry.
_AUTHOR_HEAD_RE = re.compile(r"^([A-Z][a-zA-Z'\-]+),?\s+(?:[A-Z]\.\s*)+")

_YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")

# Venue and publisher noise that should never be treated as a title.
_VENUE_NOISE_RE = re.compile(
    r"\b(proceedings|conference|journal|transactions|arxiv|preprint|vol|volume|"
    r"pp|pages|doi|springer|elsevier|ieee|acm|press|eds?|editors?|in:)\b",
    re.IGNORECASE,
)

_TITLE_MIN_WORDS = 4
_MATCH_THRESHOLD = 0.87


def _normalise_key(text: str) -> str:
    """Lowercase, strip punctuation and collapse whitespace for comparison."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def split_reference_entries(references_text: str) -> list[str]:
    """
    Split a references block into individual entries.

    Numbered bibliographies are split on their markers.  Unnumbered ones fall
    back to splitting on author-initial patterns at line starts, which covers
    most author-year styles.
    """
    text = re.sub(r"-\n\s*", "", references_text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if not text:
        return []

    markers = list(_NUMBERED_MARKER_RE.finditer(text))
    if len(markers) >= 3:
        entries = []
        for i, match in enumerate(markers):
            start = match.end()
            end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
            entry = text[start:end].strip()
            if entry:
                entries.append(entry)
        return entries

    # Unnumbered: split before "Surname, A." where it follows a sentence end.
    parts = re.split(r"(?<=[.\)])\s+(?=[A-Z][a-zA-Z'\-]+,\s+[A-Z]\.)", text)
    return [p.strip() for p in parts if len(p.strip()) > 30]


def extract_citation_key(entry: str) -> str | None:
    """
    Reduce a single reference entry to a comparable key.

    Prefers the reference title.  Titles in most styles sit between the author
    block and the venue, so the entry is split on sentence boundaries and the
    first segment that looks like a title (long enough, not venue noise) wins.
    Falls back to ``surname year``.
    """
    entry = entry.strip()
    if len(entry) < 20:
        return None

    remainder = _AUTHOR_HEAD_RE.sub("", entry).strip()
    # Drop any remaining leading author names before the first title-like run.
    remainder = re.sub(r"^(?:[A-Z][a-zA-Z'\-]+,?\s+(?:[A-Z]\.\s*)+,?\s*(?:and\s+)?)+", "", remainder)
    remainder = re.sub(r"^\(?\d{4}\)?\.?\s*", "", remainder).strip()

    for candidate in re.split(r"(?<=[.?])\s+", remainder):
        candidate = candidate.strip(" .,")
        words = candidate.split()
        if len(words) < _TITLE_MIN_WORDS:
            continue
        if _VENUE_NOISE_RE.search(candidate):
            continue
        if sum(c.isdigit() for c in candidate) > len(candidate) * 0.2:
            continue
        return _normalise_key(candidate)

    author_match = _AUTHOR_HEAD_RE.match(entry)
    year_match = _YEAR_RE.search(entry)
    if author_match and year_match:
        return _normalise_key(f"{author_match.group(1)} {year_match.group(1)}")

    return None


def parse_references(doc: Document) -> list[str]:
    """
    Parse *doc*'s references segment and store the keys on its metadata.

    Returns the list of citation keys, which is also written to
    ``doc.metadata['cited_titles']`` for :mod:`rpra.scoring` to consume.
    """
    blocks = [seg.text for seg in doc.segments if seg.section_type == "references"]
    keys: list[str] = []

    for block in blocks:
        for entry in split_reference_entries(block):
            key = extract_citation_key(entry)
            if key and key not in keys:
                keys.append(key)

    doc.metadata["cited_titles"] = keys
    doc.metadata["reference_count"] = len(keys)
    return keys


def _titles_match(cited_key: str, doc_title: str) -> bool:
    """True when a citation key refers to *doc_title*."""
    target = _normalise_key(doc_title)
    if len(target.split()) < _TITLE_MIN_WORDS or not cited_key:
        return False
    if target in cited_key or cited_key in target:
        return True
    return SequenceMatcher(None, cited_key, target).ratio() >= _MATCH_THRESHOLD


def detect_intra_corpus_citations(documents: list[Document]) -> list[Relation]:
    """
    Find documents in the corpus that cite one another.

    Produces document-level `cites` relations, which are the only genuinely
    cross-document edges available without an external citation database.
    """
    relations: list[Relation] = []

    titled = [d for d in documents if d.title and len(d.title.split()) >= _TITLE_MIN_WORDS]

    for source in documents:
        cited_keys = source.metadata.get("cited_titles") or []
        if not cited_keys:
            continue
        for target in titled:
            if target.id == source.id:
                continue
            for key in cited_keys:
                if not _titles_match(key, target.title):
                    continue
                relations.append(
                    Relation(
                        source_id=source.id,
                        target_id=target.id,
                        relation_type=RelationType.CITES,
                        confidence=0.9,
                        is_cross_document=True,
                        evidence=EvidenceTrail(
                            source_doc_id=source.id,
                            source_doc_title=source.title,
                            section="references",
                            page_number=_references_page(source),
                            sentence_span=key,
                        ),
                    )
                )
                break

    return relations


def _references_page(doc: Document) -> int:
    for seg in doc.segments:
        if seg.section_type == "references":
            return seg.page_start
    return 0


def parse_corpus_references(documents: list[Document]) -> list[Relation]:
    """Parse every document's references and return intra-corpus `cites` edges."""
    for doc in documents:
        try:
            parse_references(doc)
        except Exception as exc:
            logger.warning("Reference parsing failed for %s: %s", doc.id, exc)
            doc.metadata.setdefault("cited_titles", [])

    return detect_intra_corpus_citations(documents)
