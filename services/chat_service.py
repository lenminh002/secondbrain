from __future__ import annotations

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from knowledge_ai import answer_with_context, answer_with_tools, stream_with_tools
from services.retrieval import (
    compare_sources,
    explore_graph_connections,
    get_source_detail,
    search_knowledge_base,
)

MAX_RESEARCH_ROUNDS = 2
MAX_TOOL_CALLS = 6
MIN_EVIDENCE_SCORE = 0.62

AgentEventHandler = Callable[[dict[str, Any]], None]


@dataclass
class AgentRunState:
    account_id: str
    message: str
    plan: dict[str, Any] = field(default_factory=dict)
    citations: list[dict[str, Any]] = field(default_factory=list)
    graph_context: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, str]] = field(default_factory=list)
    agent_trace: list[dict[str, Any]] = field(default_factory=list)
    source_details: dict[str, dict[str, Any]] = field(default_factory=dict)
    evidence_score: float = 0.0
    rounds_used: int = 0
    tool_call_count: int = 0
    classification: dict[str, Any] = field(default_factory=dict)
    compared_sources: dict[str, Any] | None = None


def _agent_step(
    stage: str,
    title: str,
    detail: str = "",
    *,
    status: str = "done",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "title": title,
        "detail": detail,
        "status": status,
        "metadata": metadata or {},
    }


def _add_step(
    state: AgentRunState,
    emit_event: AgentEventHandler | None,
    stage: str,
    title: str,
    detail: str = "",
    *,
    status: str = "done",
    metadata: dict[str, Any] | None = None,
) -> None:
    step = _agent_step(stage, title, detail, status=status, metadata=metadata)
    state.agent_trace.append(step)
    if emit_event:
        emit_event({"type": "agent_step", **step})


def classify_message(message: str) -> dict[str, Any]:
    normalized = " ".join(message.strip().lower().split())
    simple_messages = {
        "hi",
        "hello",
        "hey",
        "thanks",
        "thank you",
        "ok",
        "okay",
        "cool",
        "nice",
    }
    tokens = normalized.split()
    is_simple = normalized in simple_messages or (
        len(tokens) <= 3
        and not normalized.endswith("?")
        and any(token in {"hi", "hello", "hey", "thanks"} for token in tokens)
    )
    return {
        "kind": "simple_chat" if is_simple else "knowledge_question",
        "is_simple": is_simple,
        "reason": "Short conversational message." if is_simple else "Needs knowledge retrieval.",
    }


def build_agent_plan(message: str) -> dict[str, Any]:
    normalized = " ".join(message.strip().split())
    lower = normalized.lower()
    synthesis_markers = [
        "compare",
        "connection",
        "connect",
        "relationship",
        "theme",
        "contradiction",
        "synthesize",
        "across",
        "why",
        "how",
    ]
    wants_synthesis = any(marker in lower for marker in synthesis_markers)
    queries = [normalized]
    if wants_synthesis:
        queries.append(f"core concepts related to {normalized}")
        queries.append(f"claims and tensions about {normalized}")

    deduped_queries: list[str] = []
    seen: set[str] = set()
    for query in queries:
        key = query.lower()
        if key and key not in seen:
            deduped_queries.append(query)
            seen.add(key)

    return {
        "mode": "synthesis" if wants_synthesis else "focused_lookup",
        "queries": deduped_queries[:3],
        "needs_graph": wants_synthesis,
        "needs_comparison": wants_synthesis,
    }


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


def _answer_with_tools(
    message: str,
    execute_tool: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> tuple[str, list[str]]:
    api_module = sys.modules.get("api")
    api_answer_with_tools = getattr(api_module, "answer_with_tools", None)
    is_original_export = (
        getattr(api_answer_with_tools, "__module__", "") == "knowledge_ai"
        and getattr(api_answer_with_tools, "__name__", "") == "answer_with_tools"
    )
    if callable(api_answer_with_tools) and not is_original_export:
        return api_answer_with_tools(message, execute_tool)
    return answer_with_tools(message, execute_tool)


def _record_tool_budget(state: AgentRunState, tool_name: str) -> None:
    if state.tool_call_count >= MAX_TOOL_CALLS:
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
        score < MIN_EVIDENCE_SCORE
        and state.rounds_used < MAX_RESEARCH_ROUNDS
        and state.tool_call_count < MAX_TOOL_CALLS
    )
    return {
        "score": score,
        "status": "strong" if score >= MIN_EVIDENCE_SCORE else "weak",
        "needs_revision": needs_revision,
        "citation_count": citation_count,
        "source_count": source_count,
        "graph_connection_count": graph_connection_count,
        "has_detail": has_detail,
        "rounds_used": state.rounds_used,
        "tool_call_count": state.tool_call_count,
    }


def _run_initial_gather(state: AgentRunState, emit_event: AgentEventHandler | None) -> None:
    state.rounds_used = 1
    query = str(state.plan.get("queries", [state.message])[0])
    result = _search_and_merge(state, query)
    _add_step(
        state,
        emit_event,
        "gathering",
        "Gathered first-pass evidence",
        f"Query: {query}",
        metadata={"snippets": len(result.get("snippets", [])), "tool_call_count": state.tool_call_count},
    )

    source_ids = _source_ids_from_citations(state.citations)
    if source_ids and state.tool_call_count < MAX_TOOL_CALLS:
        graph_result = _explore_and_record(state, source_ids)
        _add_step(
            state,
            emit_event,
            "gathering",
            "Mapped graph neighborhood",
            f"Found {len(graph_result.get('connections', []))} concept cluster(s).",
            metadata={"source_ids": source_ids, "tool_call_count": state.tool_call_count},
        )


def _run_revision(
    state: AgentRunState,
    emit_event: AgentEventHandler | None,
    evaluation: dict[str, Any],
) -> None:
    source_ids = _source_ids_from_citations(state.citations)
    state.rounds_used = 2

    if source_ids and not state.source_details:
        try:
            detail = _get_and_record_detail(state, source_ids[0])
            _add_step(
                state,
                emit_event,
                "revising",
                "Fetched strongest source detail",
                str(detail.get("title") or source_ids[0]),
                metadata={"source_id": source_ids[0], "tool_call_count": state.tool_call_count},
            )
            return
        except ValueError:
            _add_step(
                state,
                emit_event,
                "revising",
                "Source detail unavailable",
                f"Falling back after missing source record: {source_ids[0]}",
                status="warning",
                metadata={"source_id": source_ids[0], "tool_call_count": state.tool_call_count},
            )

    if state.plan.get("needs_comparison") and len(source_ids) >= 2:
        comparison = _compare_and_record(state, source_ids[:5])
        _add_step(
            state,
            emit_event,
            "revising",
            "Compared candidate sources",
            f"Compared {comparison.get('compared_count', 0)} source(s).",
            metadata={"shared_concepts": comparison.get("shared_concepts", []), "tool_call_count": state.tool_call_count},
        )
        return

    if source_ids and not state.graph_context:
        graph_result = _explore_and_record(state, source_ids)
        _add_step(
            state,
            emit_event,
            "revising",
            "Retried graph exploration",
            f"Found {len(graph_result.get('connections', []))} concept cluster(s).",
            metadata={"source_ids": source_ids, "tool_call_count": state.tool_call_count},
        )
        return

    queries = state.plan.get("queries", [])
    fallback_query = str(queries[1] if len(queries) > 1 else f"more evidence about {state.message}")
    result = _search_and_merge(state, fallback_query)
    _add_step(
        state,
        emit_event,
        "revising",
        "Ran targeted follow-up search",
        f"Query: {fallback_query}",
        metadata={
            "previous_score": evaluation.get("score"),
            "snippets": len(result.get("snippets", [])),
            "tool_call_count": state.tool_call_count,
        },
    )


def _direct_simple_response(message: str) -> str:
    normalized = message.strip().lower()
    if "thank" in normalized:
        return "You're welcome."
    return "Hi. Ask me anything about your saved knowledge base."


def _synthesize_answer(
    state: AgentRunState,
    emit_event: AgentEventHandler | None,
    *,
    stream_text: bool,
) -> str:
    _add_step(
        state,
        emit_event,
        "synthesis",
        "Synthesizing grounded answer",
        f"Using {len(state.citations)} citation candidate(s).",
        metadata={"evidence_score": state.evidence_score},
    )
    execute_tool = _make_execute_tool(state, emit_event)

    if stream_text:
        streamed_answer = ""
        try:
            for event in stream_with_tools(state.message, execute_tool):
                if event.get("type") == "tool_call":
                    name = str(event.get("name", ""))
                    state.tool_calls.append({"name": name})
                    if emit_event:
                        emit_event(event)
                elif event.get("type") == "text":
                    streamed_answer += str(event.get("text", ""))
                    if emit_event:
                        emit_event(event)
            return streamed_answer
        except ValueError:
            answer = answer_with_context(
                state.message,
                _context_chunks_from_citations(state.citations),
                state.graph_context,
            )
            if emit_event:
                emit_event({"type": "text", "text": answer})
            return answer

    try:
        answer, used_tools = _answer_with_tools(state.message, execute_tool)
        state.tool_calls[:] = [{"name": name} for name in used_tools]
        return answer
    except ValueError:
        return answer_with_context(
            state.message,
            _context_chunks_from_citations(state.citations),
            state.graph_context,
        )


def run_agent(
    account_id: str,
    message: str,
    *,
    emit_event: AgentEventHandler | None = None,
    stream_text: bool = False,
) -> dict[str, Any]:
    state = AgentRunState(account_id=account_id, message=message)
    state.classification = classify_message(message)
    _add_step(
        state,
        emit_event,
        "classify",
        "Classified request",
        state.classification["reason"],
        metadata=state.classification,
    )

    if state.classification["is_simple"]:
        answer = _direct_simple_response(message)
        if stream_text and emit_event:
            emit_event({"type": "text", "text": answer})
    else:
        state.plan = build_agent_plan(message)
        _add_step(
            state,
            emit_event,
            "planning",
            "Built retrieval plan",
            f"{state.plan['mode']} across {len(state.plan['queries'])} query path(s).",
            metadata=state.plan,
        )

        _run_initial_gather(state, emit_event)
        evaluation = _evaluate_evidence(state)
        _add_step(
            state,
            emit_event,
            "evaluating",
            "Scored evidence",
            f"Evidence is {evaluation['status']} ({evaluation['score']}).",
            status=evaluation["status"],
            metadata=evaluation,
        )

        if evaluation["needs_revision"]:
            _run_revision(state, emit_event, evaluation)
            evaluation = _evaluate_evidence(state)
            _add_step(
                state,
                emit_event,
                "evaluating",
                "Re-scored evidence",
                f"Evidence is {evaluation['status']} ({evaluation['score']}).",
                status=evaluation["status"],
                metadata=evaluation,
            )

        answer = _synthesize_answer(state, emit_event, stream_text=stream_text)

    verification = _verification_summary(answer, state.citations)
    _add_step(
        state,
        emit_event,
        "verification",
        "Checked citation grounding",
        f"{verification['citation_count']} citation(s), status: {verification['status']}.",
        status=verification["status"],
        metadata=verification,
    )

    return {
        "answer": answer,
        "citations": state.citations,
        "graph_context": state.graph_context,
        "tool_calls": state.tool_calls,
        "agent_trace": state.agent_trace,
    }


def chat_response(account_id: str, message: str) -> dict[str, Any]:
    return run_agent(account_id, message)
