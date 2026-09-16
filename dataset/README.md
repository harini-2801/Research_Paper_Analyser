# Evaluation corpus - 30 arXiv papers

The corpus every number in this project's README is measured on. It lives here,
in the repository, because a benchmark nobody can obtain is not a benchmark:
"precision@10 of 90%" only means something if you can re-run it on the same
papers.

## Contents

- `papers/` - 30 PDFs, ~48 MB, named by slug (`resnet_2015.pdf`, `bert_2018.pdf`, ...)
- `corpus_manifest.json` - arXiv ID, title and cluster for each paper

## Why these thirty

A random sample cannot evaluate this system. Contradiction detection only fires
when two papers report the same metric on the same dataset, and relationship
scoring needs pairs that *should* rank high alongside pairs that *should* rank
low. So the corpus is four deliberate clusters:

| Cluster | Theme | n | What it tests |
|---|---|---|---|
| A | Convolutional image classification | 8 | Dense cross-citation; the same architectures reported with different baselines |
| B | Pretrained language models | 8 | Shared GLUE/SQuAD numbers - RoBERTa openly disputes BERT's |
| C | Vision transformers, self-supervised vision | 8 | Shares ImageNet with A but not the method, separating "same benchmark" from "same approach" |
| D | Retrieval, IE, knowledge graphs | 6 | The negative control - A-vs-D pairs should score near zero |

Pairs within a cluster should outrank pairs across clusters, and A-vs-D is the
floor. That is what makes precision@10 a meaningful measurement rather than a
number with nothing to fail against.

## Provenance and licensing

Every paper is a preprint fetched from arXiv by its public PDF endpoint; the
IDs are in `corpus_manifest.json`. Copyright remains with the respective
authors, and each paper is distributed under whichever licence its authors
chose on arXiv. They are included here for reproducible academic evaluation and
are not modified. To rebuild the folder from arXiv directly:

```bash
python scripts/fetch_eval_corpus.py dataset/papers
```

## How the application uses it

`rpra.arxiv_corpus` checks this directory before going to the network, so
"Load 30 (arXiv)" in the interface is a file copy rather than a two-minute
download - and works with no internet connection at all.
