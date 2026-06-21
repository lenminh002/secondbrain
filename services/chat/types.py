from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

AgentEventHandler = Callable[[dict[str, Any]], None]
ChatHistory = list[dict[str, str]]


@dataclass
class AgentRunState:
    account_id: str
    message: str
    history: ChatHistory = field(default_factory=list)
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
