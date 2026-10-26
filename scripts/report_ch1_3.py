"""Chapters 1-3 of the project report: introduction, literature survey, requirements."""

from __future__ import annotations

BLOCKS: list = []
add = BLOCKS.append

# ======================================================================
# CHAPTER 1
# ======================================================================
add(("h1", "Introduction"))

add(("h2", "Background"))
add(("p",
     "When you start working in a new research area, the first month goes on reading. After "
     "thirty or forty papers the shape of the field starts to show. But that shape is not "
     "written down in any of the papers. Each paper tells you about its own method and its own "
     "numbers. What you actually need to know is how the papers fit together: which of them are "
     "really working on the same problem, which ones disagree, and what nobody has tried yet."))
add(("p",
     "Tools help with the first half of this. Search engines and citation managers find papers "
     "and keep them organised, and extraction tools can pull names and numbers out of a single "
     "paper. The comparing is still done by hand, in notes, spreadsheets and memory. This "
     "project tries to do that comparison automatically, in a way a reader can check."))

add(("h2", "Motivation"))
add(("p",
     "The idea came from our own literature survey for this course. We read eighteen papers on "
     "knowledge graphs, information extraction, contradiction detection and related topics. "
     "Reading them was the easy part. Building the comparison table at the end took longer, and "
     "it was the part we trusted least, because every cell was a judgement made from memory and "
     "a few highlighted lines. A tool that filled in that table, with each cell pointing to a "
     "sentence on a page, would have been worth more to us than the table."))
add(("p",
     "The survey also showed what existing work leaves out. Most systems automate one stage and "
     "stop there. Contradiction detection has mostly been studied on clinical text. Gap "
     "discovery usually means topic modelling over abstracts. Language models used for "
     "extraction sometimes make things up, and nearly every paper we read called explainability "
     "an open problem. {tab:gaps} lists these gaps next to what this project does about each."))
add(("tab", {
    "key": "gaps",
    "caption": "Gaps found in the literature survey and how this project responds to each.",
    "headers": ["Gap in existing work", "Response in this project"],
    "widths": [1, 1],
    "rows": [
        ["No end-to-end automation from raw PDFs to insight",
         "One pipeline from PDF to segments, entities, scores, graph, contradictions, gaps and report"],
        ["Extracted entities rarely flow into a live graph",
         "Entities become nodes of a queryable NetworkX graph as soon as they are extracted"],
        ["Contradiction detection is domain-specific (clinical text)",
         "Numeric comparison plus natural language inference, checked for comparability"],
        ["Gap discovery works on abstracts and topic clusters only",
         "Full-paper entities, bridge concepts and pairwise scores; three kinds of gap"],
        ["Language-model extraction hallucinates and is hard to reproduce",
         "Rule-based extraction by default; a model is optional and its output is merged, not trusted alone"],
        ["Explainability is an open problem",
         "Every score, contradiction and gap carries document, section, page and the original sentence"],
        ["Updating the graph as papers arrive is poorly supported",
         "Incremental mode is planned but not finished (see Chapter 10)"],
    ],
}))

add(("h2", "Problem Statement"))
add(("p",
     "Given a folder of research papers as PDFs, the system should tell the reader three things. "
     "First, how strongly each pair of papers is related, and why. Second, where two papers "
     "report conflicting results for comparable experiments. Third, which research directions "
     "the collection leaves open. Every answer has to point back to the text it came from. And "
     "it has to work without a paid outside service, because researchers often hold manuscripts "
     "that they cannot upload anywhere."))

add(("h2", "Objectives"))
add(("num", [
    "Read PDF papers and recover their section structure reliably, including papers whose layout "
    "defeats simple heading detection.",
    "Extract typed entities (objectives, methods, datasets, models, metrics, results, limitations "
    "and stated gaps) together with the sentence, section and page they came from.",
    "Score every pair of papers on five separate dimensions, with weights that can be changed but "
    "must add up to one.",
    "Build a knowledge graph of papers, entities and shared concepts, with evidence on every edge.",
    "Detect contradictions across papers without flooding the reader with false alarms.",
    "Report a short, ranked list of research gaps, each with its supporting sentence.",
    "Serve all of this through an API and a browser interface, and deploy it.",
    "Measure each stage against a corpus where the right answer is known.",
]))

add(("h2", "Role of Language Models"))
add(("p",
     "The term large language model is used loosely, so we say exactly what this project does and "
     "does not use. The analysis pipeline contains no generative large language model. Entity "
     "extraction is rule-based. Two small pretrained encoder models are used, both exactly as "
     "published: a sentence-transformer (all-MiniLM-L6-v2) that turns text into vectors, and a "
     "DeBERTa cross-encoder that labels a pair of sentences as entailment, contradiction or "
     "neutral. Neither generates text."))
add(("p",
     "The code also contains an optional backend that can call an OpenAI model, either to extract "
     "entities or to write plain-language explanations of findings. It is switched off unless an "
     "API key is supplied, and no key was supplied for any experiment in this report. Every "
     "result here comes from rule-based extraction. We describe the optional backend in "
     "Chapters 3 and 4 because it exists in the software, but its output is not evaluated and we "
     "make no claim about it."))

add(("h2", "Scope of the Project"))
add(("p",
     "The system works on English papers supplied as text-based PDFs. We evaluated it on thirty "
     "machine learning papers, because that field has shared benchmarks and papers that cite one "
     "another heavily, and those are what the scoring and contradiction stages need if they are "
     "to be tested at all. Nothing in the design is specific to machine learning, but the word "
     "lists used for extraction are, and moving to another field means extending them."))
add(("p",
     "A few things are left out on purpose. There is no optical character recognition, so scanned "
     "PDFs are reported as errors. We do not train or fine-tune any model; every model is used "
     "as it was published. The system says that two papers disagree and does not try to say "
     "which one is right. And scoring compares every pair of papers, so it is meant for tens or "
     "a few hundred papers, not for a whole digital library."))

add(("h2", "Contributions"))
add(("bul", [
    "A way of finding paper sections from relative font size, with a fallback so that no paper is ever dropped.",
    "A relationship score built from five separate parts, always shown with its parts.",
    "A contradiction detector that merges numeric comparison with natural language inference, "
    "and confirms a result only after four explicit checks.",
    "A gap finder that tells stated, weakly connected and missing gaps apart, and returns at most five.",
    "A web interface and a backend status page, deployed publicly, with a saved analysis so that "
    "the interface still works when no server is reachable.",
    "A thirty-paper evaluation corpus, a test suite of 236 tests, and the scripts that reproduce "
    "every figure in this report.",
]))

add(("h2", "Organisation of the Report"))
add(("p",
     "Chapter 2 reviews the literature. Chapter 3 lists the requirements. Chapters 4 and 5 "
     "describe the design and how it was built. Chapter 6 introduces the evaluation corpus, "
     "the metrics and the thresholds, and Chapter 7 gives the results. Chapter 8 is a separate "
     "discussion of strengths and weaknesses. Chapter 9 covers testing and deployment, and "
     "Chapter 10 concludes with limitations and future work. The appendices hold the "
     "configuration, sample output and the repository layout."))

# ======================================================================
# CHAPTER 2
# ======================================================================
add(("h1", "Literature Survey"))

add(("h2", "What We Read"))
add(("p",
     "Our survey covered eighteen papers in six areas: knowledge graph construction, information "
     "extraction, cross-document relation extraction, claim verification and contradiction "
     "detection, research gap discovery, and semantic similarity. This chapter keeps the parts "
     "that shaped the design, and adds the older work the implementation relies on. We checked "
     "every reference against the publisher's page while writing this, and a few details in our "
     "earlier survey turned out to be wrong, such as the year of Di Iorio et al. They are "
     "corrected here."))

add(("h2", "Knowledge Graph Construction"))
add(("p",
     "[[n:zhong2023]] divide knowledge graph construction into three steps: collecting knowledge "
     "from sources, cleaning it up, and keeping it current as things change. They name reasoning "
     "across documents and updating the graph as open problems, and both of those matter to us. "
     "[[n:ji2022]] cover the same area from the representation side, including how entities and "
     "relations are embedded and what graphs are used for afterwards. Neither survey builds a "
     "system."))
add(("p",
     "Closer to scholarly text, [[n:diiorio2017]] describe Semantic Lancet, which publishes the "
     "contents of articles as linked open data, including the reasons one paper cites another. "
     "The result is rich, but it depends on hand-built ontologies and on publisher data, so it "
     "cannot be pointed at an arbitrary folder of PDFs. [[n:milosevic2023]] compare rule-based, "
     "classical and transformer methods for building biomedical graphs, and a fine-tuned T5 "
     "model gave the best F1-score, 0.88. Their pipeline has the same shape as ours, for "
     "biomedicine only."))

add(("h2", "Information Extraction"))
add(("p",
     "[[n:xu2024]] survey extraction with generative language models and name hallucination, "
     "cost and inconsistent output formats as the main weaknesses. [[n:sciannameo2024]] show "
     "that a general model, prompted with no special training, can fill structured fields from "
     "208 medical case-report PDFs with accuracy above 80% on each of the four fields they "
     "report in detail. That is encouraging for turning PDFs into structure, though it was one "
     "kind of document and the result depended on the prompt."))
add(("p",
     "[[n:baldini2019]] learn relation representations from entity-linked text with no labelled "
     "relations, by training a model to tell whether two sentences mention the same pair of "
     "entities. [[n:luan2018]] build a multi-task system for entities, relations and coreference "
     "in scientific abstracts, and [[n:yao2019]] move relation extraction up to whole documents. "
     "All of these assume the text has already been split into sections and that labelled "
     "training data of the right kind exists. We had neither, which is why extraction in this "
     "project is rule-based and why segmentation is a stage of its own."))

add(("h2", "Relations Across Documents and Contradictions"))
add(("p",
     "Relations between papers, rather than inside one, get far less attention. "
     "[[n:wang2022]] improve cross-document relation extraction on the CodRED benchmark by "
     "filtering documents around entities and finding bridge entities that connect them. A bridge "
     "entity is a concept that shows up in several documents and so links them, and we use the "
     "same idea in our graph. [[n:yao2010]] had earlier shown that this can be done without "
     "labelled data. Both methods are heavier than a project this size can carry."))
add(("p",
     "Checking a claim against evidence is a better-studied task than finding disagreement "
     "between two papers. [[n:thorne2018]] built FEVER for claim verification, and "
     "[[n:wadden2020]] adapted it to scientific claims. [[n:fang2025]] add a pruned evidence "
     "graph, which improves the choice of supporting sentences but is early work and "
     "expensive to run. The one study aimed at contradictions in the scientific literature is "
     "[[n:makhervaks2023]]. They use a medical ontology to generate candidate contradictions "
     "from millions of PubMed abstracts and train models on them, with good results in the "
     "clinical domain. The catch is the ontology: the method cannot move to a field that has "
     "none. For the inference step we use a cross-encoder trained on MultiNLI "
     "([[williams2018]]) with a DeBERTa backbone ([[he2021]]), loaded through the "
     "Transformers library ([[wolf2020]])."))

add(("h2", "Research Gap Discovery"))
add(("p",
     "[[n:abdalrazaq2024]] ran BERTopic, which combines BERT embeddings, class-based TF-IDF, UMAP "
     "and HDBSCAN, over 33,206 CORD-19 abstracts to find under-explored COVID-19 topics. It "
     "scales and saves effort, but it reads abstracts only and says nothing about why a topic "
     "is sparse; the authors themselves ask for full-paper analysis. [[n:qi2020]] find knowledge "
     "gaps inside organisations with a Word2Vec topic network, TF-IDF and eigenvector "
     "centrality, and beat a SWOT analysis. It works on keywords and has no graph."))

add(("h2", "Semantic Similarity"))
add(("p",
     '[[n:chandrasekaran2021]] survey semantic similarity from its knowledge-based beginnings, through corpus-based methods, to neural and hybrid ones. For scientific documents, Sentence-BERT ([[reimers2019]]) made dense sentence embeddings cheap, SciBERT ([[beltagy2019]]) pretrained on scientific text, and SPECTER ([[cohan2020]]) trained document vectors with the citation graph. Each gives a document a single vector. That suits retrieval, but one number cannot say whether two papers are close in aim, in method or in data, which is why our score keeps the aspects separate.'))
add(("p",
     "Citation analysis adds a fifth signal. [[n:kessler1963]] defined bibliographic coupling, "
     "where two papers are related because they cite the same earlier work, and [[n:small1973]] "
     "defined co-citation, where they are related because others cite them together. Both are "
     "decades older than neural methods and still catch something embeddings miss: two papers "
     "can cite the same sources and share almost no vocabulary."))

add(("h2", "Comparison and Positioning"))
add(("p",
     "{tab:survey} sets the reviewed works against the capabilities this project needs. A dash "
     "means the work does not address that capability as a main contribution."))
add(("tab", {
    "key": "survey",
    "caption": "Comparison of the reviewed works. Capabilities the project needs, against what each work addresses.",
    "size": 9.5,
    "headers": ["Work", "Focus", "Graph", "Cross-paper", "Contradiction", "Gaps", "Evidence"],
    "widths": [2.4, 2.3, 1.1, 1.4, 1.9, 0.9, 1.3],
    "rows": [
        ["Zhong et al. (2023)", "KG construction survey", "Yes", "Open problem", "–", "–", "–"],
        ["Ji et al. (2022)", "KG representation survey", "Yes", "–", "–", "–", "–"],
        ["Di Iorio et al. (2017)", "Scholarly linked data", "Yes", "Citations", "–", "–", "Partial"],
        ["Milosevic & Thielemann (2023)", "Biomedical relation extraction", "Yes", "–", "–", "–", "–"],
        ["Xu et al. (2024)", "Generative IE survey", "–", "–", "–", "–", "–"],
        ["Sciannameo et al. (2024)", "PDF extraction with GPT", "–", "–", "–", "–", "–"],
        ["Baldini Soares et al. (2019)", "Relation representations", "–", "–", "–", "–", "–"],
        ["Wang et al. (2022)", "Cross-document RE", "–", "Yes", "–", "–", "–"],
        ["Yao et al. (2010)", "Cross-document RE", "–", "Yes", "–", "–", "–"],
        ["Fang et al. (2025)", "Claim verification", "–", "Partial", "Stance", "–", "Yes"],
        ["Makhervaks et al. (2023)", "Clinical contradictions", "–", "Yes", "Yes", "–", "–"],
        ["Abd-alrazaq et al. (2024)", "Gap discovery, topics", "–", "–", "–", "Yes", "–"],
        ["Qi et al. (2020)", "Knowledge gaps", "–", "–", "–", "Yes", "–"],
        ["Chandrasekaran & Mago (2021)", "Similarity survey", "–", "Partial", "–", "–", "–"],
        ["**This project**", "End-to-end analyzer", "**Yes**", "**Yes**", "**Yes**", "**Yes**", "**Yes**"],
    ],
}))
add(("p",
     "Three things stand out. No single work goes from raw documents to a graph, contradictions "
     "and gaps; each handles one stage. The two closest to contradiction and gap discovery are "
     "tied to a clinical ontology and to abstract-level topic models. And hardly any of them "
     "attach a sentence and a page to their output, even though a reader cannot act on a "
     "finding without being able to check it."))
add(("p",
     "Our base paper is the Semantic Lancet study of [[diiorio2017]]. {tab:extensions} lists the "
     "eight ways this project goes beyond it."))
add(("tab", {
    "key": "extensions",
    "caption": "Extensions to the base paper implemented in this project.",
    "headers": ["#", "Base-paper capability", "Extension implemented"],
    "widths": [0.4, 2.2, 4.4],
    "rows": [
        ["1", "Semantic enhancement of papers", "Structured extraction of objectives, methods, datasets, results and gaps"],
        ["2", "Semantic relationships", "Weighted five-dimension relationship score"],
        ["3", "None", "Document categories: experimental, survey or methodological"],
        ["4", "Citation network", "Bridge concepts shared across documents for multi-hop reasoning"],
        ["5", "Provenance in RDF", "Evidence on every edge: document, section, page, sentence"],
        ["6", "Inconsistency detection", "Numeric and natural-language-inference contradiction detection"],
        ["7", "Semantic search", "Evidence-grounded explanation of each finding"],
        ["8", "None", "Novelty-ranked research gap discovery"],
    ],
}))

# ======================================================================
# CHAPTER 3
# ======================================================================
add(("h1", "Requirements and Analysis"))

add(("h2", "Users and Use Cases"))
add(("p",
     "There are two kinds of user. A researcher supplies papers and reads the results. An "
     "operator deploys the service and keeps an eye on it. On a laptop they are the same person; "
     "on a hosted install the researcher uses the web interface and the operator uses the "
     "backend status page."))
add(("tab", {
    "key": "usecases",
    "caption": "Principal use cases.",
    "headers": ["Use case", "Actor", "Outcome"],
    "widths": [2.2, 1.2, 4.2],
    "rows": [
        ["Load a corpus", "Researcher", "PDFs uploaded, or a prepared set fetched, into the corpus directory"],
        ["Run the analysis", "Researcher", "Pipeline runs with live progress; results are held for browsing"],
        ["Explore relationships", "Researcher", "Score matrix, ranked pairs and the five-part breakdown for any pair"],
        ["Inspect a finding", "Researcher", "The original sentence, section and page behind any node, contradiction or gap"],
        ["Adjust the weights", "Researcher", "Five weights changed (sum to one) and applied on the next run"],
        ["Export a report", "Researcher", "JSON, Markdown or PDF report downloaded"],
        ["Check service health", "Operator", "Runtime, configuration, storage and endpoint counts on the backend page"],
        ["Deploy the service", "Operator", "API running on a host, interface served separately"],
    ],
}))

add(("h2", "Functional Requirements"))
add(("p",
     "We wrote eighteen numbered requirements before starting, each with acceptance criteria. "
     "{tab:fr} shows them with their status today. Sixteen are done, one is partly done and one "
     "has not been started. The last two come up again under future work."))
add(("tab", {
    "key": "fr",
    "caption": "Functional requirements and their status.",
    "size": 10,
    "headers": ["ID", "Requirement", "Status"],
    "widths": [0.5, 5.2, 1.3],
    "rows": [
        ["R1", "Ingest PDFs and split them into sections; log and skip unreadable files", "Complete"],
        ["R2", "Classify each paper as experimental, survey or methodological, with a confidence", "Complete"],
        ["R3", "Extract typed entities with source sentence, section and page", "Complete"],
        ["R4", "Extract typed relations between entities and documents", "Complete"],
        ["R5", "Build and store a knowledge graph, with a lossless round trip", "Complete"],
        ["R6", "Score every document pair on five weighted dimensions", "Complete"],
        ["R7", "Detect contradictions and confirm them under explicit conditions", "Complete"],
        ["R8", "Find research gaps from weak and missing connections", "Complete"],
        ["R9", "Build a pruned evidence graph for each finding", "Partial"],
        ["R10", "Generate explanations based only on retrieved evidence (optional language-model backend)", "Complete, optional"],
        ["R11", "Update the graph incrementally when papers are added", "Not started"],
        ["R12", "Report progress to the command line and the interface", "Complete"],
        ["R13", "Make every finding traceable to its source", "Complete"],
        ["R14", "Validate and expose configuration", "Complete"],
        ["R15", "Reduce hallucination in the optional language-model backend", "Complete, optional"],
        ["R16", "Compute embeddings, with a fallback when no model is available", "Complete"],
        ["R17", "Export results as JSON, Markdown and PDF", "Complete"],
        ["R18", "Save and load the graph so that load(save(g)) equals g", "Complete"],
    ],
}))

add(("h2", "Non-Functional Requirements"))
add(("p", "Five things mattered beyond the features."))
add(("bul", [
    "Every number or finding must come with a way to see where it came from.",
    "A complete run must need neither a network nor an API key. Researchers often work on "
    "unpublished manuscripts that must not be sent to an outside service.",
    "A missing model or a failed stage must make the output worse in a visible way, never "
    "quietly. A paper that cannot be segmented is still analysed, and an unavailable embedding "
    "model is replaced by a plain fallback.",
    "The deployed service must fit a free hosting tier. The core install is about 174 MB, while "
    "the transformer extras need roughly 2.5 GB and are optional.",
    "Each stage must be testable by itself, and the whole pipeline must be testable on generated PDFs.",
]))

add(("h2", "System Requirements"))
add(("tab", {
    "key": "sysreq",
    "caption": "Hardware and software requirements.",
    "headers": ["Item", "Minimum (core install)", "Recommended (with transformer models)"],
    "widths": [1.6, 2.6, 2.8],
    "rows": [
        ["Processor", "Dual-core CPU", "Quad-core CPU (no GPU required)"],
        ["Memory", "2 GB", "8 GB"],
        ["Disk", "1 GB free", "5 GB free (models and cache)"],
        ["Operating system", "Windows, Linux or macOS", "Same"],
        ["Python", "3.10 or later", "3.11"],
        ["Browser", "Any current browser", "Same"],
        ["Network", "Not needed to run", "Needed once to download models and to fetch arXiv papers"],
    ],
}))

add(("h2", "Technology Selection"))
add(("p",
     "We picked each tool in {tab:tech} to meet a requirement above. Two choices need a word. "
     "PyMuPDF reads the input PDFs and also writes the output report, so one dependency does "
     "two jobs. And the heavy transformer libraries are optional and loaded only when needed, "
     "so the service starts and runs on a small host."))
add(("tab", {
    "key": "tech",
    "caption": "Technology stack and the reason for each choice.",
    "headers": ["Layer", "Technology", "Reason"],
    "widths": [1.3, 2.0, 4.0],
    "rows": [
        ["PDF handling", "PyMuPDF", "Gives font size and position for every text span, which segmentation needs; also writes the PDF report"],
        ["Data model", "Pydantic", "Validated, serialisable models; range checks catch invalid scores"],
        ["Numerics", "NumPy [[harris2020]]", "Vector maths for similarity; seeded random projection for the fallback embedding"],
        ["Embeddings", "Sentence-Transformers (MiniLM) or TF-IDF fallback", "Good quality when available; deterministic and light when not"],
        ["Inference", "Transformers, DeBERTa cross-encoder", "Pretrained natural language inference on claim pairs"],
        ["Graph", "NetworkX", "Directed multigraph with per-edge attributes; JSON round trip"],
        ["API", "FastAPI, Uvicorn", "Typed REST endpoints and WebSocket progress in one small framework"],
        ["Interface", "HTML, CSS, JavaScript, Cytoscape.js", "No build step; deployable on any static host"],
        ["CLI", "Typer, Rich", "Validated command line and a live progress panel"],
        ["Hosting", "Render (API), Vercel (interface)", "Free tiers; the two halves deploy independently"],
    ],
}))

add(("h2", "Feasibility"))
add(("p",
     "Technically, almost everything already existed as a maintained library or turned out to be "
     "a small amount of rule-based code. The one real risk was splitting arbitrary PDFs into "
     "sections, so we tackled that first (Chapter 4). Financially, nothing needs paying for: "
     "hosting uses free tiers, the models are open, and the optional language-model backend is "
     "the only thing that can cost money, and only if someone supplies a key. In practice, the "
     "system installs with one command, runs as one process, and produces a web page and three "
     "report files, so it fits into a researcher's normal workflow."))
add(("p",
     "We expected three things to go wrong: weak extraction, running out of memory during "
     "inference, and the limits of free hosting. Extraction was tuned for precision and is "
     "tested in Chapter 7. Inference runs in small, capped batches. The hosting limits decided "
     "which packages are core and which are optional."))
