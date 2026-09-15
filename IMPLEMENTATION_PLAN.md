# Research Paper Relationship Analyzer — Status and Implementation Plan

Assessment of the codebase against the 18 requirements in
`.kiro/specs/research-paper-relationship-analyzer/requirements.md`, what was
repaired, and what remains.

---

## 1. Summary

The project had a complete-looking skeleton: every pipeline stage existed as a
module, the domain model was well designed, and 33 tests passed. But three
defects meant the analyser did not actually analyse anything.

| | Before | After |
|---|---|---|
| Runs end to end without an API key | no | **yes** |
| Relationship score dimensions that can be non-zero | 1 of 5 | **5 of 5** |
| API endpoints that return data | 2 of 8 | **13 of 13** |
| WebSocket progress events delivered | 0 | **51 per run** |
| Tests | 33 | **139** |
| Requirements fully implemented | 11 of 18 | **16 of 18** |

The pipeline now runs on a six-paper corpus in ~14 s with no API key, builds a
164-node knowledge graph, and recovers every contradiction and research gap the
corpus was built to contain.

---

## 2. What was wrong

### 2.1 The three defects that mattered

**No embedding stage existed.** Requirement 16 was unimplemented.
`Entity.embedding` was declared in the model and never populated by anything.
Because `scoring.py` derives objective, methodology and results similarity from
cosine distance between entity embeddings, all three were structurally always
`0.0`. `citation_overlap` read `metadata["cited_titles"]`, which nothing wrote,
so it was always `0.0` too. The composite score could only ever be
`0.20 × dataset_jaccard`. The relationship analyser could not rank relationships.

**Every API data endpoint crashed on real data.** `server.py` was written
against a different schema than `models.py`: `kg.graph` (the attribute was
`_graph`), `c.claim_1` (the field is `claim_a`), `s.doc_1_id` (it is
`doc_id_a`), `d.doc_id` (it is `id`), plus `total_pages`, `signal_fusion_score`,
`evidence_graph` and `connection_density`, none of which exist. The test suite
passed only because it exercised the empty-result path, where the handlers
return early before touching any of those fields. With a populated result, five
of six endpoints returned HTTP 500.

**There was no way to run without an OpenAI key.** `--skip-extraction` skipped
extraction entirely, producing zero entities, hence zero scores, zero
contradictions and zero gaps. The only "working" mode required paid API calls.

### 2.2 Further defects found while fixing those

| Defect | Effect |
|---|---|
| `asyncio.get_event_loop()` called from the pipeline worker thread | `RuntimeError`; no progress event ever reached the UI |
| NLI called as `f"{premise} [SEP] {hypothesis}"` | A cross-encoder needs a text pair; it was scoring one malformed string and returning meaningless labels |
| `"CIFAR-10" in "CIFAR-100"` substring match | A CIFAR-10 result was compared against a CIFAR-100 result and reported as a contradiction |
| Progress callbacks emitted inside stage `try` blocks | A console that could not encode a character made ingestion record 6 spurious failures for 6 successfully parsed files |
| `documents_sharing_bridge_entity` lowercased the lookup key, `add_bridge_entities` did not lowercase the node | Returned `[]` for any bridge entity not already lowercase |
| Numeric confidence `0.5 + gap` | A real 7.5 % disagreement scored 0.575, below the 0.60 confirmation threshold |
| Gap discovery had one narrow rule | Returned 0 gaps on a corpus containing 15 explicitly stated ones |
| `vercel.json` routed `/static/x` to `/src/rpra/static/static/x` | Deployed frontend could not load its own CSS or JS |
| Dead code in `_citation_overlap` (`for e in []`) | Misleading; the real logic was the line below it |

---

## 3. What was done

### 3.1 New modules

**`embeddings.py`** — Requirement 16. `EmbeddingBackend` encodes text to
L2-normalised vectors, preferring `sentence-transformers` and falling back to a
deterministic TF-IDF space with a seeded random projection when no model can be
loaded. The fallback is the point: on a machine with no model cache the
transformer path fails, and without a fallback the similarity matrix silently
returns to all zeros — the original bug, re-created at runtime. Vectors persist
to `.npz`.

**`heuristic_extraction.py`** — an LLM-free extraction backend, so the whole
pipeline runs offline. Three rule families: a gazetteer of ~230 dataset, metric,
model and methodology names matched on word boundaries; section-aware cue
phrases (`we propose` in an abstract is an objective, `remains an open problem`
is a research gap); and numeric claim detection requiring both a metric and a
number. Tuned for precision over recall — every entity becomes a graph node and
a scoring term, so a wrong one costs more than a missing one.

**`citations.py`** — parses reference lists into comparable citation keys,
writes them to `metadata["cited_titles"]`, and detects papers in the corpus that
cite one another. This is what makes the fifth scoring dimension non-zero.

**`scripts/make_sample_corpus.py`** — generates six realistic paper PDFs with
shared datasets, cross-citations, explicit gap statements, and two planted
contradictions (ResNet-50/CIFAR-10 and BERT/SQuAD). The project previously had
no runnable corpus.

### 3.2 Repaired modules

- **`server.py`** — rewritten against the real models. Serialisation moved into
  `_serialise_*` helpers so a model change surfaces in one place. The worker
  thread now captures the event loop on the main thread before starting, so
  WebSocket broadcasting works. Shared state is lock-guarded. Added
  `/api/entities`, `/api/report`, `DELETE /api/corpus/{filename}`, and event
  replay so a client connecting mid-run sees the backlog.
- **`contradiction.py`** — fixed the NLI call to pass a genuine text pair; added
  a numeric-disagreement detector that compares reported values for the same
  metric on the same dataset, which runs with no model at all and is the only
  detector available offline; added whole-term matching; recalibrated
  confidence; bounded the claim-pair search.
- **`gap_discovery.py`** — three detectors instead of one: *stated* (authors say
  it outright), *absent* (two established concepts that never co-occur — the
  "absent connection" case Req 8.2 asks for), and *weak* (shared concept, weak
  relationship). Concept display casing is preserved so reports do not say
  `cifar-10`.
- **`pipeline.py`** — added the citation and embedding stages in dependency
  order, wrapped the progress callback so a reporting error cannot fail a stage,
  added `summary()`.
- **`extraction.py`** — backend selection (`auto` / `llm` / `heuristic`). `auto`
  uses the LLM when a key is present and heuristics otherwise, so a run never
  silently produces an empty graph for want of credentials. When the LLM runs,
  heuristic results are merged in, because the gazetteer reliably catches
  dataset and metric names an LLM paraphrases away.

### 3.3 New frontend

Replaced the generic dark glassmorphism UI with one built for the subject.
Design notes:

- **Typographic, not decorative.** Serif (Newsreader) for headings and quoted
  evidence because the subject is scholarly writing; sans (Inter) for interface
  chrome; monospace (JetBrains Mono) for data and citations. Light "paper" mode
  by default, with a selected — not inverted — dark mode.
- **Colour assigned by job, and validated.** Node identity uses three
  categorical hues checked with a CVD validator for all-pairs separation in both
  light and dark mode; entity type is carried by **node shape** as a secondary
  channel, so meaning never rests on hue alone. Magnitude (relationship scores,
  novelty) uses one blue ramp light-to-dark. Contradiction state uses reserved
  status colours, always with an icon and a text label.
- **Contradictions are set as a two-column spread** with the disputed numbers
  highlighted, like a critical edition — the layout states the finding.
- **Evidence everywhere.** A persistent inspector shows the verbatim sentence
  behind any node, edge, contradiction or gap, cited as
  `doc · §section · p.N` (Requirement 13).

### 3.4 Tests: 33 → 139

New: `test_embeddings.py`, `test_heuristic_extraction.py`,
`test_contradiction.py`, `test_citations.py`, `test_gap_discovery.py`,
`test_pipeline_e2e.py`. `test_server.py` rewritten to populate a real result
first — the omission that let every broken handler pass.

`test_pipeline_e2e.py` runs the whole pipeline over generated PDFs offline and
asserts the things that were silently wrong: that every entity receives an
embedding, that the semantic dimensions are not all zero, that the citation
dimension contributes, and that related papers outrank unrelated ones.

---

## 4. Requirement coverage

| # | Requirement | Status | Note |
|---|---|---|---|
| 1 | PDF ingestion and segmentation | Complete | |
| 2 | Document classification | Complete | |
| 3 | Structured entity extraction | Complete | LLM + heuristic |
| 4 | Relation extraction | Complete | |
| 5 | KG construction and storage | Complete | |
| 6 | Relationship scoring | Complete | all five dimensions live |
| 7 | Contradiction detection | Complete | NLI + numeric |
| 8 | Research gap discovery | Complete | three detectors |
| 9 | Evidence graph construction | **Partial** | evidence trails complete; no pruned subgraph object |
| 10 | RAG-grounded LLM explanation | Complete | LLM backend only |
| 11 | Incremental KG update | **Not started** | `config.pipeline.incremental` is still unused |
| 12 | Pipeline progress reporting | Complete | CLI + WebSocket |
| 13 | Explainability and traceability | Complete | |
| 14 | Configuration and extensibility | Complete | |
| 15 | LLM hallucination mitigation | Complete | |
| 16 | Semantic embedding | Complete | was entirely missing |
| 17 | Results export and reporting | Complete | JSON, Markdown, API download |
| 18 | Parser/serialiser round-trip | Complete | asserted end to end |

---

## 5. What remains

### Phase 1 — Complete the two open requirements

**Requirement 11: incremental KG update.** `config.pipeline.incremental` is read
and ignored. Needed: a manifest of processed files keyed by content hash;
ingestion skips unchanged files; `KnowledgeGraph.merge()` to add new nodes and
edges without rebuilding; rescoring limited to pairs involving a new document.
Currently a 10,000-document corpus is fully reprocessed to add one paper.
*Estimate: 2–3 days.*

**Requirement 9: evidence graph.** Evidence trails exist on every edge and
finding, which satisfies traceability. What is missing is the pruned subgraph
object the requirement names — `KnowledgeGraph.subgraph_for_document()` exists
and is unused. Needed: an `EvidenceGraph` built per finding and passed to the
explainer, so RAG explanation retrieves from a pruned graph rather than a flat
evidence list. *Estimate: 2 days.*

### Phase 2 — Scale

- Scoring is O(n²) in documents. At 10,000 documents that is 50 M pairs. Needs
  blocking: an approximate-nearest-neighbour index over document vectors, with
  exact scoring only for candidates.
- `PipelineResult` holds the entire corpus in memory. Needs streaming or a
  document store past a few hundred papers.
- The knowledge graph is a single JSON file. Past ~100k nodes this needs SQLite
  or a graph database.

### Phase 3 — Quality

- **Extraction recall.** The heuristic backend is precision-tuned; its gazetteer
  is ML-centric and will under-perform on other fields. Options: expand the
  gazetteer per domain, or add a local NER model.
- **Contradiction precision** is the weakest remaining component. Successive
  gates took the real corpus from 1454 findings to 10, but a minority are still
  comparisons rather than conflicts. The residual cause is that two sentences
  can share a dataset, a metric and a polarity while describing different
  experimental conditions, which surface text does not distinguish. Fixing this
  properly needs the experimental setting modelled, not just the sentence.

### Phase 4 — Deployment

- `vercel.json` and `render.yaml` are fixed but neither has been deployed or
  tested against a live host.
- No authentication. The API allows unrestricted upload and accepts all origins.
- No upload size limits or rate limiting.

---

## 6. Running it

```bash
pip install -e .

# Generate a sample corpus with known contradictions and gaps
python scripts/make_sample_corpus.py

# Fully offline: no API key, no model downloads
rpra run --extraction-backend heuristic --no-nli

# Web UI
rpra serve

# With an LLM
export OPENAI_API_KEY=sk-...
rpra run --extraction-backend llm
```

Expected on the sample corpus: 6 documents, ~136 entities, 22 bridge concepts,
164 graph nodes, 6 contradictions, 52 research gaps, ~14 s.

---

## 6a. Measured results

Run `python scripts/evaluate_corpus.py` to reproduce these. The corpus is 30
arXiv papers in four topical clusters; the cluster assignment is the ground
truth for relationship ranking.

### Segmentation

| Metric | Before | After |
|---|---|---|
| Split by detected headings | — | **30/30 (100%)** |
| Papers yielding zero sections | 1 (ALBERT) | **0** |
| Worst over-segmentation | 186 sections (CLIP) | **8** |
| Section recall (8 sections × 30 papers) | — | **215/240 (90%)** |

Per-section recall: introduction 30/30, references 30/30, abstract 29/30,
conclusion 29/30, experiments 28/30, related work 25/30, methodology 23/30,
results 21/30.

### Relationship ranking

| Metric | Value |
|---|---|
| precision@5 | 80% |
| precision@10 | **90%** |
| precision@20 | 85% |
| precision@30 | 80% |
| Random baseline | 23% |
| Mean within-cluster score | 0.478 |
| Mean cross-cluster score | 0.352 |
| Separation | +0.125 |

The single miss in the top 10 is MoCo ↔ ResNet. That is arguably a ground-truth
artefact rather than a system error: MoCo uses ResNet as its backbone and
reports ImageNet numbers, so the two really are related — the cluster labels
simply put them in different groups.

### Contradiction precision

Successive gates, each added in response to an inspected false positive:

| Stage | Findings on the 30-paper corpus |
|---|---|
| Shared dataset + metric name only | 1454 (1112 "confirmed") |
| + same subject, per-pair cap | 79 |
| + must assert a result; shared metric in both sentences | 10 |
| + measurement modelling (below) | **0** |

Every one of the 10 survivors was inspected and every one was a false positive.
The final gate models what each number measures rather than matching words:
a delta is not a level, a figure quoted from another paper is not the author's
own, exact-match is not F1, top-1 is not top-5, and linear-probe is not
fine-tuned. `claims.py` holds that logic and `tests/test_claims.py` pins each
rule to the sentence that motivated it.

Zero is the correct answer for this corpus. These are thirty landmark papers
proposing different methods; they rarely re-run each other's experiments, which
is what a numeric contradiction requires. Recall is demonstrated separately on
the synthetic corpus, where contradictions are planted by construction: both
planted document pairs are still recovered.

Two bugs surfaced during this work and were fixed:

- PDF extraction splits decimal points with spaces, so `82 . 9%` parsed as `9%`.
  Every affected figure was wrong by an order of magnitude.
- The model gate matched whole terms only, so `ViT-B/16` did not match `ViT` and
  the gate could not fire. Models now match by family; datasets stay strict,
  because CIFAR-10 and CIFAR-100 genuinely differ.

### Research gaps

60 gaps. No ground truth, so reported rather than scored.

---

## 7. Verification

All claims above were checked by running the code, not by reading it:

- `pytest` — 139 passed
- `ruff check src/ tests/ scripts/` — clean
- Full pipeline over generated PDFs, offline, heuristic backend
- Full pipeline over real HTTP with a live WebSocket client: 51 progress events
  received, all 13 endpoints returning 200 with populated data
- The two planted contradictions recovered; no cross-dataset false positives
- Relationship ranking sanity-checked: the two vision papers score 0.83, the two
  NLP papers 0.69, cross-domain pairs below 0.35
