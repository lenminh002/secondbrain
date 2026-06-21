from __future__ import annotations

import re
from typing import Any

from services.chat.settings import max_research_rounds, max_tool_calls, min_evidence_score
from services.chat.types import AgentRunState


def _source_ids_from_citations(citations: list[dict[str, Any]], limit: int = 5) -> list[str]:
    source_ids: list[str] = []
    seen: set[str] = set()
    for citation in citations:
        source_id = str(citation.get("source_id") or "")
        if source_id and source_id not in seen:
            source_ids.append(source_id)
            seen.add(source_id)
        if len(source_ids) >= limit:
            break
    return source_ids


def _merge_citations(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for citation in [*existing, *incoming]:
        key = (
            str(citation.get("source_id") or ""),
            str(citation.get("section") or ""),
            str(citation.get("text") or "")[:180],
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(citation)
    return merged


def _merge_graph_context(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_concept: dict[str, dict[str, Any]] = {}
    for item in [*existing, *incoming]:
        concept_id = str(item.get("concept_id") or "")
        if not concept_id:
            continue
        current = by_concept.setdefault(concept_id, {**item})
        for key in ("source_ids", "source_titles", "expanded_source_ids", "expanded_source_titles"):
            values = {str(value) for value in current.get(key, []) if str(value)}
            values.update(str(value) for value in item.get(key, []) if str(value))
            current[key] = sorted(values)
    return list(by_concept.values())[:8]


def _verification_summary(answer: str, citations: list[dict[str, Any]]) -> dict[str, Any]:
    cited_indices = {int(index) for index in re.findall(r"\[(\d+)\]", answer)}
    citation_count = len(citations)
    unsupported = sorted(index for index in cited_indices if index < 1 or index > citation_count)
    return {
        "status": "warning" if unsupported or (answer and not citations) else "grounded",
        "citation_count": citation_count,
        "cited_indices": sorted(cited_indices),
        "unsupported_citation_indices": unsupported,
    }


def _context_chunks_from_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_id": citation.get("source_id"),
            "source_title": citation.get("source_title"),
            "section": citation.get("section"),
            "text": citation.get("text"),
            "score": citation.get("score"),
            "retrieval": citation.get("retrieval", "vector"),
            "matched_concept_id": citation.get("matched_concept_id"),
            "matched_concept_label": citation.get("matched_concept_label"),
        }
        for citation in citations
    ]


def _evaluate_evidence(state: AgentRunState) -> dict[str, Any]:
    source_ids = _source_ids_from_citations(state.citations, limit=20)
    citation_count = len(state.citations)
    source_count = len(source_ids)
    graph_connection_count = len(state.graph_context)
    has_detail = bool(state.source_details)

    citation_score = min(0.4, citation_count * 0.14)
    diversity_score = min(0.25, source_count * 0.125)
    graph_score = 0.2 if graph_connection_count else 0.0
    detail_score = 0.15 if has_detail else 0.0
    score = round(citation_score + diversity_score + graph_score + detail_score, 2)
    state.evidence_score = score

    needs_revision = (
        score < min_evidence_score()
        and state.rounds_used < max_research_rounds()
        and state.tool_call_count < max_tool_calls()
    )
    return {
        "score": score,
        "status": "strong" if score >= min_evidence_score() else "weak",
        "needs_revision": needs_revision,
        "citation_count": citation_count,
        "source_count": source_count,
        "graph_connection_count": graph_connection_count,
        "has_detail": has_detail,
        "rounds_used": state.rounds_used,
        "tool_call_count": state.tool_call_count,
    }
