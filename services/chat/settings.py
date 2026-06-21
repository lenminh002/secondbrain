from __future__ import annotations

import sys

MAX_RESEARCH_ROUNDS = 2
MAX_TOOL_CALLS = 6
MIN_EVIDENCE_SCORE = 0.62


def max_research_rounds() -> int:
    return int(_facade_value("MAX_RESEARCH_ROUNDS", MAX_RESEARCH_ROUNDS))


def max_tool_calls() -> int:
    return int(_facade_value("MAX_TOOL_CALLS", MAX_TOOL_CALLS))


def min_evidence_score() -> float:
    return float(_facade_value("MIN_EVIDENCE_SCORE", MIN_EVIDENCE_SCORE))


def _facade_value(name: str, default: int | float) -> int | float:
    facade = sys.modules.get("services.chat_service")
    if facade is not None and hasattr(facade, name):
        return getattr(facade, name)
    return default
