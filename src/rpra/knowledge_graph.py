"""
Knowledge Graph Construction and Storage (Requirement 5).

Uses NetworkX as the in-memory graph and JSON for persistence.
Supports incremental updates and provides a query interface.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import networkx as nx

from rpra.models import (
    Document,
    Entity,
    EvidenceTrail,
    Relation,
    RelationshipScore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid_str(v: Any) -> str:
    return str(v) if isinstance(v, UUID) else v


def _trail_to_dict(t: EvidenceTrail) -> dict:
    return t.model_dump()


# ---------------------------------------------------------------------------
# KnowledgeGraph
# ---------------------------------------------------------------------------


class KnowledgeGraph:
    """
    Directed multigraph where nodes represent documents or entities and
    edges represent typed relations with evidence trails.
    """

    def __init__(self) -> None:
        self._graph: nx.MultiDiGraph = nx.MultiDiGraph()

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def add_document(self, doc: Document) -> None:
        """Add a document node."""
        self._graph.add_node(
            doc.id,
            node_type="document",
            title=doc.title,
            category=doc.category.value,
            file_path=doc.file_path,
        )

    def add_entity(self, entity: Entity) -> None:
        """Add an entity node."""
        node_id = _uuid_str(entity.id)
        self._graph.add_node(
            node_id,
            node_type="entity",
            entity_type=entity.entity_type.value,
            text=entity.text,
            doc_id=entity.doc_id,
            section=entity.section,
            page_number=entity.page_number,
            sentence_span=entity.sentence_span,
        )
        # Link entity to its parent document
        self._graph.add_edge(
            entity.doc_id,
            node_id,
            edge_type="contains",
            evidence=None,
        )

    def add_relation(self, relation: Relation) -> None:
        """Add a typed relation edge."""
        self._graph.add_edge(
            _uuid_str(relation.source_id),
            _uuid_str(relation.target_id),
            edge_type=relation.relation_type.value,
            evidence=_trail_to_dict(relation.evidence),
            confidence=relation.confidence,
            is_cross_document=relation.is_cross_document,
        )

    def add_relationship_score(self, score: RelationshipScore) -> None:
        """Store pairwise relationship score as a document–document edge."""
        self._graph.add_edge(
            score.doc_id_a,
            score.doc_id_b,
            edge_type="relationship_score",
            composite_score=score.composite_score,
            objective_similarity=score.objective_similarity,
            methodology_similarity=score.methodology_similarity,
            dataset_overlap=score.dataset_overlap,
            results_metrics_similarity=score.results_metrics_similarity,
            citation_overlap=score.citation_overlap,
            weights_used=score.weights_used,
        )

    def add_bridge_entities(self, bridge_map: dict[str, list[str]]) -> None:
        """
        For each bridge entity text, add a bridge-node and connect it to all
        documents that contain it.
        """
        for text, doc_ids in bridge_map.items():
            bridge_id = f"bridge::{text}"
            if not self._graph.has_node(bridge_id):
                self._graph.add_node(
                    bridge_id,
                    node_type="bridge_entity",
                    text=text,
                )
            for doc_id in doc_ids:
                if self._graph.has_node(doc_id):
                    self._graph.add_edge(doc_id, bridge_id, edge_type="has_bridge_entity")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> dict | None:
        if self._graph.has_node(node_id):
            return dict(self._graph.nodes[node_id])
        return None

    def get_neighbors(self, node_id: str) -> list[str]:
        return list(self._graph.successors(node_id))

    def get_edges_between(self, a: str, b: str) -> list[dict]:
        edges = self._graph.get_edge_data(a, b) or {}
        return [dict(v) for v in edges.values()]

    def subgraph_for_document(self, doc_id: str, depth: int = 2) -> "KnowledgeGraph":
        """Return a KG containing *doc_id* and all nodes within *depth* hops."""
        nodes = nx.ego_graph(self._graph, doc_id, radius=depth, undirected=True).nodes()
        sub = KnowledgeGraph()
        sub._graph = self._graph.subgraph(nodes).copy()
        return sub

    def documents_sharing_bridge_entity(self, entity_text: str) -> list[str]:
        bridge_id = f"bridge::{entity_text.lower()}"
        if not self._graph.has_node(bridge_id):
            return []
        return [
            pred for pred in self._graph.predecessors(bridge_id)
            if self._graph.nodes[pred].get("node_type") == "document"
        ]

    def all_document_ids(self) -> list[str]:
        return [
            n for n, d in self._graph.nodes(data=True)
            if d.get("node_type") == "document"
        ]

    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    # ------------------------------------------------------------------
    # Serialisation  (Requirement 18 — round-trip integrity)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise the graph to a JSON-compatible dict."""
        return {
            "nodes": [
                {"id": n, **dict(attrs)}
                for n, attrs in self._graph.nodes(data=True)
            ],
            "edges": [
                {
                    "source": u,
                    "target": v,
                    "key": k,
                    **dict(attrs),
                }
                for u, v, k, attrs in self._graph.edges(data=True, keys=True)
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeGraph":
        """Deserialise from a dict produced by :meth:`to_dict`."""
        kg = cls()
        for node in data.get("nodes", []):
            node_copy = dict(node)
            node_id = node_copy.pop("id")
            kg._graph.add_node(node_id, **node_copy)
        for edge in data.get("edges", []):
            edge_copy = dict(edge)
            src = edge_copy.pop("source")
            tgt = edge_copy.pop("target")
            edge_copy.pop("key", None)
            kg._graph.add_edge(src, tgt, **edge_copy)
        return kg

    def save(self, path: str | Path) -> None:
        """Persist graph to *path* as JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, default=str)

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeGraph":
        """Load from a JSON file saved by :meth:`save`."""
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)


# ---------------------------------------------------------------------------
# Builder helper
# ---------------------------------------------------------------------------


def build_knowledge_graph(
    documents: list[Document],
    entities: list[Entity],
    relations: list[Relation],
    bridge_entities: dict[str, list[str]],
    relationship_scores: list[RelationshipScore] | None = None,
) -> KnowledgeGraph:
    """
    Assemble the full Knowledge Graph from pipeline artefacts.
    """
    kg = KnowledgeGraph()

    for doc in documents:
        kg.add_document(doc)

    for entity in entities:
        kg.add_entity(entity)

    for relation in relations:
        kg.add_relation(relation)

    kg.add_bridge_entities(bridge_entities)

    if relationship_scores:
        for score in relationship_scores:
            kg.add_relationship_score(score)

    return kg
