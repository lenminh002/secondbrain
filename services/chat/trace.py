from __future__ import annotations

from typing import Any

from services.chat.types import AgentEventHandler, AgentRunState


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
