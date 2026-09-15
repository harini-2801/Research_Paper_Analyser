# Research Paper Relationship Analyzer

**BCSE497J – Project I | Vellore Institute of Technology, Chennai Campus**
**School of Computer Science and Engineering**

| Member | Reg. No. |
|---|---|
| Anjaneya Sahu | 23BCE1448 |
| Harini Sriram | 23BDS1124 |
| Khushi Kumari | 23BAI1324 |

**Guide:** Dr. Poornima S, Faculty, School of Computer Science and Engineering

---

## Project Overview

This project builds an **end-to-end, explainable Research Paper Relationship Analyzer** — a system that automatically ingests a corpus of research papers (PDFs), extracts structured knowledge from them, constructs a dynamic Knowledge Graph, detects contradictory claims across papers, and surfaces unexplored research gaps using LLM-assisted reasoning.

The work is grounded in the literature survey conducted as part of BCSE497J and directly implements the architecture proposed in the **Panel Implementation Strategy** document.

---

## Motivation (from Literature Survey)

The literature survey reviewed **18 papers** across six themes and identified a consistent set of unresolved challenges across all of them:

| Gap from Literature | How This Project Addresses It |
|---|---|
| No end-to-end automation from raw PDFs to insights | Full pipeline: PDF → KG → Contradictions → Gaps → Report |
| Weak IE ↔ KG integration (entities rarely flow into a live graph) | Extracted entities flow directly into a queryable NetworkX KG |
| Contradiction detection is domain-specific (clinical/biomedical only) | Domain-independent NLI + signal-fusion approach |
| Research gaps found only via abstract-level topic modelling | Full-paper semantic analysis with bridge entity reasoning |
| LLM hallucination in generative IE pipelines | Structured schemas, constrained decoding, retry logic, audit logging |
| Dynamic/incremental KG update not supported | Incremental ingestion mode (only new docs reprocessed) |
| Explainability is an open problem | Every finding carries a full Evidence Trail to source page/sentence |

> *"While each theme has produced mature and effective techniques individually, the literature consistently shows that no existing system unifies these capabilities into a single, explainable, end-to-end pipeline."*
> — Literature Survey, Section 6

---

## Base Paper Extension (Panel Implementation Strategy)

The base paper is **Di Iorio et al. (2014), "Analysing and Discovering Semantic Relations in Scholarly Data"**, which established the foundation for representing scholarly knowledge as machine-readable semantic structures.

This project extends that foundation in **8 major ways**, as defined in the Panel Implementation Strategy document:

| Extension | Base Paper Capability | Our Extension |
|---|---|---|
| 1 | Semantic enhancement | Structured research-signal extraction (objectives, methods, datasets, results, gaps) |
| 2 | Semantic relationships | **Weighted Relationship Score** across 5 dimensions |
| 3 | — | **Document Categorisation** (Experimental / Survey / Methodological) |
| 4 | Citation network | **Bridge Entity** discovery for multi-hop cross-paper reasoning |
| 5 | RDF/OWL provenance | **Evidence-backed KG edges** (source, section, page, sentence) |
| 6 | Data inconsistency detection | **NLI + signal fusion** contradiction detection |
| 7 | Semantic search | **RAG + Evidence Graph** grounded LLM explanations |
| 8 | — | **Novelty-scored Research Gap Discovery** from weak KG connections |

The four core signals from the strategy document are all implemented:

- **Metric Signal** — quantitative results (F1-score, accuracy, BLEU)
- **Stance Signal** — NLI-based support / contradiction / neutral classification
- **Bridge Signal** — entities shared across documents enabling multi-hop paths
- **Novelty Signal** — absent/weak KG connections as candidate research gaps

---

## System Architecture

```
Research Papers (PDFs)
        │
        ▼
┌─────────────────────┐
│  PDF Ingestion &    │  PyMuPDF — extracts text, preserves section boundaries,
│  Segmentation       │  page numbers. Segments into: abstract, introduction,
└──────────┬──────────┘  methodology, results, conclusion, references
           │
           ▼
┌─────────────────────┐
│ Document            │  Keyword-signal classifier assigns each paper one of:
│ Classification      │  Experimental | Survey/Review | Methodological
└──────────┬──────────┘  Confidence score attached; low-confidence → manual review flag
           │
           ▼
┌─────────────────────┐
│ Structured          │  LLM (GPT-4o-mini) with constrained JSON schemas extracts:
│ Entity & Relation   │  Entities: objective, methodology, dataset, model,
│ Extraction          │            evaluation_metric, quantitative_result,
└──────────┬──────────┘            limitation, research_gap
           │           Relations: uses, evaluates-on, outperforms, contradicts,
           │                      extends, cites, addresses, identifies-gap-in
           ▼
┌─────────────────────┐
│ Knowledge Graph     │  NetworkX directed multigraph. Every edge stores:
│ Construction        │  - Typed relation
└──────────┬──────────┘  - Full Evidence Trail (doc ID, section, page, sentence)
           │           Bridge Entities identified and connected across documents
           │           Persisted as JSON (round-trip verified)
           ▼
┌─────────────────────┐
│ Relationship        │  Weighted composite score per document pair:
│ Scoring             │  Score = 0.25·Obj + 0.25·Meth + 0.20·DS + 0.20·Res + 0.10·Cite
└──────────┬──────────┘  Objective/Methodology: cosine similarity over embeddings
           │           Dataset/Citation: Jaccard similarity over entity sets
           │           Weights fully configurable via config.yaml
           ▼
┌─────────────────────┐
│ Contradiction       │  Candidate pairs: share a Bridge Entity OR score > 0.4
│ Detection           │  NLI (DeBERTa) classifies stance: entailment/contradiction/neutral
└──────────┬──────────┘  Confirmed only when: NLI=contradiction AND (dataset OR metric
           │           compatible) AND methodology_similarity ≥ 0.3
           │           Unconfirmed contradictions also retained with confidence score
           ▼
┌─────────────────────┐
│ Research Gap        │  Scans for Bridge Entities where connected doc pairs
│ Discovery           │  have composite_score < 0.2 (weak connection threshold)
└──────────┬──────────┘  Validates against existing gap/limitation entities in KG
           │           Ranks by novelty score (inverse connection density)
           ▼
┌─────────────────────┐
│ Evidence Graph &    │  Pruned KG subgraph per finding (only supporting edges)
│ RAG Explanation     │  LLM generates explanation grounded ONLY in Evidence Graph
└──────────┬──────────┘  Inline citations: [DocID, Section, Page]
           │           Low-confidence flag if < 2 supporting edges
           ▼
┌─────────────────────┐
│ Export & Progress   │  JSON report + Markdown report with inline citations
│ Panel               │  JSON log of all pipeline events
└─────────────────────┘  Rich live CLI progress panel
```

---

## Repository Structure

```
ResearchPaperAnalyer/
├── config.yaml                  # Single config file for all pipeline parameters
├── pyproject.toml               # Package definition and dependencies
├── IMPLEMENTATION_PLAN.md       # Status against the 18 requirements, and what remains
│
├── scripts/
│   └── make_sample_corpus.py    # Generates a demo corpus with known contradictions
│
├── src/rpra/
│   ├── models.py                # Core domain models (Entity, Relation, Contradiction…)
│   ├── config.py                # Config loader + Pydantic validation
│   ├── ingestion.py             # PDF parsing and segmentation (PyMuPDF)
│   ├── citations.py             # Reference-list parsing; citation score dimension
│   ├── classification.py        # Document type classifier
│   ├── extraction.py            # Extraction driver + backend selection
│   ├── heuristic_extraction.py  # LLM-free extraction (gazetteer + cue phrases)
│   ├── embeddings.py            # Entity vectors, with a deterministic fallback
│   ├── scoring.py               # Weighted five-dimension relationship scoring
│   ├── knowledge_graph.py       # KG construction, query, serialisation
│   ├── contradiction.py         # NLI + numeric contradiction detection
│   ├── gap_discovery.py         # Stated / absent / weak gap detectors
│   ├── explainer.py             # RAG-grounded LLM explanation generation
│   ├── reporter.py              # JSON + Markdown export
│   ├── progress.py              # Rich progress panel + JSON log
│   ├── pipeline.py              # End-to-end orchestrator
│   ├── server.py                # FastAPI REST + WebSocket backend
│   ├── cli.py                   # CLI entry point (rpra command)
│   └── static/                  # Web UI (HTML, CSS, JS)
│
└── tests/                       # 139 tests
    ├── test_config.py           # Config validation
    ├── test_models.py           # Domain models + KG round-trip (Req 18)
    ├── test_classification.py   # Document classification
    ├── test_scoring.py          # Relationship scoring maths
    ├── test_embeddings.py       # Embedding backend + persistence (Req 16)
    ├── test_heuristic_extraction.py  # Rule-based extraction
    ├── test_citations.py        # Reference parsing + citation overlap
    ├── test_contradiction.py    # Contradiction detection (Req 7)
    ├── test_gap_discovery.py    # Gap detectors (Req 8)
    ├── test_server.py           # API against populated results
    └── test_pipeline_e2e.py     # Full pipeline over generated PDFs
```

---

## Key Design Decisions

### 1. Evidence Trail on Every Edge
Every relation, relationship score, contradiction, and research gap carries an `EvidenceTrail` — a structured record of source document ID, section, page number, and verbatim sentence span. This directly implements the explainability requirement and extends the base paper's provenance model to sentence level.

### 2. NLI + Signal Fusion for Contradictions
The system does **not** label two different numbers as a contradiction simply because they differ. Following the panel strategy document:
```
Contradiction = NLI(contradiction) AND (dataset_compatible OR metric_comparable) AND methodology_similarity ≥ 0.3
```
This prevents false positives where papers evaluate different conditions.

### 3. Configurable Weighted Scoring
The relationship score is a configurable weighted sum:
```
Score = w_obj · S_obj + w_meth · S_meth + w_ds · S_ds + w_res · S_res + w_cite · S_cite
```
Default weights sum to 1.0 and are validated at startup. Custom weights can be provided via `config.yaml`; weights that don't sum to 1.0 are rejected with a descriptive error.

### 4. Bridge Entity Multi-hop Reasoning
Entities shared across two or more documents (datasets, models, algorithms) are elevated to Bridge Entity nodes in the KG. These enable multi-hop reasoning paths up to depth 3, and directly drive both contradiction candidate selection and gap discovery — following the Wang et al. (EMNLP 2022) entity-centered approach.

### 5. LLM Hallucination Mitigation
- Structured JSON output schemas with defined entity/relation type sets
- Non-conforming outputs discarded and retried up to 2 times
- Hallucination audit log records all discarded outputs
- LLM explanations grounded exclusively in the Evidence Graph — no free generation

---

## Installation

```bash
pip install -e ".[dev]"
```

An OpenAI API key is optional. Without one the pipeline uses the heuristic
extraction backend, which runs fully offline:

```bash
set OPENAI_API_KEY=your-key-here    # Windows CMD
# export OPENAI_API_KEY=your-key    # Linux/macOS
```

---

## Usage

### Generate a sample corpus

The repository ships a generator that produces six papers with shared datasets,
cross-citations, explicit gap statements, and two planted contradictions — so
the pipeline has something to find on a first run:

```bash
python scripts/make_sample_corpus.py
```

### Run the pipeline offline (no API key, no model downloads)

```bash
rpra run --extraction-backend heuristic --no-nli
```

On the sample corpus this produces, in about 14 seconds:

```
Documents processed : 6
Extraction backend  : heuristic
Embedding backend   : sentence-transformers
Entities extracted  : 136
Bridge concepts     : 22
KG nodes / edges    : 164 / 223
Contradictions      : 6
Research gaps       : 52
```

### Run with an LLM

```bash
rpra run --extraction-backend llm
```

LLM and heuristic results are merged: the gazetteer reliably catches dataset and
metric names an LLM paraphrases away, while the LLM catches objectives and
limitations no rule covers.

### Launch the web UI

```bash
rpra serve
```

Opens `http://localhost:8000` with the knowledge graph explorer, relationship
matrix, contradiction spreads, ranked research gaps, and a live progress stream
over WebSocket. Every view is clickable through to the verbatim sentence the
finding came from.

### Validate configuration

```bash
rpra validate-config
```

---

## Extraction Backends

| Backend | Requires | Use |
|---|---|---|
| `heuristic` | nothing | Offline runs, demos, CI |
| `llm` | `OPENAI_API_KEY` | Highest recall |
| `auto` (default) | — | LLM when a key is present, heuristic otherwise |

`auto` exists so a run never silently produces an empty knowledge graph because
no credentials were configured.

---

## API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/status` | System state, corpus contents, last run summary |
| `POST` | `/api/upload` | Add a PDF to the corpus |
| `DELETE` | `/api/corpus/{filename}` | Remove a PDF |
| `POST` | `/api/run` | Start a pipeline run |
| `WS` | `/ws/progress` | Live progress events |
| `GET` | `/api/graph` | Knowledge graph, Cytoscape format |
| `GET` | `/api/documents` | Ingested documents and categories |
| `GET` | `/api/contradictions` | Contradictions with evidence trails |
| `GET` | `/api/gaps` | Novelty-ranked research gaps |
| `GET` | `/api/scores` | Pairwise scores across five dimensions |
| `GET` | `/api/entities` | Extracted entities |
| `GET` | `/api/report?fmt=json\|md` | Download the report |
| `POST` | `/api/config/weights` | Update scoring weights |

---

## Deployment Instructions

### 1. Frontend Deployment (Vercel)
The static web UI deploys to Vercel via `vercel.json`:
1. Connect the repository to **Vercel**; `vercel.json` routes `/static/*` to
   `src/rpra/static`.
2. Point the frontend at the backend by appending `?api=https://your-api.onrender.com`
   to the URL, or by setting `window.RPRA_API_BASE` before `app.js` loads.

Note: neither deployment target has been tested against a live host.

### 2. Backend Deployment (Render)
The FastAPI backend server is configured for Render via `render.yaml`:
1. Create a new **Web Service** on **Render** connected to your repository.
2. Select **Python** runtime with Build Command: `pip install -e .`
3. Start Command: `uvicorn rpra.server:app --host 0.0.0.0 --port $PORT`
4. Optionally add `OPENAI_API_KEY`. Without it the service runs the
   heuristic extraction backend.

---



## Test Results

```
139 passed
```

| Test module | Covers |
|---|---|
| `test_config.py` | Config loading, missing keys, invalid weights |
| `test_models.py` | Entity round-trip, KG round-trip (Req 18), bridge queries |
| `test_classification.py` | Category detection, low-confidence flagging |
| `test_scoring.py` | Jaccard, cosine, composite score formula |
| `test_embeddings.py` | Backend selection, determinism, persistence (Req 16) |
| `test_heuristic_extraction.py` | Gazetteer, cue phrases, relation inference |
| `test_citations.py` | Reference splitting, key extraction, citation overlap |
| `test_contradiction.py` | Value parsing, whole-term matching, Req 7.4 conditions |
| `test_gap_discovery.py` | Stated / absent / weak detectors, novelty ranking |
| `test_server.py` | Every endpoint against a populated pipeline result |
| `test_pipeline_e2e.py` | Whole pipeline over generated PDFs, offline |

`test_pipeline_e2e.py` is the one that matters most: it runs every stage over
real PDFs and asserts the properties that were silently broken before — that
every entity receives an embedding, that the semantic scoring dimensions are not
all zero, that the citation dimension contributes, and that related papers
outrank unrelated ones.

---

## Configuration Reference (`config.yaml`)

```yaml
llm:
  provider: openai          # openai | ollama | anthropic
  model: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
  temperature: 0.0
  max_retries: 3

embedding:
  model: sentence-transformers/all-MiniLM-L6-v2
  device: cpu

nli:
  model: cross-encoder/nli-deberta-v3-small
  contradiction_confidence_threshold: 0.60   # Req 7.6
  methodology_similarity_threshold: 0.30      # Req 7.4

relationship_scoring:
  weights:                  # Must sum to 1.0 (Req 6.3 / 6.5)
    objective: 0.25
    methodology: 0.25
    dataset: 0.20
    results_metrics: 0.20
    citation: 0.10

gap_discovery:
  weak_connection_threshold: 0.20   # Req 8.2

storage:
  corpus_input_path: ./data/papers
  output_path: ./output

pipeline:
  extraction_backend: auto  # auto | llm | heuristic
  use_nli: true             # false skips the ~280 MB NLI model download
```

All values are validated at startup against defined ranges. Missing required keys or out-of-range values terminate the pipeline with a descriptive error message (Req 14).

---

## Outputs

After a pipeline run, the `./output/` directory contains:

| File | Description |
|---|---|
| `report.json` | Full structured findings: contradictions, gaps, top-N related pairs, summary statistics |
| `report.md` | Human-readable Markdown report with inline citations |
| `knowledge_graph.json` | Full KG snapshot in JSON (importable into graph tools) |
| `pipeline.log` | Structured JSON log of all pipeline events with timestamps |

---

## Mapping to Literature Survey References

| Component | Key References (from Survey) |
|---|---|
| PDF Ingestion | Sciannameo et al. (2024) — zero-shot extraction from PDFs |
| Entity Extraction | Xu et al. (2024) — Generative IE survey; Zhou et al. (2023) — PromptNER |
| Relation Extraction | Baldini Soares et al. (2020) — Matching the Blanks |
| Cross-document RE | Wang et al. (2022) — Entity-Centered Cross-Document RE (EMNLP) |
| Bridge Entities | Wang et al. (2022); Yao et al. (2010) — collective cross-document extraction |
| KG Construction | Zhong et al. (2022); Ji et al. (2021); Milosevic & Thielemann (2022) |
| Weighted Scoring | Di Iorio et al. (2014) — base paper; Chandrasekaran & Mago (2021) — semantic similarity |
| Contradiction Detection | Fang et al. (2025) — Pruned Evidence Graph; Makhervaks et al. (2023) — NLI |
| Gap Discovery | Abd-alrazaq et al. (2024) — BERTopic; Qi et al. (2020) — network analysis |
| RAG Explanation | KG-Enhanced LLMs (OpenReview) — KG-grounded generative reasoning |

---

## What's Next

See `IMPLEMENTATION_PLAN.md` for the full assessment against all 18
requirements. Outstanding work:

| Phase | Work |
|---|---|
| Requirements | Incremental KG update (Req 11); pruned Evidence Graph object (Req 9) |
| Scale | Blocking for O(n²) scoring; streaming results; graph store past ~100k nodes |
| Quality | Two-column PDF handling; `page_end` refinement; domain gazetteers; a labelled evaluation set |
| Deployment | Live deployment test; authentication; upload limits |

---

*Built as part of BCSE497J – Project I, 2026.*
