"""Chapters 9-10 of the project report: testing and deployment, conclusion."""

from __future__ import annotations

BLOCKS: list = []
add = BLOCKS.append

# ======================================================================
# CHAPTER 8 - TESTING AND DEPLOYMENT
# ======================================================================
add(("h1", "Testing and Deployment"))

add(("h2", "Test Strategy"))
add(("p",
     "The automated suite has 236 tests in fourteen files ({tab:tests}). We built it after a "
     "specific failure. When the project was first assessed, 33 tests passed while the analyzer "
     "was not actually analysing anything: the embedding stage did not exist, five of six data "
     "endpoints crashed on real results, and every score except one was zero by construction. "
     "The tests passed because they ran on empty results, where the handlers return early "
     "before touching the fields that were wrong. After that we ran tests on populated results "
     "and made them assert the properties that had been silently broken."))
add(("tab", {
    "key": "tests",
    "caption": "The automated test suite by file.",
    "headers": ["Test file", "Tests", "Concern"],
    "widths": [2.3, 0.8, 4.4],
    "rows": [
        ["test_ingestion", "45", "Heading detection, small capitals, numbering, fallback, malformed files"],
        ["test_claims", "30", "Value versus change, own versus quoted figure, metric variants, regimes"],
        ["test_server", "27", "API against a populated result, upload checks, weights validation, status page"],
        ["test_pipeline_e2e", "22", "Whole pipeline over generated PDFs, offline"],
        ["test_contradiction", "20", "Numeric and inference detectors, confirmation gates, planted contradictions"],
        ["test_heuristic_extraction", "17", "Word lists, cue phrases, numeric claims, section affinity"],
        ["test_gap_discovery", "14", "Stated, weak and absent detectors; caps; ranking"],
        ["test_citations", "13", "Reference splitting, key extraction, intra-corpus citations"],
        ["test_scoring", "13", "Clamping, weights, Jaccard and cosine behaviour"],
        ["test_embeddings", "12", "Backend selection, fallback determinism, persistence"],
        ["test_corpus_sources", "8", "Corpus acquisition and local-copy behaviour"],
        ["test_classification", "6", "Category assignment and confidence"],
        ["test_models", "5", "Model validation and graph round trip"],
        ["test_config", "4", "Configuration validation, weights must sum to one"],
        ["**Total**", "**236**", ""],
    ],
}))

add(("h2", "End-to-End Assertions"))
add(("p",
     "The end-to-end test generates PDFs, runs the whole pipeline offline and asserts what had "
     "gone wrong before. Every entity must have an embedding. The semantic dimensions of the "
     "score must not all be zero. The citation dimension must contribute. Related papers must "
     "outrank unrelated ones. The two planted contradictions must be found. The number of "
     "scored pairs must equal n(n-1)/2, which is the assertion that would have caught the 203 "
     "silently dropped pairs. A separate test saves the knowledge graph, loads it again and "
     "requires the two to be equal, which covers requirement R18."))

add(("h2", "Deployment Procedure"))
add(("p", "Deploying the API on Render takes five steps."))
add(("num", [
    "Push the repository to GitHub.",
    "In Render, create a web service from the repository. The render.yaml file supplies the "
    "settings: Python 3.11, the free plan, the oregon region, a build command that installs "
    "from requirements.txt, and a start command that runs Uvicorn on the port Render assigns.",
    "Leave the OpenAI key unset. The service then uses the rule-based backend and needs nothing "
    "else.",
    "Wait for the health check on /api/status to pass. On start-up the service seeds the "
    "corpus, and with the arXiv option set it fetches the thirty papers in the background.",
    "Open the service address. The root shows the backend status page, and the full interface "
    "is at /app.",
]))
add(("p",
     "The static interface deploys to Vercel from the same repository, with a small routing file "
     "that maps /static paths onto the interface directory. To point it at the API, use the "
     "Connect backend dialog or an ?api= query parameter."))

add(("h2", "Operational Notes"))
add(("p",
     "Several limits of the free hosting tier shaped decisions earlier in the project. The "
     "build installs only the core dependencies, about 174 MB. The transformer stack, around "
     "2.5 GB, is more than a small instance can build. Every use of the heavy libraries is "
     "imported lazily behind a working fallback, so the service starts and finishes an "
     "analysis without them. The file system is wiped when the instance restarts or spins "
     "down after inactivity, and the first request after a spin-down is slow. That is why the "
     "server seeds its own corpus at start-up and why the status page shows exactly what is on "
     "disk."))
add(("p",
     "We checked the deployed instance after it went up. It answers on its public address, "
     "the interface shows a live connection, and the status bar reported the arXiv corpus ready "
     "with all thirty papers downloaded. Before a first analysis the graph and score views are "
     "empty, which is correct: results exist only after a run, and the saved analysis appears "
     "only when no server answers at all. Two risks remain. The API has no authentication, no "
     "upload size limit and accepts requests from any origin. That is fine for a demonstration "
     "and not for a shared deployment."))

# ======================================================================
# CHAPTER 9 - CONCLUSION
# ======================================================================
add(("h1", "Conclusion and Future Work"))

add(("h2", "Conclusion"))
add(("p",
     'Comparing papers is something researchers still do by hand. We wanted to automate it without losing the ability to check the result. The system we built reads a folder of PDFs and reports how the papers relate, where they disagree and what they leave out, and every finding points to a sentence on a page. It needs no outside service, has no generative language model in it, offers a documented API and a browser interface, and is deployed publicly.'))
add(("p",
     'We tested on thirty papers chosen to have a known structure. Segmentation worked for every paper and found 90% of the expected sections. Related papers were ranked far above chance (AUC 0.86 against 0.50, MAP 0.68 against 0.31) and the score beat each of its own parts, but it did not beat full-text TF-IDF (AUC 0.87, MAP 0.78), so what it offers is explanation, not accuracy. The numeric contradiction detector found both planted contradictions with no false alarm and confirmed nothing on real papers, while adding the inference model cost precision. The graph showed real but coarse community structure. Gap discovery returned five gaps we can check, where its first version returned sixty. {tab:objectives} sets these outcomes against the objectives from Chapter 1.'))
add(("tab", {
    "key": "objectives",
    "caption": "Objectives of Chapter 1 and how each was met.",
    "size": 10,
    "headers": ["#", "Objective", "Outcome"],
    "widths": [0.4, 3.0, 4.2],
    "rows": [
        ["1", "Reliable segmentation", "30 of 30 papers from detected headings; 215 of 240 sections"],
        ["2", "Typed entity extraction with source", "Eight entity types, each with sentence, section and page"],
        ["3", "Five-dimension score, weights sum to one", "Implemented and enforced; AUC 0.86, but below full-text TF-IDF on MAP and nDCG"],
        ["4", "Knowledge graph with evidence", "1,159 nodes and 2,047 edges; two coarse communities; lossless round trip"],
        ["5", "Contradiction detection, few false positives", "No false positives on real papers; both planted contradictions found; none confirmed on real papers"],
        ["6", "Short, ranked list of gaps", "Five gaps, each with evidence; two are weak"],
        ["7", "API, interface and deployment", "Deployed on Render and Vercel; backend status page"],
        ["8", "Evaluation against known truth", "Clustered corpus, eight baselines, ablation, gate and threshold analysis, 236 tests"],
    ],
}))
add(("p",
     "If one lesson carries over to other projects, it is that the failures that matter in a "
     "pipeline like this do not look like failures. A missing stage, a clamped value and a "
     "heading detector that returned zero sections each produced output that a reader would "
     "have accepted. What caught them was counting the output against what it should have been, "
     "and building the system so that a degraded result says it is degraded. The baseline "
     "comparison taught the same thing about our own result: a number that looks good is only "
     "good compared with something."))

add(("h2", "Limitations"))
add(("bul", [
    "Extraction is rule-based and English-only, and its word lists are specific to machine learning.",
    "Scanned PDFs give no text and are reported as errors, since no optical character recognition is attempted.",
    "Pairwise scoring is quadratic. That is fine at thirty papers and workable at a few "
    "hundred, but not at tens of thousands.",
    "Requirement R11 is not implemented, so adding one paper reprocesses the whole corpus.",
    "Requirement R9 is only partly done: evidence trails are complete, but no pruned evidence "
    "subgraph is built for each finding.",
    "The contradiction finding rests on a single corpus from a single field.",
]))

add(("h2", "Future Work"))
add(("num", [
    "Incremental updates. Record each processed file's content hash in a manifest, skip files "
    "that have not changed, merge new nodes and edges into the existing graph, and rescore only "
    "the pairs involving a new paper. This is the biggest requirement still open.",
    "Evidence graphs. Build a pruned subgraph for each finding and pass it to the explainer, so "
    "explanations come from a graph and not from a flat list.",
    "Scale. Add an approximate nearest-neighbour index to pick candidate pairs before exact "
    "scoring, stream documents instead of holding the corpus in memory, and move the graph "
    "from a JSON file to an indexed store.",
    "Experimental settings. The remaining false-positive pattern is two sentences that share "
    "dataset, metric and direction but describe different conditions. Fixing it means parsing "
    "and comparing the experimental setting, not just the sentence.",
    "Learned weights. Collect a small labelled set of related and unrelated pairs, and study "
    "how sensitive the ranking is to the weights instead of asserting them.",
    "Broader extraction. Extend the word lists to other fields or add a local entity "
    "recogniser, and add optical character recognition for scanned papers.",
    "Hardening. Add authentication, upload size limits, rate limiting and restricted origins "
    "before any shared deployment.",
    "A held-out evaluation. Collect a second corpus that none of our thresholds were set on, "
    "label a sample of real contradictions by hand, and measure precision and recall there. This "
    "would also test the claim that the gates remove spurious findings without losing real ones.",
    "Fix the page numbers. Two of five gap records cite the page before the one the sentence is on.",
    "A user study. Ask researchers to review a real corpus with and without the tool and compare "
    "the time taken and what they noticed. That would test the claim that provenance makes the "
    "output more usable, which this evaluation does not.",
]))
