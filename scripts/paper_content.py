"""
The conference paper's text, held apart from the two templates that render it.

The same manuscript is submitted to two venues with incompatible house styles
(AIP Conference Proceedings numbers nothing and centres its headings in capitals;
Springer LNCS numbers everything and puts table captions above the table). Keeping
the prose here, and the formatting in the renderers, means a correction to the text
lands in both files instead of in whichever one was edited last.

Blocks are ``(kind, payload)``. The renderers map *kind* onto whatever paragraph
style the template of the moment happens to call it.
"""

from __future__ import annotations

TITLE = (
    "A Multi-Dimensional Knowledge Graph Framework for Relationship Analysis, "
    "Contradiction Detection and Research Gap Discovery in Scientific Literature"
)

SHORT_TITLE = "A Knowledge Graph Framework for Scientific Literature Analysis"

AUTHORS = [
    {"name": "Harini Sriram", "affil": 1, "email": "a", "orcid": ""},
    {"name": "Anjaneya Sahu", "affil": 2, "email": "b", "orcid": ""},
    {"name": "Khushi Kumari", "affil": 3, "email": "c", "orcid": ""},
]

# All three authors are at the same institution but in different departments,
# so the affiliation cannot be collapsed to one entry; each is numbered.
AFFILIATIONS = [
    "Department of Computer Science and Engineering (Data Science), "
    "Vellore Institute of Technology, Chennai, 600127, India.",
    "Department of Computer Science and Engineering (Core), "
    "Vellore Institute of Technology, Chennai, 600127, India.",
    "Department of Computer Science and Engineering "
    "(Artificial Intelligence and Machine Learning), "
    "Vellore Institute of Technology, Chennai, 600127, India.",
]

EMAILS = [
    ("a", "Corresponding author: harini.sriram2023@vitstudent.ac.in"),
    ("b", "anjaneya.sahu2023@vitstudent.ac.in"),
    ("c", "khushi.kumari2023@vitstudent.ac.in"),
]

KEYWORDS = (
    "Knowledge graphs, Scientific literature mining, Information extraction, "
    "Contradiction detection, Research gap discovery, Document similarity"
)

from paper_body import ABSTRACT, BODY, TABLE3, TABLE4  # noqa: E402

TABLE1 = {
    "caption": "The five scoring dimensions, their weights, and the measure used for each.",
    "headers": ["Dimension", "Wt.", "Measure", "Compares"],
    "rows": [
        ["Objective", "0.25", "Cosine", "Mean embedding of objective statements"],
        ["Methodology", "0.25", "Cosine", "Mean embedding of method entities"],
        ["Dataset", "0.20", "Jaccard", "Sets of dataset names"],
        ["Results and metrics", "0.20", "Cosine", "Reported results and evaluation metrics"],
        ["Citation", "0.10", "Jaccard", "Reference lists (bibliographic coupling)"],
    ],
    "widths": [0.22, 0.10, 0.13, 0.55],
}

TABLES = {"table1": TABLE1, "table3": TABLE3, "table4": TABLE4}

FIGURES = {
    "pipeline": {
        "file": "paper/figures/fig1_pipeline.png", "max_in": 5.5,
        "caption": "The eleven pipeline stages. Ordering is forced by data "
                   "dependency: three of the five scoring dimensions are cosine "
                   "similarities over entity vectors, so embedding must precede "
                   "scoring.",
    },
    "workspace": {
        "file": "paper/figures/fig2_workspace.png", "width_in": 5.2,
        "caption": "The analysis workspace. Above, the headline counts, the "
                   "knowledge graph with one paper selected and the inspector. "
                   "Below, the composite score for every pair of papers.",
    },
    "heatmap": {
        "file": "paper/figures/fig2_heatmap.png", "max_in": 3.0,
        "caption": "Composite relationship score for all 435 document pairs, "
                   "ordered by topical cluster. The pale lower-left region is "
                   "cluster A against cluster D, the negative control.",
    },
    "communities": {
        "file": "paper/figures/graph_communities.png", "max_in": 3.6,
        "caption": "The paper network at a score threshold of 0.50. Colour is the "
                   "community found by Louvain on the full weighted network; shape "
                   "is the assigned cluster.",
    },
}


REFERENCES = [
    "Reimers, N., Gurevych, I.: Sentence-BERT: Sentence Embeddings using Siamese "
    "BERT-Networks. In: Proceedings of EMNLP-IJCNLP, pp. 3982–3992 (2019).",

    "Beltagy, I., Lo, K., Cohan, A.: SciBERT: A Pretrained Language Model for "
    "Scientific Text. In: Proceedings of EMNLP-IJCNLP, pp. 3615–3620 (2019).",

    "Cohan, A., Feldman, S., Beltagy, I., Downey, D., Weld, D.S.: SPECTER: "
    "Document-level Representation Learning using Citation-informed Transformers. "
    "In: Proceedings of ACL, pp. 2270–2282 (2020).",

    "Luan, Y., He, L., Ostendorf, M., Hajishirzi, H.: Multi-Task Identification of "
    "Entities, Relations, and Coreference for Scientific Knowledge Graph "
    "Construction. In: Proceedings of EMNLP, pp. 3219–3232 (2018).",

    "Yao, Y., Ye, D., Li, P., Han, X., Lin, Y., Liu, Z., Sun, M.: DocRED: A "
    "Large-Scale Document-Level Relation Extraction Dataset. In: Proceedings of ACL, "
    "pp. 764–777 (2019).",

    "Thorne, J., Vlachos, A., Christodoulopoulos, C., Mittal, A.: FEVER: a "
    "Large-scale Dataset for Fact Extraction and VERification. In: Proceedings of "
    "NAACL-HLT, pp. 809–819 (2018).",

    "Wadden, D., Lin, S., Lo, K., Wang, L.L., van Zuylen, M., Cohan, A., Hajishirzi, "
    "H.: Fact or Fiction: Verifying Scientific Claims. In: Proceedings of EMNLP, "
    "pp. 7534–7550 (2020).",

    "Williams, A., Nangia, N., Bowman, S.: A Broad-Coverage Challenge Corpus for "
    "Sentence Understanding through Inference. In: Proceedings of NAACL-HLT, "
    "pp. 1112–1122 (2018).",

    "He, P., Liu, X., Gao, J., Chen, W.: DeBERTa: Decoding-enhanced BERT with "
    "Disentangled Attention. In: Proceedings of ICLR (2021).",

    "Kessler, M.M.: Bibliographic coupling between scientific papers. American "
    "Documentation 14(1), 10–25 (1963).",

    "Small, H.: Co-citation in the scientific literature: A new measure of the "
    "relationship between two documents. Journal of the American Society for "
    "Information Science 24(4), 265–269 (1973).",

    "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A.N., "
    "Kaiser, Ł., Polosukhin, I.: Attention Is All You Need. In: Advances in Neural "
    "Information Processing Systems 30, pp. 5998–6008 (2017).",

    "Devlin, J., Chang, M.-W., Lee, K., Toutanova, K.: BERT: Pre-training of Deep "
    "Bidirectional Transformers for Language Understanding. In: Proceedings of "
    "NAACL-HLT, pp. 4171–4186 (2019).",

    "He, K., Zhang, X., Ren, S., Sun, J.: Deep Residual Learning for Image "
    "Recognition. In: Proceedings of CVPR, pp. 770–778 (2016).",

    "He, K., Fan, H., Wu, Y., Xie, S., Girshick, R.: Momentum Contrast for "
    "Unsupervised Visual Representation Learning. In: Proceedings of CVPR, "
    "pp. 9729–9738 (2020).",

    "Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., "
    "Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., Kiela, D.: "
    "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. In: Advances "
    "in Neural Information Processing Systems 33, pp. 9459–9474 (2020).",

    "Ji, S., Pan, S., Cambria, E., Marttinen, P., Yu, P.S.: A Survey on Knowledge "
    "Graphs: Representation, Acquisition, and Applications. IEEE Transactions on "
    "Neural Networks and Learning Systems 33(2), 494–514 (2022).",

    "Hagberg, A.A., Schult, D.A., Swart, P.J.: Exploring Network Structure, "
    "Dynamics, and Function using NetworkX. In: Proceedings of the 7th Python in "
    "Science Conference, pp. 11–15 (2008).",

    "Salton, G., Buckley, C.: Term-weighting approaches in automatic text retrieval. "
    "Information Processing & Management 24(5), 513–523 (1988).",

    "Blondel, V.D., Guillaume, J.-L., Lambiotte, R., Lefebvre, E.: Fast unfolding of "
    "communities in large networks. Journal of Statistical Mechanics: Theory and "
    "Experiment 2008(10), P10008 (2008).",
]


# The same twenty works in the format the AIP template prescribes: initials first,
# "and" before the last author, titles in quotation marks for papers in proceedings,
# and no title for a journal article. Numbering is supplied by the Reference style.
REFERENCES_AIP = [
    "N. Reimers and I. Gurevych, \u201cSentence-BERT: Sentence Embeddings using Siamese "
    "BERT-Networks,\u201d in Proceedings of EMNLP-IJCNLP (2019), pp. 3982\u20133992.",

    "I. Beltagy, K. Lo, and A. Cohan, \u201cSciBERT: A Pretrained Language Model for "
    "Scientific Text,\u201d in Proceedings of EMNLP-IJCNLP (2019), pp. 3615\u20133620.",

    "A. Cohan, S. Feldman, I. Beltagy, D. Downey, and D. S. Weld, \u201cSPECTER: "
    "Document-level Representation Learning using Citation-informed Transformers,\u201d in "
    "Proceedings of ACL (2020), pp. 2270\u20132282.",

    "Y. Luan, L. He, M. Ostendorf, and H. Hajishirzi, \u201cMulti-Task Identification of "
    "Entities, Relations, and Coreference for Scientific Knowledge Graph Construction,\u201d "
    "in Proceedings of EMNLP (2018), pp. 3219\u20133232.",

    "Y. Yao, D. Ye, P. Li, X. Han, Y. Lin, Z. Liu, and M. Sun, \u201cDocRED: A Large-Scale "
    "Document-Level Relation Extraction Dataset,\u201d in Proceedings of ACL (2019), "
    "pp. 764\u2013777.",

    "J. Thorne, A. Vlachos, C. Christodoulopoulos, and A. Mittal, \u201cFEVER: a Large-scale "
    "Dataset for Fact Extraction and VERification,\u201d in Proceedings of NAACL-HLT (2018), "
    "pp. 809\u2013819.",

    "D. Wadden, S. Lin, K. Lo, L. L. Wang, M. van Zuylen, A. Cohan, and H. Hajishirzi, "
    "\u201cFact or Fiction: Verifying Scientific Claims,\u201d in Proceedings of EMNLP (2020), "
    "pp. 7534\u20137550.",

    "A. Williams, N. Nangia, and S. Bowman, \u201cA Broad-Coverage Challenge Corpus for "
    "Sentence Understanding through Inference,\u201d in Proceedings of NAACL-HLT (2018), "
    "pp. 1112\u20131122.",

    "P. He, X. Liu, J. Gao, and W. Chen, \u201cDeBERTa: Decoding-enhanced BERT with "
    "Disentangled Attention,\u201d in Proceedings of ICLR (2021).",

    "M. M. Kessler, American Documentation 14, 10\u201325 (1963).",

    "H. Small, J. Am. Soc. Inf. Sci. 24, 265\u2013269 (1973).",

    "A. Vaswani et al., \u201cAttention Is All You Need,\u201d in Advances in Neural "
    "Information Processing Systems 30 (2017), pp. 5998\u20136008.",

    "J. Devlin, M.-W. Chang, K. Lee, and K. Toutanova, \u201cBERT: Pre-training of Deep "
    "Bidirectional Transformers for Language Understanding,\u201d in Proceedings of "
    "NAACL-HLT (2019), pp. 4171\u20134186.",

    "K. He, X. Zhang, S. Ren, and J. Sun, \u201cDeep Residual Learning for Image "
    "Recognition,\u201d in Proceedings of CVPR (2016), pp. 770\u2013778.",

    "K. He, H. Fan, Y. Wu, S. Xie, and R. Girshick, \u201cMomentum Contrast for "
    "Unsupervised Visual Representation Learning,\u201d in Proceedings of CVPR (2020), "
    "pp. 9729\u20139738.",

    "P. Lewis et al., \u201cRetrieval-Augmented Generation for Knowledge-Intensive NLP "
    "Tasks,\u201d in Advances in Neural Information Processing Systems 33 (2020), "
    "pp. 9459\u20139474.",

    "S. Ji, S. Pan, E. Cambria, P. Marttinen, and P. S. Yu, IEEE Trans. Neural Netw. "
    "Learn. Syst. 33, 494\u2013514 (2022).",

    "A. A. Hagberg, D. A. Schult, and P. J. Swart, \u201cExploring Network Structure, "
    "Dynamics, and Function using NetworkX,\u201d in Proceedings of the 7th Python in "
    "Science Conference (2008), pp. 11\u201315.",

    "G. Salton and C. Buckley, Inf. Process. Manag. 24, 513\u2013523 (1988).",

    "V. D. Blondel, J.-L. Guillaume, R. Lambiotte, and E. Lefebvre, J. Stat. Mech. "
    "2008, P10008 (2008).",
]
assert len(REFERENCES_AIP) == len(REFERENCES), "AIP and LNCS reference lists must match"
