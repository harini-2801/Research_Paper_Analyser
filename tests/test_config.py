"""Tests for configuration loading and validation."""

from pathlib import Path

import pytest

from rpra.config import load_settings


def test_load_default_config(tmp_path):
    """Valid config.yaml loads without errors."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
llm:
  provider: openai
  model: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
  temperature: 0.0
  max_retries: 3
embedding:
  model: sentence-transformers/all-MiniLM-L6-v2
  device: cpu
  batch_size: 32
nli:
  model: cross-encoder/nli-deberta-v3-small
  contradiction_confidence_threshold: 0.60
  methodology_similarity_threshold: 0.30
relationship_scoring:
  weights:
    objective: 0.25
    methodology: 0.25
    dataset: 0.20
    results_metrics: 0.20
    citation: 0.10
gap_discovery:
  weak_connection_threshold: 0.20
  novelty_score_min: 0.0
  novelty_score_max: 1.0
storage:
  corpus_input_path: ./data/papers
  output_path: ./output
  graph_path: ./output/knowledge_graph.json
  embeddings_path: ./output/embeddings.npz
  log_path: ./output/pipeline.log
pipeline:
  max_documents: 10000
  incremental: true
  segment_types:
    - abstract
    - introduction
    - methodology
    - results
    - conclusion
    - references
"""
    )
    settings = load_settings(cfg)
    assert settings.llm.model == "gpt-4o-mini"
    assert settings.relationship_scoring.weights.objective == 0.25


def test_missing_required_key(tmp_path):
    """Missing a required top-level key raises KeyError."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text("llm:\n  model: gpt-4o-mini\n")  # missing many keys
    with pytest.raises(KeyError, match="Missing required configuration key"):
        load_settings(cfg)


def test_weights_must_sum_to_one(tmp_path):
    """Weights that do not sum to 1.0 raise ValueError."""
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
llm:
  provider: openai
  model: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
  temperature: 0.0
  max_retries: 3
embedding:
  model: sentence-transformers/all-MiniLM-L6-v2
  device: cpu
  batch_size: 32
nli:
  model: cross-encoder/nli-deberta-v3-small
  contradiction_confidence_threshold: 0.60
  methodology_similarity_threshold: 0.30
relationship_scoring:
  weights:
    objective: 0.50
    methodology: 0.50
    dataset: 0.50
    results_metrics: 0.50
    citation: 0.50
gap_discovery:
  weak_connection_threshold: 0.20
  novelty_score_min: 0.0
  novelty_score_max: 1.0
storage:
  corpus_input_path: ./data/papers
  output_path: ./output
  graph_path: ./output/kg.json
  embeddings_path: ./output/emb.npz
  log_path: ./output/log.jsonl
pipeline:
  max_documents: 100
  incremental: true
  segment_types: [abstract]
"""
    )
    with pytest.raises(Exception, match="sum to 1.0"):
        load_settings(cfg)


def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_settings(Path("nonexistent_config.yaml"))
