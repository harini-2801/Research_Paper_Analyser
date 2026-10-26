"""
Front-matter content for the project report: names, dates, abstract,
acknowledgement and the list of acronyms.

Anything that is a fact about the student, guide or dates lives here so it can
be corrected in one place.
"""

from __future__ import annotations

TITLE = (
    "Research Paper Relationship Analyzer: An Explainable Knowledge Graph Pipeline for "
    "Relationship Scoring, Contradiction Detection and Research Gap Discovery"
)

NAME = "Harini Sriram"
REG_NO = "23BDS1124"
GUIDE = "Dr. Poornima S"
GUIDE_DESIGNATION = "Faculty"
HOD = "Vegin Raja Sarobin"
PROGRAM = "Computer Science and Engineering (Specialization in Data Science)"
PROGRAM_SHORT = "Computer Science and Engineering (Data Science)"

# Every team member appears on the cover and title page; the declaration,
# certificate and acknowledgement carry only the submitting student.
TEAM = [
    ("Anjaneya Sahu", "23BCE1448"),
    ("Harini Sriram", "23BDS1124"),
    ("Khushi Kumari", "23BAI1324"),
]

DATE_NUM = "16/10/2026"
MONTH_YEAR = "October, 2026"

KEYWORDS = (
    "knowledge graph, scientific literature, contradiction detection, research gap discovery, "
    "document similarity, explainable analysis"
)

ABSTRACT = [
    (
        "Anyone who starts reading in a new research area soon finds that the papers answer the "
        "wrong question. Each one reports its own result, but what a reader needs sits between "
        "the papers: which of them tackle the same problem, where two of them report different "
        "numbers for what looks like the same experiment, and which combinations of ideas nobody "
        "in the collection has tried. This project builds a system that finds those cross-paper "
        "facts in a folder of PDFs and shows the reader exactly where each one came from."
    ),
    (
        "The system splits every paper into sections using relative font size, extracts typed "
        "entities with rules, and scores each pair "
        "of papers on five separate dimensions (objective, methodology, dataset, results and "
        "citations) whose weights add up to one. The entities form a knowledge graph. "
        "Contradictions are looked for with a numeric detector and a natural language inference "
        "model, and are confirmed only when the two papers measure the same thing under "
        "comparable methods. Research gaps are reported as stated, weakly connected or missing "
        "combinations, and cut down to the few that matter. Every finding carries the document, "
        "section, page and original sentence behind it. The system runs behind a FastAPI "
        "back end with a browser interface, deployed with the interface on Vercel and the API "
        "on Render."
    ),
    (
        "We tested it on thirty arXiv papers arranged in four topical clusters and compared it "
        "with seven baselines. Segmentation worked for all thirty papers and found 215 of 240 "
        "expected sections. The relationship score ranked related papers far above chance (AUC "
        "0.86 against 0.50; MAP 0.68 against 0.31) and above each of its own parts, but it did not "
        "beat plain full-text TF-IDF (AUC 0.87; MAP 0.78), so its value lies in being explainable "
        "rather than more accurate. The numeric contradiction detector found both contradictions "
        "planted in a six-paper corpus with no false positive and confirmed nothing on the real "
        "papers; adding a natural language inference model cost precision. Community analysis of "
        "the paper network found a coarse split into image-based and language-based papers. A "
        "suite of 236 automated tests covers the pipeline end to end, and a full analysis of "
        "thirty papers takes about half a minute on a laptop CPU."
    ),
]


def acknowledgement() -> list[str]:
    return [
        f"I would like to thank my guide, {GUIDE}, {GUIDE_DESIGNATION}, School of Computer "
        "Science and Engineering, Vellore Institute of Technology, Chennai, for her guidance, "
        "encouragement and patience throughout this project, and for all I learned from her "
        "about natural language processing and knowledge graphs.",

        "I am grateful to our Chancellor, Dr. G. Viswanathan, the Vice Presidents, the "
        "Vice-Chancellor, Dr. V. S. Kanchana Bhaaskaran, and the Dean of the School of Computer "
        "Science and Engineering, Dr. Viswanathan V, for an excellent environment to study "
        "and work in.",

        f"My thanks also go to the Head of the Department, {HOD}, and the project coordinators "
        "for their support, to the faculty and staff of VIT Chennai, to my parents and friends, "
        "and to my project partners, Anjaneya Sahu and Khushi Kumari, with whom this system "
        "was designed and built.",
    ]


ACRONYMS = [
    ("API", "Application Programming Interface"),
    ("APA", "American Psychological Association (citation style)"),
    ("BERT", "Bidirectional Encoder Representations from Transformers"),
    ("CORS", "Cross-Origin Resource Sharing"),
    ("CPU", "Central Processing Unit"),
    ("CSS", "Cascading Style Sheets"),
    ("DeBERTa", "Decoding-enhanced BERT with Disentangled Attention"),
    ("HTML", "HyperText Markup Language"),
    ("HTTP", "HyperText Transfer Protocol"),
    ("IE", "Information Extraction"),
    ("JSON", "JavaScript Object Notation"),
    ("KG", "Knowledge Graph"),
    ("LLM", "Large Language Model"),
    ("MNLI", "Multi-Genre Natural Language Inference"),
    ("NER", "Named Entity Recognition"),
    ("NLI", "Natural Language Inference"),
    ("NLP", "Natural Language Processing"),
    ("PDF", "Portable Document Format"),
    ("RAG", "Retrieval-Augmented Generation"),
    ("REST", "Representational State Transfer"),
    ("TF-IDF", "Term Frequency, Inverse Document Frequency"),
    ("UI", "User Interface"),
    ("WebSocket", "Full-duplex communication protocol over a single TCP connection"),
]
