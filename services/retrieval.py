from __future__ import annotations

import heapq
import sys
from typing import Any

from embeddings import cosine_similarity, embed_text
from storage import load_chunks, load_graph, load_sources


def _sort_newest(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda record: str(record.get("created_at", "")), reverse=True)


def _source_node_id(source_id: str) -> str:
    return f"source-{source_id}"


def _source_id_from_node(node_id: str) -> str | None:
    return node_id.removeprefix("source-") if node_id.startswith("source-") else None


def _rank_chunks(
    question_embedding: list[float],
    chunks: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    def scored_chunks() -> Any:
        for chunk in chunks:
            embedding = chunk.get("embedding")
            if not isinstance(embedding, list) or len(embedding) != len(question_embedding):
                continue
            score = cosine_similarity(question_embedding, embedding)
            yield (score, chunk)

    return [
        {**chunk, "score": round(score, 4)}
        for score, chunk in heapq.nlargest(limit, scored_chunks(), key=lambda item: item[0])
    ]


def _embed_query(query: str) -> list[float]:
    api_module = sys.modules.get("api")
    api_embed_text = getattr(api_module, "embed_text", None)
    if callable(api_embed_text) and api_embed_text is not embed_text:
        return api_embed_text(query)
    return embed_text(query)


def _build_graph_context(
    top_chunks: list[dict[str, Any]],
    all_chunks: list[dict[str, Any]],
    graph: dict[str, list[dict[str, Any]]],
    max_extra_sources: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_by_id = {str(node.get("id")): node for node in nodes if isinstance(node, dict)}
    source_title_by_id = {
        str(chunk.get("source_id")): str(chunk.get("source_title", "Untitled"))
        for chunk in all_chunks
        if chunk.get("source_id")
    }
    top_source_ids = {
        str(chunk.get("source_id"))
        for chunk in top_chunks
        if chunk.get("source_id")
    }
    if not top_source_ids or not edges:
        return top_chunks, []

    concept_to_sources: dict[str, set[str]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        source_id = _source_id_from_node(source)
        concept_id = target if target.startswith("concept-") else ""
        if not source_id or not concept_id:
            continue
        concept_to_sources.setdefault(concept_id, set()).add(source_id)

    related_source_ids: set[str] = set()
    graph_match_by_source_id: dict[str, dict[str, str]] = {}
    graph_context: list[dict[str, Any]] = []
    for concept_id, source_ids in sorted(concept_to_sources.items()):
        if not source_ids.intersection(top_source_ids):
            continue
        neighbors = source_ids - top_source_ids
        related_source_ids.update(neighbors)
        concept_node = node_by_id.get(concept_id, {})
        concept_label = str(concept_node.get("label", concept_id))
        for source_id in sorted(neighbors):
            graph_match_by_source_id.setdefault(
                source_id,
                {
                    "matched_concept_id": concept_id,
                    "matched_concept_label": concept_label,
                },
            )
        graph_context.append(
            {
                "concept_id": concept_id,
                "concept_label": concept_label,
                "source_ids": sorted(source_ids),
                "source_titles": sorted(
                    source_title_by_id.get(source_id, source_id) for source_id in source_ids
                ),
                "expanded_source_ids": sorted(neighbors),
                "expanded_source_titles": sorted(
                    source_title_by_id.get(source_id, source_id) for source_id in neighbors
                ),
            }
        )

    existing_chunk_ids = {chunk.get("id") for chunk in top_chunks}
    first_chunk_by_source_id: dict[str, dict[str, Any]] = {}
    for chunk in all_chunks:
        source_id = str(chunk.get("source_id", ""))
        if (
            source_id
            and source_id not in first_chunk_by_source_id
            and chunk.get("id") not in existing_chunk_ids
        ):
            first_chunk_by_source_id[source_id] = chunk

    extra_chunks: list[dict[str, Any]] = []
    for source_id in sorted(related_source_ids):
        if len(extra_chunks) >= max_extra_sources:
            break
        chunk = first_chunk_by_source_id.get(source_id)
        if chunk:
            extra_chunks.append(
                {
                    **chunk,
                    **graph_match_by_source_id.get(source_id, {}),
                    "score": 0,
                    "retrieval": "graph_neighbor",
                }
            )
            existing_chunk_ids.add(chunk.get("id"))

    return top_chunks + extra_chunks, graph_context[:8]


def _citation_from_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    citation = {
        "source_id": chunk.get("source_id"),
        "source_title": chunk.get("source_title"),
        "section": chunk.get("section"),
        "text": chunk.get("text"),
        "score": chunk.get("score"),
        "retrieval": chunk.get("retrieval", "vector"),
    }
    if chunk.get("matched_concept_id"):
        citation["matched_concept_id"] = chunk.get("matched_concept_id")
    if chunk.get("matched_concept_label"):
        citation["matched_concept_label"] = chunk.get("matched_concept_label")
    return citation


def search_knowledge_base(
    account_id: str,
    query: str,
    limit: int = 5,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    question_embedding = _embed_query(query)
    chunks = load_chunks(account_id, copy_result=False)
    top_chunks = _rank_chunks(question_embedding, chunks, limit=limit)
    expanded_chunks, graph_context = _build_graph_context(top_chunks, chunks, load_graph(account_id))
    citations = [_citation_from_chunk(chunk) for chunk in expanded_chunks]
    result = {
        "query": query,
        "snippets": [
            {
                "citation_index": index + 1,
                "source_id": chunk.get("source_id"),
                "source_title": chunk.get("source_title"),
                "section": chunk.get("section"),
                "text": str(chunk.get("text", ""))[:1200],
                "score": chunk.get("score"),
                "retrieval": chunk.get("retrieval", "vector"),
                "matched_concept_id": chunk.get("matched_concept_id"),
                "matched_concept_label": chunk.get("matched_concept_label"),
            }
            for index, chunk in enumerate(expanded_chunks)
        ],
        "graph_context": graph_context,
    }
    return result, citations, graph_context


def explore_graph_connections(
    account_id: str,
    source_ids: list[str] | None = None,
    concept_query: str | None = None,
) -> dict[str, Any]:
    graph = load_graph(account_id)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_by_id = {str(node.get("id")): node for node in nodes if isinstance(node, dict)}
    source_filter = {f"source-{source_id}" for source_id in source_ids or [] if source_id}
    concept_query_lower = (concept_query or "").strip().lower()

    concept_to_sources: dict[str, set[str]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if not source.startswith("source-") or not target.startswith("concept-"):
            continue
        if source_filter and source not in source_filter:
            continue
        concept_node = node_by_id.get(target, {})
        concept_label = str(concept_node.get("label", target))
        if concept_query_lower and concept_query_lower not in concept_label.lower():
            continue
        concept_to_sources.setdefault(target, set()).add(source.removeprefix("source-"))

    if source_filter:
        for edge in edges:
            source = str(edge.get("source", ""))
            target = str(edge.get("target", ""))
            if source not in source_filter or not target.startswith("concept-"):
                continue
            for neighbor in edges:
                neighbor_source = str(neighbor.get("source", ""))
                if str(neighbor.get("target", "")) == target and neighbor_source.startswith("source-"):
                    concept_to_sources.setdefault(target, set()).add(
                        neighbor_source.removeprefix("source-")
                    )

    connections = []
    for concept_id, connected_source_ids in sorted(concept_to_sources.items()):
        concept_node = node_by_id.get(concept_id, {})
        connections.append(
            {
                "concept_id": concept_id,
                "concept_label": str(concept_node.get("label", concept_id)),
                "source_ids": sorted(connected_source_ids),
            }
        )

    return {
        "connections": connections[:12],
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def compare_sources(account_id: str, source_ids: list[str]) -> dict[str, Any]:
    wanted_set = {source_id for source_id in source_ids if source_id}
    sources = [source for source in load_sources(account_id) if source.get("id") in wanted_set]
    concept_sets = [
        {str(concept).strip() for concept in source.get("concepts", []) if str(concept).strip()}
        for source in sources
    ]
    shared_concepts = sorted(set.intersection(*concept_sets)) if len(concept_sets) >= 2 else []

    return {
        "sources": [
            {
                "source_id": source.get("id"),
                "title": source.get("title"),
                "summary": source.get("summary", ""),
                "concepts": source.get("concepts", []),
                "claims": source.get("claims", []),
            }
            for source in sources
        ],
        "shared_concepts": shared_concepts,
        "compared_count": len(sources),
    }


def get_source_detail(account_id: str, source_id: str) -> dict[str, Any]:
    for source in load_sources(account_id):
        if source.get("id") == source_id:
            return {
                "source_id": source.get("id"),
                "title": source.get("title"),
                "type": source.get("type"),
                "summary": source.get("summary", ""),
                "key_ideas": source.get("key_ideas", []),
                "concepts": source.get("concepts", []),
                "claims": source.get("claims", []),
                "content": str(source.get("content", ""))[:6000],
            }
    raise ValueError("Source not found.")
