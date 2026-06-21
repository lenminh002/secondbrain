from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from knowledge_ai import answer_with_context, answer_with_tools, stream_with_tools
from services.chat.evidence import (
    _context_chunks_from_citations,
    _evaluate_evidence,
    _source_ids_from_citations,
    _verification_summary,
)
from services.chat.planning import _direct_simple_response, build_agent_plan, classify_message
from services.chat.settings import max_tool_calls
from services.chat.tools import (
    _compare_and_record,
    _explore_and_record,
    _get_and_record_detail,
    _make_execute_tool,
    _search_and_merge,
)
from services.chat.trace import _add_step
from services.chat.types import AgentEventHandler, AgentRunState, ChatHistory


def _answer_with_tools(
    message: str,
    execute_tool: Callable[[str, dict[str, Any]], dict[str, Any]],
    history: ChatHistory | None = None,
) -> tuple[str, list[str]]:
    api_module = sys.modules.get("api")
    api_answer_with_tools = getattr(api_module, "answer_with_tools", None)
    is_original_export = (
        getattr(api_answer_with_tools, "__module__", "") == "knowledge_ai"
        and getattr(api_answer_with_tools, "__name__", "") == "answer_with_tools"
    )
    if callable(api_answer_with_tools) and not is_original_export:
        return api_answer_with_tools(message, execute_tool)
    return answer_with_tools(message, execute_tool, history=history)


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
    if source_ids and state.tool_call_count < max_tool_calls():
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
            for event in stream_with_tools(
                state.message,
                execute_tool,
                history=state.history,
            ):
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
                history=state.history,
            )
            if emit_event:
                emit_event({"type": "text", "text": answer})
            return answer

    try:
        answer, used_tools = _answer_with_tools(
            state.message,
            execute_tool,
            history=state.history,
        )
        state.tool_calls[:] = [{"name": name} for name in used_tools]
        return answer
    except ValueError:
        return answer_with_context(
            state.message,
            _context_chunks_from_citations(state.citations),
            state.graph_context,
            history=state.history,
        )


def run_agent(
    account_id: str,
    message: str,
    *,
    history: ChatHistory | None = None,
    emit_event: AgentEventHandler | None = None,
    stream_text: bool = False,
) -> dict[str, Any]:
    state = AgentRunState(account_id=account_id, message=message, history=history or [])
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


def chat_response(
    account_id: str,
    message: str,
    *,
    history: ChatHistory | None = None,
) -> dict[str, Any]:
    return run_agent(account_id, message, history=history)
