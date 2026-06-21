from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.chat.evidence import (
    _merge_citations,
    _merge_graph_context,
    _source_ids_from_citations,
)
from services.chat.settings import max_tool_calls
from services.chat.trace import _add_step
from services.chat.types import AgentEventHandler, AgentRunState
from services.retrieval import (
    compare_sources,
    explore_graph_connections,
    get_source_detail,
    search_knowledge_base,
)


def _record_tool_budget(state: AgentRunState, tool_name: str) -> None:
    if state.tool_call_count >= max_tool_calls():
        raise ValueError(f"Tool budget exhausted before {tool_name}.")
    state.tool_call_count += 1


def _search_and_merge(state: AgentRunState, query: str) -> dict[str, Any]:
    _record_tool_budget(state, "search_knowledge_base")
    result, citations, graph_context = search_knowledge_base(state.account_id, query)
    state.citations[:] = _merge_citations(state.citations, citations)
    state.graph_context[:] = _merge_graph_context(state.graph_context, graph_context)
    return result


def _explore_and_record(state: AgentRunState, source_ids: list[str]) -> dict[str, Any]:
    _record_tool_budget(state, "explore_graph_connections")
    result = explore_graph_connections(state.account_id, source_ids)
    return result


def _get_and_record_detail(state: AgentRunState, source_id: str) -> dict[str, Any]:
    _record_tool_budget(state, "get_source_detail")
    detail = get_source_detail(state.account_id, source_id)
    state.source_details[source_id] = detail
    return detail


def _compare_and_record(state: AgentRunState, source_ids: list[str]) -> dict[str, Any]:
    _record_tool_budget(state, "compare_sources")
    result = compare_sources(state.account_id, source_ids)
    state.compared_sources = result
    return result


def _make_execute_tool(
    state: AgentRunState,
    emit_event: AgentEventHandler | None = None,
) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "search_knowledge_base":
            query = str(tool_input.get("query") or state.message).strip() or state.message
            result = _search_and_merge(state, query)
            _add_step(
                state,
                emit_event,
                "gathering",
                "Searched knowledge base",
                f"Query: {query}",
                metadata={"snippets": len(result.get("snippets", [])), "tool_call_count": state.tool_call_count},
            )
            return result
        if tool_name == "get_source_detail":
            source_id = str(tool_input.get("source_id") or "").strip()
            if not source_id:
                raise ValueError("source_id is required.")
            detail = _get_and_record_detail(state, source_id)
            _add_step(
                state,
                emit_event,
                "gathering",
                "Fetched source detail",
                str(detail.get("title") or source_id),
                metadata={"source_id": source_id, "tool_call_count": state.tool_call_count},
            )
            return detail
        if tool_name == "explore_graph_connections":
            source_ids = [
                str(source_id)
                for source_id in tool_input.get("source_ids", [])
                if str(source_id).strip()
            ]
            concept_query = str(tool_input.get("concept_query") or "").strip()
            if not source_ids:
                source_ids = _source_ids_from_citations(state.citations)
            result = _explore_and_record(state, source_ids)
            _add_step(
                state,
                emit_event,
                "gathering",
                "Explored graph connections",
                f"Found {len(result.get('connections', []))} concept cluster(s).",
                metadata={
                    "source_ids": source_ids,
                    "concept_query": concept_query,
                    "tool_call_count": state.tool_call_count,
                },
            )
            return result
        if tool_name == "compare_sources":
            source_ids = [
                str(source_id)
                for source_id in tool_input.get("source_ids", [])
                if str(source_id).strip()
            ]
            result = _compare_and_record(state, source_ids)
            _add_step(
                state,
                emit_event,
                "gathering",
                "Compared source records",
                f"Compared {result.get('compared_count', 0)} source(s).",
                metadata={
                    "shared_concepts": result.get("shared_concepts", []),
                    "tool_call_count": state.tool_call_count,
                },
            )
            return result
        raise ValueError(f"Unknown tool: {tool_name}")

    return execute_tool
