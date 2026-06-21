from __future__ import annotations

import re
import uuid
from typing import Any

def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or str(uuid.uuid4())


def coerce_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def coerce_graph(value: Any) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(value, dict):
        return {"nodes": [], "edges": []}
    nodes = value.get("nodes") if isinstance(value.get("nodes"), list) else []
    edges = value.get("edges") if isinstance(value.get("edges"), list) else []
    return {"nodes": coerce_list(nodes), "edges": coerce_list(edges)}


def merge_graph(
    graph: dict[str, list[dict[str, Any]]],
    source: dict[str, Any],
    concepts: list[str],
    tags: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    nodes_by_id = {node.get("id"): node for node in nodes if isinstance(node, dict)}
    source_node_id = f"source-{source['id']}"
    edges = [
        edge
        for edge in edges
        if not (isinstance(edge, dict) and edge.get("source") == source_node_id)
    ]
    edge_keys = {
        (edge.get("source"), edge.get("target"), edge.get("relation"))
        for edge in edges
        if isinstance(edge, dict)
    }

    nodes_by_id[source_node_id] = {
        "id": source_node_id,
        "label": source["title"],
        "type": "source",
    }

    for concept in concepts:
        concept_id = f"concept-{slugify(concept)}"
        nodes_by_id[concept_id] = {"id": concept_id, "label": concept, "type": "concept"}
        key = (source_node_id, concept_id, "mentions")
        if key not in edge_keys:
            edges.append({"source": source_node_id, "target": concept_id, "relation": "mentions"})
            edge_keys.add(key)

    for tag in (tags or []):
        tag_id = f"tag-{slugify(tag)}"
        nodes_by_id[tag_id] = {"id": tag_id, "label": tag, "type": "tag"}
        key = (source_node_id, tag_id, "tagged_as")
        if key not in edge_keys:
            edges.append({"source": source_node_id, "target": tag_id, "relation": "tagged_as"})
            edge_keys.add(key)

    return {"nodes": list(nodes_by_id.values()), "edges": edges}
