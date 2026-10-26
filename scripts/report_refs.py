"""
Bibliography for the project report, in APA 7th edition.

Text in the report cites by key: ``[[wang2022]]`` renders as (Wang et al., 2022)
and ``[[n:wang2022]]`` as Wang et al. (2022). The reference list is built from
the keys actually cited, in alphabetical order, so the list and the text cannot
drift apart: an entry nobody cites does not appear, and a citation with no entry
stops the build.

Every entry below was checked against the publisher or the ACL Anthology page.
Where a detail could not be confirmed (page ranges mostly) it is left out
rather than guessed. Words wrapped in asterisks are rendered in italics.
"""

from __future__ import annotations

# key: (in-text author string, year, full APA reference)
REFS: dict[str, tuple[str, str, str]] = {
    "zhong2023": (
        "Zhong et al.", "2023",
        "Zhong, L., Wu, J., Li, Q., Peng, H., & Wu, X. (2023). A comprehensive survey on "
        "automatic knowledge graph construction. *ACM Computing Surveys, 56*. "
        "https://arxiv.org/abs/2302.05019",
    ),
    "ji2022": (
        "Ji et al.", "2022",
        "Ji, S., Pan, S., Cambria, E., Marttinen, P., & Yu, P. S. (2022). A survey on knowledge "
        "graphs: Representation, acquisition, and applications. *IEEE Transactions on Neural "
        "Networks and Learning Systems, 33*(2), 494–514. https://doi.org/10.1109/TNNLS.2021.3070843",
    ),
    "diiorio2017": (
        "Di Iorio et al.", "2017",
        "Di Iorio, A., Nuzzolese, A. G., Peroni, S., Poggi, F., Vitali, F., & Ciancarini, P. "
        "(2017). Analysing and discovering semantic relations in scholarly data. In *Digital "
        "Libraries and Archives (IRCDL 2017), Communications in Computer and Information Science, "
        "733* (pp. 3–19). Springer. https://doi.org/10.1007/978-3-319-68130-6_1",
    ),
    "milosevic2023": (
        "Milosevic & Thielemann", "2023",
        "Milosevic, N., & Thielemann, W. (2023). Comparison of biomedical relationship extraction "
        "methods and models for knowledge graph creation. *Journal of Web Semantics, 75*. "
        "https://arxiv.org/abs/2201.01647",
    ),
    "wang2022": (
        "Wang et al.", "2022",
        "Wang, F., Li, F., Fei, H., Li, J., Wu, S., Su, F., Shi, W., Ji, D., & Cai, B. (2022). "
        "Entity-centered cross-document relation extraction. In *Proceedings of the 2022 "
        "Conference on Empirical Methods in Natural Language Processing* (pp. 9871–9881). "
        "Association for Computational Linguistics. https://doi.org/10.18653/v1/2022.emnlp-main.671",
    ),
    "yao2010": (
        "Yao et al.", "2010",
        "Yao, L., Riedel, S., & McCallum, A. (2010). Collective cross-document relation extraction "
        "without labelled data. In *Proceedings of the 2010 Conference on Empirical Methods in "
        "Natural Language Processing*. Association for Computational Linguistics.",
    ),
    "xu2024": (
        "Xu et al.", "2024",
        "Xu, D., Chen, W., Peng, W., Zhang, C., Xu, T., Zhao, X., Wu, X., Zheng, Y., Wang, Y., & "
        "Chen, E. (2024). Large language models for generative information extraction: A survey. "
        "*Frontiers of Computer Science, 18*(6).",
    ),
    "sciannameo2024": (
        "Sciannameo et al.", "2024",
        "Sciannameo, V., Jahier Pagliari, D., Urru, S., Grimaldi, P., Ocagli, H., Ahsani-Nasab, S., "
        "Comoretto, R. I., Gregori, D., & Berchialla, P. (2024). Information extraction from "
        "medical case reports using OpenAI InstructGPT. *Computer Methods and Programs in "
        "Biomedicine*.",
    ),
    "baldini2019": (
        "Baldini Soares et al.", "2019",
        "Baldini Soares, L., FitzGerald, N., Ling, J., & Kwiatkowski, T. (2019). Matching the "
        "blanks: Distributional similarity for relation learning. In *Proceedings of the 57th "
        "Annual Meeting of the Association for Computational Linguistics* (pp. 2895–2905). "
        "Association for Computational Linguistics. https://doi.org/10.18653/v1/P19-1279",
    ),
    "fang2025": (
        "Fang et al.", "2025",
        "Fang, L., Fu, D., & Torvik, V. I. (2025). Automatic scientific claims verification with "
        "pruned evidence graph. *ICLR 2025 Workshop on Agentic AI*.",
    ),
    "makhervaks2023": (
        "Makhervaks et al.", "2023",
        "Makhervaks, D., Gillis, P., & Radinsky, K. (2023). Clinical contradiction detection. In "
        "*Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing* "
        "(pp. 1248–1263). Association for Computational Linguistics. "
        "https://doi.org/10.18653/v1/2023.emnlp-main.80",
    ),
    "abdalrazaq2024": (
        "Abd-alrazaq et al.", "2024",
        "Abd-alrazaq, A., et al. (2024). Machine learning–based approach for identifying research "
        "gaps: COVID-19 as a case study. *JMIR Formative Research, 8*.",
    ),
    "qi2020": (
        "Qi et al.", "2020",
        "Qi, L., An, X., Zhang, S., & Wang, X. (2020). Research on knowledge gap identification "
        "method in innovative organizations under the “Internet+” environment. *Information, "
        "11*(12), 572. https://doi.org/10.3390/info11120572",
    ),
    "chandrasekaran2021": (
        "Chandrasekaran & Mago", "2021",
        "Chandrasekaran, D., & Mago, V. (2021). Evolution of semantic similarity—A survey. *ACM "
        "Computing Surveys, 54*(2). https://doi.org/10.1145/3440755",
    ),
    "reimers2019": (
        "Reimers & Gurevych", "2019",
        "Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence embeddings using Siamese "
        "BERT-networks. In *Proceedings of EMNLP-IJCNLP 2019* (pp. 3982–3992). Association for "
        "Computational Linguistics. https://doi.org/10.18653/v1/D19-1410",
    ),
    "beltagy2019": (
        "Beltagy et al.", "2019",
        "Beltagy, I., Lo, K., & Cohan, A. (2019). SciBERT: A pretrained language model for "
        "scientific text. In *Proceedings of EMNLP-IJCNLP 2019* (pp. 3615–3620). Association for "
        "Computational Linguistics.",
    ),
    "cohan2020": (
        "Cohan et al.", "2020",
        "Cohan, A., Feldman, S., Beltagy, I., Downey, D., & Weld, D. S. (2020). SPECTER: "
        "Document-level representation learning using citation-informed transformers. In "
        "*Proceedings of the 58th Annual Meeting of the Association for Computational "
        "Linguistics* (pp. 2270–2282). Association for Computational Linguistics.",
    ),
    "luan2018": (
        "Luan et al.", "2018",
        "Luan, Y., He, L., Ostendorf, M., & Hajishirzi, H. (2018). Multi-task identification of "
        "entities, relations, and coreference for scientific knowledge graph construction. In "
        "*Proceedings of the 2018 Conference on Empirical Methods in Natural Language Processing* "
        "(pp. 3219–3232). Association for Computational Linguistics.",
    ),
    "yao2019": (
        "Yao et al.", "2019",
        "Yao, Y., Ye, D., Li, P., Han, X., Lin, Y., Liu, Z., & Sun, M. (2019). DocRED: A "
        "large-scale document-level relation extraction dataset. In *Proceedings of the 57th "
        "Annual Meeting of the Association for Computational Linguistics* (pp. 764–777). "
        "Association for Computational Linguistics.",
    ),
    "thorne2018": (
        "Thorne et al.", "2018",
        "Thorne, J., Vlachos, A., Christodoulopoulos, C., & Mittal, A. (2018). FEVER: A "
        "large-scale dataset for fact extraction and verification. In *Proceedings of NAACL-HLT "
        "2018* (pp. 809–819). Association for Computational Linguistics.",
    ),
    "wadden2020": (
        "Wadden et al.", "2020",
        "Wadden, D., Lin, S., Lo, K., Wang, L. L., van Zuylen, M., Cohan, A., & Hajishirzi, H. "
        "(2020). Fact or fiction: Verifying scientific claims. In *Proceedings of the 2020 "
        "Conference on Empirical Methods in Natural Language Processing* (pp. 7534–7550). "
        "Association for Computational Linguistics.",
    ),
    "williams2018": (
        "Williams et al.", "2018",
        "Williams, A., Nangia, N., & Bowman, S. (2018). A broad-coverage challenge corpus for "
        "sentence understanding through inference. In *Proceedings of NAACL-HLT 2018* "
        "(pp. 1112–1122). Association for Computational Linguistics.",
    ),
    "he2021": (
        "He et al.", "2021",
        "He, P., Liu, X., Gao, J., & Chen, W. (2021). DeBERTa: Decoding-enhanced BERT with "
        "disentangled attention. In *International Conference on Learning Representations*.",
    ),
    "kessler1963": (
        "Kessler", "1963",
        "Kessler, M. M. (1963). Bibliographic coupling between scientific papers. *American "
        "Documentation, 14*(1), 10–25.",
    ),
    "small1973": (
        "Small", "1973",
        "Small, H. (1973). Co-citation in the scientific literature: A new measure of the "
        "relationship between two documents. *Journal of the American Society for Information "
        "Science, 24*(4), 265–269.",
    ),
    "vaswani2017": (
        "Vaswani et al.", "2017",
        "Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, Ł., "
        "& Polosukhin, I. (2017). Attention is all you need. In *Advances in Neural Information "
        "Processing Systems 30* (pp. 5998–6008).",
    ),
    "devlin2019": (
        "Devlin et al.", "2019",
        "Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep "
        "bidirectional transformers for language understanding. In *Proceedings of NAACL-HLT "
        "2019* (pp. 4171–4186). Association for Computational Linguistics. "
        "https://doi.org/10.18653/v1/N19-1423",
    ),
    "he2016": (
        "He et al.", "2016",
        "He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep residual learning for image "
        "recognition. In *Proceedings of the IEEE Conference on Computer Vision and Pattern "
        "Recognition* (pp. 770–778). https://doi.org/10.1109/CVPR.2016.90",
    ),
    "he2020": (
        "He et al.", "2020",
        "He, K., Fan, H., Wu, Y., Xie, S., & Girshick, R. (2020). Momentum contrast for "
        "unsupervised visual representation learning. In *Proceedings of the IEEE/CVF Conference "
        "on Computer Vision and Pattern Recognition* (pp. 9729–9738).",
    ),
    "lewis2020": (
        "Lewis et al.", "2020",
        "Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., "
        "Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., & Kiela, D. (2020). Retrieval-augmented "
        "generation for knowledge-intensive NLP tasks. In *Advances in Neural Information "
        "Processing Systems 33* (pp. 9459–9474).",
    ),
    "hagberg2008": (
        "Hagberg et al.", "2008",
        "Hagberg, A. A., Schult, D. A., & Swart, P. J. (2008). Exploring network structure, "
        "dynamics, and function using NetworkX. In *Proceedings of the 7th Python in Science "
        "Conference* (pp. 11–15).",
    ),
    "franz2016": (
        "Franz et al.", "2016",
        "Franz, M., Lopes, C. T., Huck, G., Dong, Y., Sumer, O., & Bader, G. D. (2016). "
        "Cytoscape.js: A graph theory library for visualisation and analysis. *Bioinformatics, "
        "32*(2), 309–311. https://doi.org/10.1093/bioinformatics/btv557",
    ),
    "salton1988": (
        "Salton & Buckley", "1988",
        "Salton, G., & Buckley, C. (1988). Term-weighting approaches in automatic text retrieval. "
        "*Information Processing & Management, 24*(5), 513–523. "
        "https://doi.org/10.1016/0306-4573(88)90021-0",
    ),
    "jaccard1912": (
        "Jaccard", "1912",
        "Jaccard, P. (1912). The distribution of the flora in the alpine zone. *New Phytologist, "
        "11*(2), 37–50.",
    ),
    "johnson1984": (
        "Johnson & Lindenstrauss", "1984",
        "Johnson, W. B., & Lindenstrauss, J. (1984). Extensions of Lipschitz mappings into a "
        "Hilbert space. *Contemporary Mathematics, 26*, 189–206.",
    ),
    "harris2020": (
        "Harris et al.", "2020",
        "Harris, C. R., Millman, K. J., van der Walt, S. J., et al. (2020). Array programming with "
        "NumPy. *Nature, 585*, 357–362. https://doi.org/10.1038/s41586-020-2649-2",
    ),
    "wolf2020": (
        "Wolf et al.", "2020",
        "Wolf, T., Debut, L., Sanh, V., et al. (2020). Transformers: State-of-the-art natural "
        "language processing. In *Proceedings of the 2020 Conference on Empirical Methods in "
        "Natural Language Processing: System Demonstrations* (pp. 38–45). Association for "
        "Computational Linguistics. https://doi.org/10.18653/v1/2020.emnlp-demos.6",
    ),
}
