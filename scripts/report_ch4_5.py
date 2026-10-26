"""Chapters 4-5 of the project report: system design and implementation."""

from __future__ import annotations

BLOCKS: list = []
add = BLOCKS.append

# ======================================================================
# CHAPTER 4 - DESIGN
# ======================================================================
add(("h1", "System Design"))

add(("h2", "Design Principles"))
add(("p",
     "We settled four rules early and checked every later decision against them."))
add(("num", [
    "Show the source. A number, a contradiction or a gap is never shown without the sentence, "
    "section and page it came from. If a stage cannot attach evidence, it does not produce the "
    "finding.",
    "Get worse in plain sight. When something cannot be done well, the system does a poorer job "
    "and says so. A paper that cannot be segmented is cut into page chunks and marked as "
    "unstructured. An unavailable embedding model is replaced by a simple one, and the result "
    "records which was used.",
    "Prefer precision to recall. Every extracted entity becomes a node in the graph and a term "
    "in a score, so a wrong entity does more harm than a missing one. Rules fire only on strong "
    "evidence in the text.",
    "Keep the parts separate. Each stage reads and writes plain data models, so it can be "
    "tested alone, replaced or switched off.",
]))

add(("h2", "System Architecture"))
add(("p",
     "The system has four layers ({fig:arch}). The analysis pipeline is a library that knows "
     "nothing about the web: give it a configuration and a directory and it returns a result "
     "object. A thin service layer wraps it for network use. That layer adds the endpoints, the "
     "progress stream, and the locking needed because a run happens on a worker thread while "
     "requests keep arriving. The presentation layer is a static page that talks to the service, "
     "plus a status page that the service serves itself. Storage is the local file system."))
add(("fig", {"key": "arch", "file": "arch_layers.png", "width_cm": 12.8,
             "caption": "Layered architecture. Each layer depends only on the one beneath it."}))
add(("p",
     "This split is what made the deployment in {sec:deployment} possible. The interface needs "
     "nothing from the server except HTTP, so it can sit on a static host while the server runs "
     "somewhere else, and it can run alone against a saved analysis when no server answers."))

add(("h2", "Pipeline Design"))
add(("p",
     "The pipeline has eleven stages ({fig:pipeline}), and their order is forced by what each "
     "one needs from the one before ({tab:stages}). The dependency that bit us was embedding "
     "before scoring. Three of the five score dimensions are cosine similarities between entity "
     "vectors. If scoring runs first it does not crash; it just returns zero for those "
     "dimensions, and the total still looks like a sensible number. The pipeline now checks the "
     "order instead of trusting it."))
add(("fig", {"key": "pipeline", "file": "fig1_pipeline.png", "width_cm": 12.4,
             "caption": "The eleven pipeline stages in execution order."}))
add(("tab", {
    "key": "stages",
    "caption": "Pipeline stages and their dependencies. What each consumes, what it produces, and what it must follow.",
    "size": 10,
    "headers": ["Stage", "Consumes", "Produces", "Must follow"],
    "widths": [1.3, 1.9, 2.3, 2.2],
    "rows": [
        ["1 Ingestion", "PDF files", "Documents with segments", "–"],
        ["2 Citations", "Reference segments", "Citation keys; paper-to-paper citations", "Ingestion"],
        ["3 Classification", "Segments", "Category and confidence", "Ingestion"],
        ["4 Extraction", "Segments", "Entities and relations", "Ingestion"],
        ["5 Embedding", "Entities", "Entity vectors", "Extraction"],
        ["6 Scoring", "Entities, vectors, citations", "Pairwise scores", "Embedding, citations"],
        ["7 Graph", "All of the above", "Knowledge graph, bridge concepts", "Scoring"],
        ["8 Contradictions", "Entities, scores, graph", "Findings with evidence", "Scoring (methodology similarity)"],
        ["9 Gaps", "Graph, scores", "Ranked gaps", "Graph, scores"],
        ["10 Explanation", "Findings, evidence", "Plain-language text (optional)", "Findings"],
        ["11 Export", "Everything", "JSON, Markdown and PDF reports", "All"],
    ],
}))

add(("h2", "Data Model"))
add(("p",
     "All stages share the Pydantic models in {fig:model}. A Document owns its Segments. An "
     "Entity belongs to a document and records the section, page and sentence it came from. A "
     "Relation links entities or documents. Every Contradiction and ResearchGap carries a list "
     "of EvidenceTrail records. Scores are limited to the range 0 to 1 by the model itself, so "
     "an out-of-range value is rejected the moment it is created and cannot travel further."))
add(("fig", {"key": "model", "file": "data_model.png", "width_cm": 12.8,
             "caption": "Core domain model. Evidence trails attach to every finding."}))
add(("tab", {
    "key": "entities",
    "caption": "Entity types extracted from each paper.",
    "headers": ["Type", "What it captures", "Typical source section"],
    "widths": [2.1, 3.1, 2.3],
    "rows": [
        ["objective", "What the paper sets out to do", "Abstract, introduction, conclusion"],
        ["methodology", "Techniques and procedures used", "Methodology, experiments"],
        ["dataset", "Named benchmarks and corpora", "Experiments, results"],
        ["model", "Named architectures and systems", "Methodology, results"],
        ["evaluation_metric", "Named measures such as accuracy or F1", "Experiments, results"],
        ["quantitative_result", "A sentence reporting a metric with a number", "Results, abstract"],
        ["limitation", "A stated weakness of the work", "Conclusion, discussion"],
        ["research_gap", "A stated open problem", "Introduction, conclusion"],
    ],
}))

add(("h2", "Segmentation Design"))
add(("p",
     "A PDF does not say where one section ends and the next begins. It only records where "
     "glyphs are drawn. So the structure has to be guessed, and the obvious guesses fail on real "
     "papers. A list of section names breaks because authors disagree about names: Background, "
     "Prior Work and Related Literature are the same section. Looking for bold text breaks "
     "because many templates leave headings in regular weight. Looking for short lines breaks "
     "worst on two-column pages, where every line is short. Our first attempt used all three "
     "and found no sections at all in one paper and 186 in another, with identical code."))
add(("p",
     "What finally worked was something every publisher does: headings are set larger than the "
     "text under them. For each document we find the usual body size, counting each font size "
     "by the number of characters set in it. A short line that is larger than that by a margin, "
     "and is not just a number, becomes a heading candidate. We strip any numbering and test "
     "the candidate against patterns for each section type. Because the test is relative to the "
     "document itself, nothing has to be retuned for a new venue."))
add(("code", {
    "caption": "Algorithm 4.1. Section segmentation by relative font size.",
    "lines": [
        "for each page of the PDF:",
        "    read every text line with its font size and weight",
        "body_size <- mode of font sizes, weighted by characters",
        "for each line:",
        "    if size(line) > body_size + margin and short(line):",
        "        text <- repair capitals, strip numbering",
        "        label <- first anchored pattern matching text",
        "        if label found: start a new segment",
        "    else append the line to the current segment",
        "if no heading was found anywhere:",
        "    split the document into three-page chunks labelled 'body'",
        "    mark the document as unstructured",
    ],
}))
add(("p",
     "Two more repairs were needed. Papers set in small capitals, such as ICLR papers, come out "
     "of text extraction with a stray space after the first letter, so the heading reads "
     "I NTRODUCTION and no word pattern matches it. We repair those first. And no paper is ever "
     "thrown away: if no heading is found at all, the text is cut into three-page chunks, marked "
     "as unstructured, and carried through every later stage."))

add(("h2", "Classification and Citation Design"))
add(("p",
     "Each paper gets one of three categories (experimental, survey or review, and "
     "methodological) by counting weighted signal phrases in its text. The three totals become "
     "a confidence, and any paper whose top two categories are too close is flagged for manual "
     "review. The code lets a language model be asked about uncertain papers, but that path is optional, off by default and not used in any experiment here."))
add(("p",
     "Reference lists are handled in two steps. First the block is split into separate entries. "
     "Then each entry is reduced to a key that can be compared across papers: the title when it "
     "can be found, otherwise the first author's surname plus the year. A further pass matches "
     "titles to find papers in the corpus that cite each other. These keys feed the citation "
     "part of the relationship score."))

add(("h2", "Extraction Design"))
add(("p",
     "Extraction is done by rules, in three kinds. A word list of about 230 dataset, metric, "
     "model and method names is matched on word boundaries; these are the terms that actually "
     "drive comparison between papers. Cue phrases are sentence patterns tied to a section, so "
     "\"we propose\" in an abstract marks an objective and \"remains an open problem\" marks a "
     "stated gap. Numeric claims are sentences that contain both a metric and a number, and "
     "they are what the contradiction stage later compares. At most twelve entities of a type "
     "are kept per segment, and a sentence is cut at 400 characters."))
add(("p",
     'The section a sentence sits in is a clue to its content, so each entity type is accepted only from the sections where it normally appears. Applied blindly, that rule would starve a paper whose sections we could not find, because there is no section to check against. For unstructured segments the rule is therefore switched off. We pay for this in precision for such papers, but their objectives, methods and results still reach the analysis. A paper that really has no method section, such as an editorial, just scores zero on methodology. We leave the other weights alone, because rescaling them would let a paper that matches on one dimension look the same as one matching on all five.'))
add(("p",
     "If an OpenAI key is supplied, an optional language-model backend can be chosen instead. It was not used in any experiment in this report. Its output "
     "is combined with the rule-based entities, not substituted for them, because the word lists "
     "reliably catch dataset and metric names that a model tends to rephrase."))

add(("h2", "Embedding Design"))
add(("p",
     'Entity text is embedded with the all-MiniLM-L6-v2 sentence-transformer whenever it can be loaded. If it cannot, the system uses a simpler space: TF-IDF ([[salton1988]]) fitted on the corpus itself, then reduced to 256 dimensions with a seeded random projection, which roughly preserves distances ([[johnson1984]]). Vectors are normalised, so cosine similarity becomes a dot product, and they are cached on disk. The fallback matters more than it looks. Without it, a machine with no model cache would produce all-zero vectors and the relationship score would quietly shrink to its dataset term, which is the failure the order check was added to catch.'))

add(("h2", ("Relationship Scoring Design", "scoring")))
add(("p",
     "Every pair of documents is scored from 0 to 1 on five dimensions, and the overall score is "
     "their weighted sum."))
add(("eq", ("S(a, b) = Σ w_k · S_k(a, b),   k ∈ {obj, meth, data, res, cite}", "1")))
add(("p",
     "{tab:dims} gives the measure for each dimension. The three semantic ones take the cosine "
     "similarity between the mean embeddings of the relevant entities. The dataset dimension "
     "uses set overlap instead, because dataset names are exact tokens and the Jaccard index "
     "([[jaccard1912]]) suits them better. The citation dimension is bibliographic coupling "
     "([[kessler1963]]), and a direct citation between the two papers counts as full overlap."))
add(("tab", {
    "key": "dims",
    "caption": "The five scoring dimensions.",
    "headers": ["Dimension", "Weight", "Measure", "Computed over"],
    "widths": [1.5, 0.9, 1.2, 3.7],
    "rows": [
        ["Objective", "0.25", "Cosine", "Mean embedding of the papers' objective entities"],
        ["Methodology", "0.25", "Cosine", "Mean embedding of methodology entities"],
        ["Dataset", "0.20", "Jaccard", "Sets of dataset names"],
        ["Results and metrics", "0.20", "Cosine", "Mean embedding of results and metric entities"],
        ["Citation", "0.10", "Jaccard", "Reference keys; 1.0 for a direct citation"],
    ],
}))
add(("fig", {"key": "weights", "file": "weights.png", "width_cm": 10.2,
             "caption": "Default weights. They sum to exactly 1.00 and can be changed at run time."}))
add(("p",
     "We chose these weights ourselves; they were not fitted to any data. The reasoning is "
     "simple. A paper's objective and its method together say what the paper is, so they share "
     "half the weight. Datasets and metrics are concrete and easy to check, so they share forty "
     "percent. Shared citations do show kinship, but late, since a paper cannot cite work that "
     "came after it, so they get the last tenth. Two things stop this from being arbitrary. The "
     "configuration loader refuses any weights that do not add up to exactly 1.0, which keeps "
     "scores comparable between runs. And the interface lets a reader change the weights and "
     "recompute, so anyone who disagrees with our judgement can substitute their own."))
add(("p",
     "One detail is easy to get wrong. Cosine similarity runs from -1 to 1, but two papers are "
     "either related to some degree or not related at all. Opposite vectors mean unrelated, not "
     "anti-related. So every similarity is clamped into the range 0 to 1 before the weights are "
     "applied. This turned out to matter in practice, as {sec:defects} explains."))

add(("h2", "Knowledge Graph Design"))
add(("p",
     "The graph is a NetworkX directed multigraph ([[hagberg2008]]) with three kinds of node: "
     "documents, entities and bridge entities. A bridge entity is a concept, such as a dataset, "
     "model or method, that appears in two or more documents. It is linked to each of them, and "
     "that is what lets a path run from one paper to another through shared content. Edges are "
     "typed. Documents connect to their entities by contains edges. Extracted relations such "
     "as uses, evaluates-on and outperforms connect entities. Relationship-score edges join "
     "pairs of documents and carry the total and its parts. Has-bridge-entity edges tie "
     "documents to their shared concepts. Every edge keeps its evidence. The graph saves to "
     "JSON and loads back unchanged, and a test checks that."))

add(("h2", "Contradiction Detection Design"))
add(("p",
     'Whether two papers contradict each other is mostly a question of whether their numbers can be compared at all, and the numbers cannot answer that themselves. So a claims module first turns each sentence into measurements and applies five distinctions, each learned from a false positive on real papers ({tab:distinctions}).'))
add(("tab", {
    "key": "distinctions",
    "caption": "Distinctions a numeric claim must satisfy before it is compared.",
    "headers": ["Distinction", "Example", "Why it matters"],
    "widths": [1.5, 3.2, 2.7],
    "rows": [
        ["Value or change", "“+1.2% top-1 accuracy” against “79.9% accuracy”", "A delta is not a level"],
        ["Own result or quoted", "“reaches 81.3% against 88.5% reported elsewhere”", "Only the first belongs to the paper"],
        ["Which metric", "“an EM of 81.2% and an F1 of 88.9%”", "Each value binds to the nearest metric"],
        ["Which variant", "top-1 against top-5 accuracy", "Different quantities, not in conflict"],
        ["Which regime", "linear-probe, fine-tuned, zero-shot", "Numbers are not interchangeable across regimes"],
    ],
}))
add(("p",
     "Two detectors then run and their results are merged. One is a cross-encoder trained for "
     "natural language inference. It receives two claim sentences as a genuine pair and "
     "predicts whether they agree, conflict or are unrelated. The other is a numeric detector "
     "that needs no model. It pulls out the figure each paper reports for a measure, checks "
     "that the experimental conditions do not clash, and raises a finding when the two figures "
     "differ by more than 5%. Its confidence starts at 0.62 and rises with the size of the gap "
     "until it levels off at a 30% difference. Because it has no model dependency, it is the "
     "part that keeps working when the inference model cannot be loaded."))
add(("p",
     "Both are bounded. Two papers are examined only if they share a bridge concept or score "
     "above 0.35 together. A document offers at most eight claims, a pair of documents at most "
     "24 claim pairs, and three findings are kept per pair. Papers with nothing in common cannot "
     "contradict each other, and without this bound the stage would grow with the square of "
     "the corpus."))
add(("p", "A finding is confirmed only when all four of the following hold:"))
add(("num", [
    "the stance reported by the inference model is contradiction;",
    "the model's confidence is at least 0.60;",
    "the two papers share a dataset or report comparable metrics; and",
    "their methodology similarity, the S_meth term of Equation 1, is at least 0.30.",
]))
add(("p",
     "A finding that fails any of these is not thrown away. It stays in the output as "
     "unconfirmed. The methodology condition removes the commonest false positive, where two "
     "papers report different numbers only because they measured different things."))

add(("h2", ("Research Gap Discovery Design", "gapdesign")))
add(("p",
     "Gaps come in three forms and we do not trust them equally ({tab:gapkinds}). A stated gap "
     "is one the authors wrote themselves. It is the most dependable kind, and wording such as "
     "\"to the best of our knowledge\" raises its score. A weak-connection gap appears when "
     "several papers share one specific concept but are otherwise dissimilar. An absent "
     "pairing is a method or model and a dataset that never appear together. That last kind is "
     "the least reliable, because most combinations have never been tried and for good reason. "
     "We propose one only when each side is backed by at least three papers, the two groups do "
     "not already overlap, and they are related to each other at a level of 0.40 or more."))
add(("tab", {
    "key": "gapkinds",
    "caption": "The three gap detectors and their caps.",
    "headers": ["Kind", "Evidence", "Cap before ranking"],
    "widths": [1.4, 4.4, 1.5],
    "rows": [
        ["Stated", "Sentence extracted as a research-gap or limitation, at least 45 characters", "8"],
        ["Weak connection", "Shared concept (spread at most 6 papers) but low pairwise scores", "2"],
        ["Absent pairing", "Methodology or model and dataset that never occur together, both with 3+ papers", "1"],
    ],
}))
add(("p",
     "The first version of this stage returned about sixty gaps, which is a pile to dig through "
     "and not a list to read. The final version ranks candidates by an importance score, drops "
     "anything below 0.60 and returns at most five. Recall goes down, and we think that is the "
     "right trade."))

add(("h2", "Explanation and Reporting Design"))
add(("p",
     "When the optional language-model backend is configured (it was not, in any experiment here), an explainer collects a small evidence set for "
     "each finding and asks the model to explain it using only that evidence, with citations in "
     "the form [document, section, page]. A finding with fewer than two supporting edges is "
     "marked low-confidence. Reports come out as JSON, Markdown and PDF. The PDF is laid out by "
     "a small engine on top of PyMuPDF, which we already depend on, so no extra package is "
     "needed."))

add(("h2", "API Design"))
add(("p",
     "{tab:api} lists the endpoints. The data endpoints return empty lists, not errors, before "
     "the first run, so the interface can show an empty state. Progress is pushed over a "
     "WebSocket, which replays earlier events to a client that connects partway through a run."))
add(("tab", {
    "key": "api",
    "caption": "HTTP and WebSocket interface of the service.",
    "size": 10,
    "headers": ["Method and path", "Purpose"],
    "widths": [2.6, 4.6],
    "rows": [
        ["GET /api/status", "Corpus contents, whether results exist, summary counts, configuration"],
        ["POST /api/upload", "Add a PDF to the corpus after checking its %PDF header"],
        ["DELETE /api/corpus/{filename}", "Remove a PDF from the corpus"],
        ["POST /api/corpus/seed", "Load the bundled sample or the arXiv corpus"],
        ["POST /api/corpus/fetch-arxiv", "Fetch the thirty-paper arXiv corpus in the background"],
        ["POST /api/run", "Start a pipeline run on a worker thread; refuses a second concurrent run"],
        ["WS /ws/progress", "Stream progress events; replay the backlog on connect"],
        ["GET /api/documents", "Documents with category, sections and reference count"],
        ["GET /api/scores", "Pairwise scores, strongest first, with components"],
        ["GET /api/graph", "Knowledge graph in Cytoscape element format"],
        ["GET /api/contradictions", "Findings with stance, signals and evidence"],
        ["GET /api/gaps", "Ranked gaps with evidence"],
        ["GET /api/entities", "Extracted entities, optionally for one document"],
        ["GET /api/report?fmt=", "Download the JSON, Markdown or PDF report"],
        ["POST /api/config/weights", "Change the five weights; rejected unless they sum to 1"],
        ["GET /api/backend", "Runtime, configuration, storage and endpoint counts of the server itself"],
    ],
}))

add(("h2", "Interface Design"))
add(("p",
     "The interface ({fig:workspace}) is built around the questions a reader brings. A strip of "
     "headline counts sits at the top. Below it, tabs switch between the knowledge graph, the "
     "relationship matrix, contradictions, research gaps and the document table. On the right, "
     "an inspector shows whatever is selected, together with its source sentence, section and "
     "page. We assigned colour by job. Three hues, checked for colour-vision deficiency, mark "
     "node kinds, and node shape carries entity type as a second signal so meaning never rests on "
     "hue alone. One light-to-dark ramp encodes magnitudes such as scores. Contradiction status "
     "has its own reserved colours and always comes with an icon and a label. Each contradiction "
     "is laid out in two columns, with the disputed figures highlighted."))
add(("fig", {"key": "workspace", "file": "fig2_workspace.png", "width_cm": 13.0,
             "caption": "The analysis workspace. Graph, inspector and the pairwise score matrix."}))

add(("h2", ("Deployment Design", "deployment")))
add(("p",
     "The deployed system has two halves ({fig:deploy}). The API runs on Render as one web "
     "service, and the static interface runs on Vercel. The interface takes the API address "
     "from a query string or a dialog, so one build works with any backend. If no API answers, "
     "it loads a saved analysis of the thirty-paper corpus and works read-only, which is why the "
     "public interface never opens empty. Render's free tier has a disk that is wiped when the "
     "instance restarts, so uploaded papers and reports last only until then. The server "
     "therefore seeds its own corpus at start-up, and serves a status page at its root so the "
     "operator can see what it actually holds."))
add(("fig", {"key": "deploy", "file": "deployment.png", "width_cm": 12.4,
             "caption": "Deployment topology. The interface falls back to a saved analysis when no API answers."}))

# ======================================================================
# CHAPTER 5 - IMPLEMENTATION
# ======================================================================
add(("h1", "Implementation"))

add(("h2", "Code Organisation"))
add(("p",
     "The Python package is about 8,500 lines in twenty-two modules. The front end adds about "
     "3,300 lines of HTML, CSS and JavaScript, and the tests about 6,200. {tab:modules} lists "
     "the modules. Only the pipeline module knows the order of the stages; every other module "
     "implements one stage and depends only on the data models."))
add(("tab", {
    "key": "modules",
    "caption": "Modules of the rpra package and their responsibilities.",
    "size": 10,
    "headers": ["Module", "Lines", "Responsibility"],
    "widths": [2.2, 0.7, 4.6],
    "rows": [
        ["models", "215", "Pydantic data models and enumerations"],
        ["config", "181", "Configuration loading and validation (weights must sum to 1)"],
        ["ingestion", "556", "PDF reading, heading detection, segmentation"],
        ["classification", "205", "Document category and confidence"],
        ["citations", "213", "Reference parsing; paper-to-paper citation detection"],
        ["heuristic_extraction", "495", "Rule-based entity and relation extraction"],
        ["extraction", "500", "Backend selection and merging (rules and optional model)"],
        ["embeddings", "437", "Sentence-transformer backend with TF-IDF fallback; caching"],
        ["scoring", "253", "Five-dimension pairwise scoring"],
        ["knowledge_graph", "277", "Graph construction, queries, JSON persistence"],
        ["claims", "386", "Measurement parsing and comparability rules"],
        ["contradiction", "753", "Numeric and inference detectors; confirmation gates"],
        ["gap_discovery", "547", "Stated, weak and absent gap detectors; ranking"],
        ["explainer", "157", "Evidence-grounded explanation (optional)"],
        ["reporter, report_pdf", "732", "JSON, Markdown and PDF export"],
        ["progress", "152", "Progress events, console panel, JSON log"],
        ["pipeline", "441", "Orchestration in dependency order"],
        ["server", "1,100", "REST, WebSocket, static hosting, corpus seeding"],
        ["cli", "163", "The rpra command: run, serve, validate-config"],
        ["arxiv_corpus, sample_corpus", "708", "Evaluation corpus acquisition; synthetic corpus with planted contradictions"],
    ],
}))

add(("h2", "Ingestion and Segmentation"))
add(("p",
     "Ingestion opens each PDF with PyMuPDF and reads every text line with its font size and "
     "weight. The body size is worked out once per document. A heading is accepted if it passes "
     "the size test, is at most 90 characters and ten words long, and matches one of the section "
     "patterns once numbering and small-capital artefacts are removed. Every segment keeps its "
     "page numbers, which is what lets a finding cite a page later. A file that cannot be "
     "opened, is encrypted or has no text is logged as an ingestion error with its path and the "
     "reason, and the run carries on. Files that are not PDFs are rejected with a reason."))
add(("p",
     "In the evaluation all thirty documents segmented from detected headings and none needed "
     "the page-chunk fallback. The fallback is still there, and a test covers it with a "
     "document built to have no headings."))

add(("h2", "Extraction"))
add(("p",
     "The word lists are compiled once into regular expressions with word boundaries and matched "
     "against each sentence. Sentences are split at final punctuation followed by a capital "
     "letter or an opening bracket, then filtered so that fragments such as table rows are not "
     "treated as sentences. Names that look like acronyms need an exact-case match; otherwise "
     "\"ALL\" would be found inside ordinary uses of \"all\". Every entity records its "
     "sentence, section and page, and that is the evidence trail used everywhere downstream."))

add(("h2", "Embedding"))
add(("p",
     "An embedding backend object picks its implementation when it is created and exposes one "
     "method, which turns a list of strings into an array of unit vectors. The sentence "
     "transformer takes about fourteen seconds to load, and loading it inside the first user "
     "request made that request look broken. So the server now loads the model on a background "
     "thread at start-up, and keeps it for the life of the process. Entities are embedded "
     "together with a short context string so that the same word in two sections does not get "
     "an identical vector."))

add(("h2", "Scoring"))
add(("code", {
    "caption": "Algorithm 5.1. Pairwise relationship scoring.",
    "lines": [
        "for each unordered pair (a, b) of documents:",
        "    s_obj  <- clamp(cos(mean(objectives(a)), mean(objectives(b))))",
        "    s_meth <- clamp(cos(mean(methods(a)), mean(methods(b))))",
        "    s_data <- jaccard(datasets(a), datasets(b))",
        "    s_res  <- clamp(cos(mean(results(a)), mean(results(b))))",
        "    s_cite <- 1.0 if a cites b or b cites a",
        "             else jaccard(refs(a), refs(b))",
        "    S      <- sum of w_k * s_k over the five dimensions",
        "    store S with its five components and the weights",
    ],
}))
add(("p",
     "Thirty papers give 435 pairs, and each score is stored with its five components and the "
     "weights used, so a result file explains itself. Progress is reported every fifty pairs."))

add(("h2", "Contradiction Detection"))
add(("code", {
    "caption": "Algorithm 5.2. Contradiction detection and confirmation.",
    "lines": [
        "pairs <- pairs sharing a bridge concept, or with S > 0.35",
        "for each pair (a, b) in pairs:",
        "    claims_a, claims_b <- up to 8 numeric claims each",
        "    for each comparable (x, y), at most 24 per pair:",
        "        numeric <- flag if relative difference > 5%",
        "        stance  <- NLI(x, y), batches of 16, 256 tokens",
        "        finding <- merge numeric and stance results",
        "    keep the 3 strongest findings for the pair",
        "for each finding:",
        "    if stance = contradiction and p >= 0.60",
        "       and (same dataset or comparable metric)",
        "       and methodology_similarity >= 0.30: confirmed",
        "    else: unconfirmed",
    ],
}))
add(("p",
     "Inference was the first place we ran out of memory. One model call per claim pair "
     "exhausted the CPU memory of the development laptop. Calls are now batched in groups of "
     "sixteen with a cap on token length, and a failed allocation costs one batch instead of "
     "every verdict. A second bug was subtler. An early version joined the two claims into one "
     "string with a separator, but a cross-encoder expects two separate texts. It was scoring "
     "one malformed string and returning labels that meant nothing."))

add(("h2", "Gap Discovery"))
add(("p",
     "Concepts are indexed by the documents that contain them. Stated gaps are read straight from "
     "entities typed as gaps or limitations, deduplicated, and scored by how strongly they are "
     "worded. Weak-connection gaps scan the bridge concepts for ones whose documents have a low "
     "average pairwise score. Absent pairings list the method-and-dataset combinations that "
     "never occur together and apply the conditions from {sec:gapdesign}. All candidates are "
     "then ranked by importance, filtered at 0.60 and cut to five. Concept text keeps its "
     "original capitalisation, so a report says CIFAR-10 and not cifar-10."))

add(("h2", "Service Layer"))
add(("p",
     'Results live in a shared object behind a lock. A run happens on a worker thread while the main event loop keeps answering requests, so both sides need protection. The worker has no event loop of its own, and asking for one raises an error, so the request handler grabs the running loop first and passes it along for broadcasting progress. Events are also kept in a list, which lets a client that joins mid-run catch up on what it missed. If a run is already going, a second request is refused with a conflict status.'))
add(("p",
     "Two features were added for running the service. A start-up hook seeds the corpus when the "
     "directory is empty and can fetch the thirty-paper arXiv set in the background, leaving a "
     "few seconds between downloads as arXiv asks. And the root of the service serves a backend "
     "status page, backed by the /api/backend endpoint, with tables for the runtime, "
     "configuration, last run, endpoint row counts, pipeline stages, storage and corpus files. "
     "We added it because the interface can imitate every analysis endpoint from its saved "
     "bundle, so looking at the interface cannot tell you whether a live server is behind it."))

add(("h2", "Web Interface"))
add(("p",
     "The interface is plain JavaScript with no build step. The graph is drawn with Cytoscape.js "
     "([[franz2016]]) in three views. The paper network shows papers only, joined by their "
     "relationship score, with a slider that hides the weaker links. The shared-concepts view "
     "shows papers and the bridge concepts between them. It leaves out any concept that spans "
     "more than four papers, because a concept linking nearly everything says nothing about "
     "any particular pair, and it caps the view at forty concepts. The full view shows "
     "everything and is labelled dense for a reason. Selecting a node dims everything outside "
     "its neighbourhood. In the matrix view each cell is coloured by score, and clicking it "
     "opens the five-part breakdown."))
add(("p",
     "Because the public interface is static, it has to cope with no server. On load it asks "
     "the configured API for its status. If that fails, it loads a bundle holding the exact "
     "payloads from a real run, shows a banner saying so, and disables the run button. A "
     "Connect backend dialog stores the API address in the query string."))

add(("h2", "Report Generation"))
add(("p",
     'The PDF report begins with a cover page of headline numbers. After it come the strongest relationships, then each confirmed contradiction in two columns beside its evidence, then the ranked gaps. The layout code is roughly five hundred lines. It tracks a vertical position on the page, every drawing call says how much height it used, and a new page starts when the next block does not fit. We wrote it because the alternative was a PDF library larger than everything else in the service. Characters the standard fonts lack are swapped for safe ones, so nothing prints as an empty box.'))

add(("h2", ("Defects Found and Fixed", "defects")))
add(("p",
     "A lot of the engineering effort went into bugs that did not announce themselves. "
     "{tab:defects} lists the most instructive. They share a pattern: the output still looked "
     "plausible. The score that dropped 203 of 435 pairs raised no error. The composite that "
     "shrank to its dataset term still returned numbers between zero and one. We found both by "
     "counting the output instead of reading the code, and the end-to-end test now asserts "
     "those counts."))
add(("tab", {
    "key": "defects",
    "caption": "Representative defects, their visible effect and their fix.",
    "size": 10,
    "headers": ["Defect", "Effect", "Fix"],
    "widths": [2.5, 2.6, 2.4],
    "rows": [
        ["No embedding stage ran; three score dimensions always read zero", "Composite reduced to 0.20 × dataset overlap; ranking meaningless", "Embedding stage added before scoring, with a fallback backend"],
        ["Negative cosine similarity passed to a [0, 1] model", "203 of 435 pairs silently dropped", "Clamp each similarity to [0, 1]"],
        ["Heading detection by text and line length", "0 sections in one paper, 186 in another", "Relative font size; small-capital repair; page-chunk fallback"],
        ["API handlers written against a different schema than the models", "Five of six data endpoints returned HTTP 500 on real data", "Handlers rewritten; tests now populate a real result first"],
        ["Event loop requested from the worker thread", "No progress event reached the interface", "Loop captured on the main thread"],
        ["Dataset names matched as substrings", "CIFAR-10 compared against CIFAR-100 and reported as a contradiction", "Whole-term matching"],
        ["Claims joined into one string for inference", "Meaningless stance labels", "Claims passed to the cross-encoder as a pair"],
        ["No gate on comparability", "Over a thousand spurious contradictions on the real corpus in an early version", "Comparability gates (measured in Chapter 7)"],
        ["Single narrow gap rule", "0 gaps on a corpus with 15 stated gaps", "Three detectors with ranking and a cap"],
        ["Static-host route rewrote /static/x to /static/static/x", "Deployed interface could not load its own CSS and JavaScript", "Corrected routes"],
    ],
}))
