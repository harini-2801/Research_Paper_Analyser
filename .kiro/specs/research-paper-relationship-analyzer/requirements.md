# Requirements Document

## Introduction

The Research Paper Relationship Analyzer is an end-to-end system that ingests a corpus of research papers in PDF format, extracts structured entities and relationships using LLM-assisted information extraction, constructs and evolves a dynamic Knowledge Graph (KG), identifies contradictory claims across papers, and surfaces unexplored research gaps. The system produces explainable, evidence-grounded outputs suitable for literature review, research planning, and gap discovery.

The pipeline follows the sequence: PDF ingestion → document classification → structured extraction → knowledge graph construction → similarity, contradiction, and gap analysis → weighted evidence fusion → RAG-grounded LLM explanation.

---

## Glossary

- **Corpus**: The full collection of research papers submitted for analysis.
- **Document**: A single research paper, represented as a PDF file.
- **Segment**: A logically coherent section of a document (e.g., abstract, introduction, methodology, results, conclusion).
- **Entity**: A named, typed concept extracted from a document (method, dataset, model, metric, result, objective, limitation, research gap).
- **Relation**: A typed, directed edge between two entities or between two documents, carrying evidence metadata.
- **Knowledge Graph (KG)**: A directed graph where nodes are entities or documents and edges are typed relations with associated evidence.
- **Bridge Entity**: An intermediate entity (dataset, model, algorithm, research problem) shared by two or more documents enabling multi-hop connections.
- **Evidence Trail**: The provenance record attached to each KG edge, containing source document ID, section, page, and sentence reference.
- **Relationship Score**: The weighted composite score quantifying the relatedness of two documents across five signal dimensions.
- **Metric Signal**: Signal derived from quantitative evaluation results (e.g., F1-score, accuracy, BLEU).
- **Stance Signal**: Signal derived from NLI-based stance classification (support, contradiction, neutral) between claims.
- **Bridge Signal**: Signal derived from shared bridge entities enabling multi-hop reasoning between documents.
- **Novelty Signal**: Signal derived from absent or weak KG connections treated as candidate research gaps.
- **NLI**: Natural Language Inference — classifying the logical relationship between two text spans as entailment, contradiction, or neutral.
- **RAG**: Retrieval-Augmented Generation — an LLM reasoning pattern that retrieves relevant evidence before generating an answer.
- **Evidence Graph**: A pruned subgraph of the KG containing only the edges most relevant to a specific query or claim.
- **Document Category**: One of three document types: Experimental, Survey/Review, or Methodological.
- **Incremental Update**: Adding new documents to the KG without reprocessing the entire corpus.
- **Pipeline**: The ordered sequence of processing stages from PDF ingestion to final output.
- **Pipeline Run**: A single execution of the full pipeline on a given corpus or corpus delta.
- **LLM**: Large Language Model used for entity extraction, relation extraction, classification, and explanation generation.
- **Extractor**: The pipeline component responsible for structured information extraction from segments.
- **Classifier**: The pipeline component responsible for document categorisation.
- **Contradiction Detector**: The pipeline component that identifies contradictory claims using NLI and signal analysis.
- **Gap Discoverer**: The pipeline component that identifies candidate research gaps from weak or absent KG connections.
- **Progress Panel**: The user-facing interface displaying real-time status of pipeline stages and subtasks.

---

## Requirements

---

### Requirement 1: PDF Ingestion and Segmentation

**User Story:** As a researcher, I want to upload a collection of PDF research papers so that the system can process them as structured input.

#### Acceptance Criteria

1. THE Pipeline SHALL accept a directory path or a list of PDF file paths as corpus input.
2. WHEN a PDF file is provided, THE Pipeline SHALL extract full text, preserving section boundaries, page numbers, and paragraph structure.
3. THE Pipeline SHALL segment each document into logical sections: abstract, introduction, related work, methodology, experiments/results, conclusion, and references.
4. IF a PDF file is malformed, password-protected, or cannot be parsed, THEN THE Pipeline SHALL log a structured error containing the file path and reason, skip that file, and continue processing the remaining corpus.
5. WHEN segmentation is complete for a document, THE Pipeline SHALL emit a progress event to the Progress Panel indicating the document name and completion status.
6. THE Pipeline SHALL support corpora of up to 10,000 PDF documents in a single run.
7. IF a submitted file is not in PDF format, THEN THE Pipeline SHALL reject that file, record the rejection with a reason, and exclude it from processing.

---

### Requirement 2: Document Classification

**User Story:** As a researcher, I want each paper to be categorised by its document type so that relationship analysis can apply type-appropriate weights and heuristics.

#### Acceptance Criteria

1. WHEN segmentation of a document is complete, THE Classifier SHALL assign the document one of three categories: Experimental, Survey/Review, or Methodological.
2. THE Classifier SHALL base classification on features extracted from the abstract, methodology, and results sections.
3. THE Classifier SHALL attach the assigned category and a confidence score in the range [0.0, 1.0] to the document metadata.
4. IF the Classifier confidence score is below 0.5, THEN THE Classifier SHALL assign the category "Experimental" as the default and flag the document for manual review.
5. WHEN classification of a document is complete, THE Pipeline SHALL emit a progress event to the Progress Panel indicating the document name, assigned category, and confidence score.

---

### Requirement 3: Structured Entity Extraction

**User Story:** As a researcher, I want the system to extract key entities from each paper so that the knowledge graph has rich, typed nodes.

#### Acceptance Criteria

1. WHEN a document segment is available, THE Extractor SHALL extract entities of the following types: objective, methodology, dataset, model, evaluation metric, quantitative result, limitation, and research gap.
2. THE Extractor SHALL associate each extracted entity with its source document ID, section name, page number, and sentence span.
3. THE Extractor SHALL use an LLM with structured prompting to perform named entity recognition, constraining output to the defined entity type schema.
4. IF the LLM returns an entity that does not conform to the defined type schema, THEN THE Extractor SHALL discard that entity and log a structured warning containing the document ID, entity text, and returned type.
5. THE Extractor SHALL deduplicate entities within a document using string normalisation and semantic similarity, retaining the entity instance with the most complete provenance.
6. WHEN extraction for a document is complete, THE Pipeline SHALL emit a progress event to the Progress Panel indicating the document name and the count of entities extracted by type.
7. THE Extractor SHALL process each document segment independently so that extraction failures in one segment do not prevent extraction from other segments of the same document.

---

### Requirement 4: Relation Extraction

**User Story:** As a researcher, I want the system to identify typed relationships between extracted entities so that the knowledge graph captures meaningful scholarly connections.

#### Acceptance Criteria

1. WHEN entities have been extracted from a document, THE Extractor SHALL identify typed relations between entity pairs within the same document.
2. THE Extractor SHALL support the following relation types: uses, evaluates-on, outperforms, contradicts, extends, cites, addresses, and identifies-gap-in.
3. WHEN cross-document relations are identified, THE Extractor SHALL record an Evidence Trail for each relation containing source document ID, target document ID, section, page, and sentence reference for both endpoints.
4. THE Extractor SHALL identify Bridge Entities — entities shared across two or more documents — and record all document references for each Bridge Entity.
5. IF the LLM returns a relation type not in the defined schema, THEN THE Extractor SHALL discard that relation and log a structured warning.
6. THE Extractor SHALL support multi-hop relation paths of depth up to 3 through Bridge Entities.

---

### Requirement 5: Knowledge Graph Construction and Storage

**User Story:** As a researcher, I want the extracted entities and relations stored as a queryable knowledge graph so that I can explore connections across the literature.

#### Acceptance Criteria

1. WHEN entity and relation extraction is complete for the corpus, THE Pipeline SHALL construct a directed Knowledge Graph where nodes represent entities and documents, and edges represent typed relations.
2. THE Knowledge Graph SHALL store every edge with its associated Evidence Trail.
3. THE Knowledge Graph SHALL be persisted to durable storage in a format that supports graph traversal queries.
4. WHEN the Knowledge Graph is updated with new data, THE Pipeline SHALL preserve all previously existing nodes and edges unless explicitly instructed to rebuild.
5. THE Knowledge Graph SHALL support incremental updates: WHEN new documents are added to the corpus, THE Pipeline SHALL extract and integrate them without reprocessing already-indexed documents.
6. THE Knowledge Graph SHALL expose a query interface that accepts entity names, document IDs, or relation types and returns matching subgraphs.
7. WHEN a Knowledge Graph query is executed, THE Pipeline SHALL return results within 5 seconds for subgraphs of up to 500 nodes.

---

### Requirement 6: Relationship Scoring

**User Story:** As a researcher, I want pairs of papers to be scored for relatedness across multiple dimensions so that the most relevant connections are surfaced first.

#### Acceptance Criteria

1. THE Pipeline SHALL compute a Relationship Score for every pair of documents in the corpus.
2. THE Relationship Score SHALL be computed as a weighted sum of five component scores: objective similarity, methodology similarity, dataset overlap, results/metrics similarity, and citation overlap.
3. THE Pipeline SHALL apply default component weights that sum to 1.0: objective (0.25), methodology (0.25), dataset (0.20), results/metrics (0.20), citation (0.10).
4. WHERE a user provides custom component weights, THE Pipeline SHALL use those weights provided that the supplied weights sum to 1.0.
5. IF the supplied custom weights do not sum to 1.0, THEN THE Pipeline SHALL reject the configuration, return a descriptive error message, and apply the default weights.
6. WHEN computing objective and methodology similarity, THE Pipeline SHALL use semantic embedding cosine similarity with a minimum similarity threshold of 0.0 and maximum of 1.0.
7. WHEN computing dataset overlap and citation overlap, THE Pipeline SHALL use Jaccard similarity over the respective entity sets.
8. THE Pipeline SHALL store each Relationship Score alongside its five component scores and the weights used in the Knowledge Graph edge connecting the two documents.

---

### Requirement 7: Contradiction Detection

**User Story:** As a researcher, I want the system to identify contradictory claims across papers so that I can understand where the literature disagrees.

#### Acceptance Criteria

1. THE Contradiction Detector SHALL identify candidate contradictions between claim pairs drawn from documents that share at least one Bridge Entity or have a Relationship Score above 0.4.
2. WHEN evaluating a candidate claim pair, THE Contradiction Detector SHALL apply NLI stance classification to determine whether the relationship is entailment, contradiction, or neutral.
3. WHEN NLI stance classification returns contradiction for a claim pair, THE Contradiction Detector SHALL additionally verify dataset compatibility, metric compatibility, and methodology similarity before confirming the contradiction.
4. THE Contradiction Detector SHALL confirm a contradiction only when NLI stance is "contradiction" AND (datasets are compatible OR metrics are directly comparable) AND methodology similarity score is above 0.3.
5. THE Contradiction Detector SHALL attach a confidence score in the range [0.0, 1.0] and the full Evidence Trail to each confirmed contradiction.
6. IF NLI confidence is below 0.6 for a contradiction candidate, THEN THE Contradiction Detector SHALL mark the contradiction as "unconfirmed" rather than discarding it, and include it in output with its confidence score.
7. WHEN contradiction detection is complete, THE Pipeline SHALL emit a progress event to the Progress Panel with the count of confirmed and unconfirmed contradictions found.

---

### Requirement 8: Research Gap Discovery

**User Story:** As a researcher, I want the system to identify unexplored research areas so that I can direct future work to meaningful open problems.

#### Acceptance Criteria

1. THE Gap Discoverer SHALL identify candidate research gaps by analysing weak or absent connections in the Knowledge Graph between entity clusters that are otherwise densely connected.
2. THE Gap Discoverer SHALL treat a connection as weak WHEN the Relationship Score between two documents sharing a Bridge Entity is below 0.2.
3. THE Gap Discoverer SHALL validate each candidate gap by checking whether the gap is already addressed by an existing entity of type "research gap" or "limitation" in the Knowledge Graph.
4. WHEN a candidate gap is not addressed by existing entities, THE Gap Discoverer SHALL promote it to a confirmed research gap and record supporting evidence.
5. THE Gap Discoverer SHALL rank confirmed research gaps by a novelty score derived from the density of surrounding KG connections and the recency of the most recent citing paper.
6. THE Gap Discoverer SHALL output a ranked list of research gaps, each with a plain-language description, supporting evidence references, and novelty score.
7. WHEN gap discovery is complete, THE Pipeline SHALL emit a progress event to the Progress Panel with the count of confirmed research gaps identified.

---

### Requirement 9: Evidence Graph Construction

**User Story:** As a researcher, I want every analysis result to be backed by a traceable evidence graph so that I can verify the system's conclusions.

#### Acceptance Criteria

1. THE Pipeline SHALL construct an Evidence Graph for each confirmed contradiction and each confirmed research gap.
2. WHEN constructing an Evidence Graph, THE Pipeline SHALL include only the KG edges and nodes directly supporting the specific finding, pruning unrelated content.
3. THE Evidence Graph SHALL retain the full Evidence Trail for each included edge, identifying source document, section, page number, and sentence span.
4. THE Evidence Graph SHALL be queryable by finding ID (contradiction ID or gap ID) and SHALL return the associated subgraph within 3 seconds.
5. THE Pipeline SHALL associate each Evidence Graph with its parent finding so that the LLM explanation step has direct access to supporting evidence.

---

### Requirement 10: RAG-Grounded LLM Explanation

**User Story:** As a researcher, I want the system to generate plain-language explanations of findings that are grounded in retrieved evidence so that I can trust and act on the outputs.

#### Acceptance Criteria

1. WHEN generating an explanation for a finding, THE Pipeline SHALL retrieve the associated Evidence Graph and pass it as context to the LLM.
2. THE Pipeline SHALL instruct the LLM to generate explanations that reference specific source documents, sections, and claims from the Evidence Graph.
3. THE Pipeline SHALL constrain the LLM to base all factual claims in the explanation exclusively on content present in the provided Evidence Graph.
4. THE Pipeline SHALL include provenance citations (document ID, section, page) inline within each generated explanation.
5. IF the Evidence Graph for a finding contains fewer than 2 supporting edges, THEN THE Pipeline SHALL flag the explanation as "low-confidence" and include the flag in the output.
6. THE Pipeline SHALL not expose free-generation LLM outputs that are unsupported by the Evidence Graph to end users.

---

### Requirement 11: Incremental Knowledge Graph Update

**User Story:** As a researcher, I want to add new papers to an existing corpus without reprocessing all previously analysed papers so that the system scales efficiently over time.

#### Acceptance Criteria

1. WHEN new documents are submitted to an existing corpus, THE Pipeline SHALL process only the new documents through all pipeline stages.
2. WHEN integrating new documents, THE Pipeline SHALL identify Bridge Entities shared between new and existing documents and update the Knowledge Graph edges accordingly.
3. WHEN a new document introduces a contradiction or research gap finding, THE Pipeline SHALL update the relevant Evidence Graphs and re-rank affected findings.
4. THE Pipeline SHALL complete incremental ingestion of up to 100 new documents within 30 minutes on a corpus of 1,000 existing documents.
5. THE Pipeline SHALL preserve all prior findings and scores unless the new evidence explicitly invalidates them, in which case THE Pipeline SHALL update the affected findings and retain a version history of the change.

---

### Requirement 12: Pipeline Progress Reporting

**User Story:** As a researcher, I want real-time visibility into each stage of the pipeline so that I can monitor progress and identify failures quickly.

#### Acceptance Criteria

1. THE Pipeline SHALL expose a Progress Panel interface that displays the status of each pipeline stage: Pending, Running, Complete, or Failed.
2. WHEN a pipeline stage transitions to Running, Complete, or Failed, THE Pipeline SHALL emit a timestamped progress event to the Progress Panel within 1 second of the transition.
3. THE Progress Panel SHALL display, for each document being processed: document name, current stage, elapsed time, and any error messages.
4. WHEN a pipeline stage fails, THE Pipeline SHALL display the error message and the affected document or component in the Progress Panel without stopping other in-progress stages.
5. THE Progress Panel SHALL display an overall completion percentage calculated as the ratio of completed pipeline stage-document pairs to the total expected stage-document pairs.
6. THE Pipeline SHALL log all progress events and errors to a persistent structured log file in JSON format.

---

### Requirement 13: Explainability and Evidence Traceability

**User Story:** As a researcher, I want every system output to be fully traceable to source material so that I can independently verify conclusions.

#### Acceptance Criteria

1. THE Pipeline SHALL attach an Evidence Trail to every Relation, Relationship Score, confirmed contradiction, and confirmed research gap produced by the system.
2. THE Evidence Trail SHALL contain at minimum: source document ID, document title, section name, page number, and verbatim sentence span for each supporting claim.
3. THE Pipeline SHALL make Evidence Trails accessible via the query interface using finding ID or entity ID as lookup keys.
4. WHEN an Evidence Trail is retrieved, THE Pipeline SHALL return results within 2 seconds.
5. THE Pipeline SHALL not produce any externally visible finding that lacks an associated Evidence Trail.

---

### Requirement 14: Configuration and Extensibility

**User Story:** As a system operator, I want to configure pipeline behaviour through a structured configuration file so that the system can be tuned for different research domains without code changes.

#### Acceptance Criteria

1. THE Pipeline SHALL read configuration from a single structured configuration file at startup.
2. THE configuration file SHALL support specification of: LLM provider and model name, relationship score component weights, NLI model name, contradiction confidence threshold, gap discovery novelty threshold, corpus input path, and output storage path.
3. IF a required configuration key is absent, THEN THE Pipeline SHALL log a descriptive error identifying the missing key and terminate without processing.
4. IF a configuration value is out of the valid range for its key, THEN THE Pipeline SHALL log a descriptive error identifying the key, the invalid value, and the valid range, then terminate without processing.
5. THE Pipeline SHALL validate the full configuration file before beginning any processing step.
6. WHERE a configuration key has a defined default value, THE Pipeline SHALL apply that default when the key is absent from the configuration file.

---

### Requirement 15: LLM Hallucination Mitigation

**User Story:** As a researcher, I want the system to minimise unsupported LLM outputs so that I can rely on the system's findings for scholarly work.

#### Acceptance Criteria

1. THE Pipeline SHALL use structured output schemas with constrained decoding when invoking the LLM for entity extraction and relation extraction.
2. WHEN the LLM returns an entity or relation that does not conform to the defined schema, THE Extractor SHALL discard the output and retry the request up to 2 additional times before logging a failure.
3. THE Pipeline SHALL not include LLM-generated text in any output unless the text is grounded in and explicitly references the provided Evidence Graph context.
4. THE Pipeline SHALL maintain a hallucination audit log recording all discarded LLM outputs, including document ID, prompt type, and the non-conforming response.
5. WHEN the hallucination audit log records more than 10% discarded outputs for a single document, THE Pipeline SHALL flag that document for manual review and include the flag in the Progress Panel.

---

### Requirement 16: Semantic Embedding and Vector Representation

**User Story:** As a researcher, I want the system to generate dense semantic embeddings for documents and entities so that similarity-based analysis is grounded in meaning rather than surface text.

#### Acceptance Criteria

1. THE Pipeline SHALL generate a semantic embedding vector for each extracted entity and for each document using a pre-configured embedding model.
2. THE Pipeline SHALL store entity and document embeddings alongside their source records in durable storage.
3. WHEN computing objective similarity and methodology similarity for Relationship Scoring, THE Pipeline SHALL use cosine similarity over the corresponding embedding vectors.
4. THE Pipeline SHALL support swapping the embedding model by changing a single configuration key without modifying pipeline code.
5. IF embedding generation fails for an entity or document, THEN THE Pipeline SHALL log a structured error containing the entity or document ID and reason, assign a zero vector as a fallback, and continue processing.
6. THE Pipeline SHALL reuse previously computed embeddings for existing documents during incremental updates, recomputing only for newly added documents.

---

### Requirement 17: Results Export and Reporting

**User Story:** As a researcher, I want the system to export its findings in structured, human-readable formats so that I can use the results in reports, presentations, and downstream tools.

#### Acceptance Criteria

1. THE Pipeline SHALL export a final report containing: the ranked list of confirmed contradictions, the ranked list of confirmed research gaps, the top-N document pairs by Relationship Score, and summary statistics for the corpus.
2. THE Pipeline SHALL export findings in both JSON format and a human-readable Markdown format.
3. WHEN generating the Markdown report, THE Pipeline SHALL include inline citations linking each finding to its source documents by document ID and title.
4. THE Pipeline SHALL export the full Knowledge Graph snapshot in a standard graph serialisation format (e.g., GraphML or JSON-LD) suitable for import into external graph tools.
5. IF an export operation fails due to a storage or formatting error, THEN THE Pipeline SHALL log a structured error and retain all findings in the Knowledge Graph so that export can be re-attempted without reprocessing.
6. WHEN export is complete, THE Pipeline SHALL emit a progress event to the Progress Panel with the output file paths and counts of exported findings.

---

### Requirement 18: Parser and Serialiser Round-Trip Integrity

**User Story:** As a system operator, I want all structured data produced by the pipeline to survive serialisation and deserialisation without loss so that stored artefacts are reliable.

#### Acceptance Criteria

1. THE Pipeline SHALL serialise all Knowledge Graph snapshots, Evidence Graphs, entity records, and relation records to a defined structured format (JSON or equivalent).
2. THE Pipeline SHALL deserialise stored artefacts back into in-memory representations using the same schema.
3. FOR ALL valid Knowledge Graph snapshots, serialising then deserialising SHALL produce a graph that is structurally and semantically equivalent to the original (round-trip property).
4. FOR ALL valid entity and relation records, serialising then deserialising SHALL produce records equal to the originals in all fields (round-trip property).
5. IF deserialisation of a stored artefact fails schema validation, THEN THE Pipeline SHALL log a structured error identifying the artefact path and the validation failure, and SHALL NOT load the corrupted artefact into the active graph.
