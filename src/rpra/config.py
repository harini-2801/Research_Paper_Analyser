"""
Config loader and validator.

Reads config.yaml, validates all keys and value ranges, and
exposes a single `Settings` object used throughout the pipeline.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------
    

class LLMConfig(BaseModel):
    provider: Literal["openai", "ollama", "anthropic"] = "openai"
    model: str = "gpt-4o-mini"
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    max_retries: int = Field(3, ge=1, le=10)


class EmbeddingConfig(BaseModel):
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    device: Literal["cpu", "cuda", "mps"] = "cpu"
    batch_size: int = Field(32, ge=1)


class NLIConfig(BaseModel):
    model: str = "cross-encoder/nli-deberta-v3-small"
    contradiction_confidence_threshold: float = Field(0.60, ge=0.0, le=1.0)
    methodology_similarity_threshold: float = Field(0.30, ge=0.0, le=1.0)


class RelationshipWeights(BaseModel):
    objective: float = Field(0.25, ge=0.0, le=1.0)
    methodology: float = Field(0.25, ge=0.0, le=1.0)
    dataset: float = Field(0.20, ge=0.0, le=1.0)
    results_metrics: float = Field(0.20, ge=0.0, le=1.0)
    citation: float = Field(0.10, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "RelationshipWeights":
        total = (
            self.objective
            + self.methodology
            + self.dataset
            + self.results_metrics
            + self.citation
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Relationship score weights must sum to 1.0, got {total:.6f}. "
                "Adjust the weights in config.yaml."
            )
        return self


class RelationshipScoringConfig(BaseModel):
    weights: RelationshipWeights = Field(default_factory=RelationshipWeights)


class GapDiscoveryConfig(BaseModel):
    weak_connection_threshold: float = Field(0.20, ge=0.0, le=1.0)
    novelty_score_min: float = Field(0.0, ge=0.0)
    novelty_score_max: float = Field(1.0, le=1.0)

    @model_validator(mode="after")
    def min_less_than_max(self) -> "GapDiscoveryConfig":
        if self.novelty_score_min >= self.novelty_score_max:
            raise ValueError(
                "gap_discovery.novelty_score_min must be less than novelty_score_max."
            )
        return self


class StorageConfig(BaseModel):
    corpus_input_path: str = "./data/papers"
    output_path: str = "./output"
    graph_path: str = "./output/knowledge_graph.json"
    embeddings_path: str = "./output/embeddings.npz"
    log_path: str = "./output/pipeline.log"


class PipelineConfig(BaseModel):
    max_documents: int = Field(10000, ge=1)
    incremental: bool = True
    segment_types: list[str] = Field(
        default_factory=lambda: [
            "abstract",
            "introduction",
            "related_work",
            "methodology",
            "experiments",
            "results",
            "conclusion",
            "references",
        ]
    )


# ---------------------------------------------------------------------------
# Root settings
# ---------------------------------------------------------------------------


class Settings(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    nli: NLIConfig = Field(default_factory=NLIConfig)
    relationship_scoring: RelationshipScoringConfig = Field(
        default_factory=RelationshipScoringConfig
    )
    gap_discovery: GapDiscoveryConfig = Field(default_factory=GapDiscoveryConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    # resolved API key (populated after loading, never serialised)
    _api_key: str | None = None

    def resolve_api_key(self) -> str | None:
        """Read the LLM API key from the environment variable specified in config."""
        key = os.environ.get(self.llm.api_key_env)
        self._api_key = key
        return key


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


_REQUIRED_KEYS = {"llm", "embedding", "nli", "relationship_scoring", "gap_discovery", "storage", "pipeline"}


def load_settings(config_path: str | Path = "config.yaml") -> Settings:
    """
    Load and validate settings from *config_path*.

    Raises
    ------
    FileNotFoundError
        If the config file does not exist.
    KeyError
        If a required top-level key is missing.
    ValueError
        If any value fails range or consistency validation (bubbles from Pydantic).
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path.resolve()}\n"
            "Create a config.yaml file in the project root. "
            "See config.yaml.example for the full schema."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        raw: dict = yaml.safe_load(fh) or {}

    missing = _REQUIRED_KEYS - set(raw.keys())
    if missing:
        raise KeyError(
            f"Missing required configuration key(s): {sorted(missing)}. "
            f"Check {config_path} and ensure all required sections are present."
        )

    # Pydantic validates types + ranges and raises with descriptive messages
    settings = Settings(**raw)
    return settings
