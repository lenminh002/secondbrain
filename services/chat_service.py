from __future__ import annotations

from typing import Any

from knowledge_ai import answer_with_context, answer_with_tools
from services.retrieval import get_source_detail, search_knowledge_base


def _make_execute_tool(
    account_id: str,
    message: str,
    citations: list[dict[str, Any]],
    graph_context: list[dict[str, Any]],
) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
    """Return an execute_tool callable that closes over the mutable citation/graph lists."""

    def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        nonlocal citations, graph_context
        if tool_name == "search_knowledge_base":
            query = str(tool_input.get("query") or message).strip() or message
            result, citations[:], graph_context[:] = search_knowledge_base(account_id, query)
            # Replace contents in-place so callers see the updated lists
            return result
        if tool_name == "get_source_detail":
            source_id = str(tool_input.get("source_id") or "").strip()
            if not source_id:
                raise ValueError("source_id is required.")
            return get_source_detail(account_id, source_id)
        raise ValueError(f"Unknown tool: {tool_name}")

    return execute_tool


def chat_response(account_id: str, message: str) -> dict[str, Any]:
    citations: list[dict[str, Any]] = []
    graph_context: list[dict[str, Any]] = []
    tool_calls: list[dict[str, str]] = []

    execute_tool = _make_execute_tool(account_id, message, citations, graph_context)

    try:
        answer, used_tools = answer_with_tools(message, execute_tool)
        tool_calls = [{"name": name} for name in used_tools]
    except ValueError:
        top_chunks = [
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
        answer = answer_with_context(message, top_chunks, graph_context)

    return {
        "answer": answer,
        "citations": citations,
        "graph_context": graph_context,
        "tool_calls": tool_calls,
    }
