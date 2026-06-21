from __future__ import annotations

from typing import Any


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


def _direct_simple_response(message: str) -> str:
    normalized = message.strip().lower()
    if "thank" in normalized:
        return "You're welcome."
    return "Hi. Ask me anything about your saved knowledge base."
