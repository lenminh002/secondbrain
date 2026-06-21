from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Generator
from typing import Any

from anthropic import Anthropic

MODEL_NAME = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_AGENT_TURNS = 3

CHAT_TOOLS = [
    {
        "name": "search_knowledge_base",
        "description": "Search the user's saved knowledge base for relevant notes and graph-connected context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to run against saved knowledge.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_source_detail",
        "description": "Fetch the full content and enrichment fields for one saved source by source_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "The exact source_id returned by search_knowledge_base.",
                }
            },
            "required": ["source_id"],
            "additionalProperties": False,
        },
    },
]


def _strip_code_fence(text: str) -> str:
    """Extract the first fenced JSON block, or return the raw text.

    Previously anchored with $ so prose *around* a fenced block ("Here is the
    JSON: ```{...}```") was not stripped, causing json.loads to fail.  Now we
    search for the first fenced block anywhere in the response.
    """
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    return fenced.group(1).strip() if fenced else stripped


def _as_string_list(value: Any, limit: int = 12) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned[:limit]


def _fallback_enrichment(title: str, content: str) -> dict[str, Any]:
    sentences = re.split(r"(?<=[.!?])\s+", content.strip())
    usable = [sentence.strip() for sentence in sentences if sentence.strip()]
    summary = " ".join(usable[:2]) if usable else f"{title} was added to the knowledge base."
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", content)
    seen: set[str] = set()
    concepts: list[str] = []
    for word in words:
        key = word.lower()
        if key not in seen:
            seen.add(key)
            concepts.append(word)
        if len(concepts) >= 8:
            break
    key_ideas = usable[:5] or [summary]
    return {
        "summary": summary,
        "key_ideas": key_ideas,
        "concepts": concepts or ["Knowledge base"],
        "claims": usable[:4],
        "questions": ["What should I connect this to next?"],
        "social_post": f"Added a new note on {title}: {summary[:220]}",
    }


def enrich_content(source_type: str, title: str, source_url: str | None, content: str) -> dict[str, Any]:
    client = _client()
    if client is None:
        return _fallback_enrichment(title, content)

    prompt = f"""
You are turning a consumed knowledge source into a personal knowledge-base entry.

Source type: {source_type}
Title: {title}
Source URL: {source_url or "none"}

Return ONLY valid JSON in this shape:
{{
  "summary": "one concise paragraph",
  "key_ideas": ["short bullet"],
  "concepts": ["canonical concept/entity name"],
  "claims": ["claim or useful assertion"],
  "questions": ["open question for future learning"],
  "social_post": "one social-media style post in first person, under 900 characters"
}}

Content:
{content[:30000]}
""".strip()

    try:
        message = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1800,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        parsed = json.loads(_strip_code_fence(_text_from_content(message.content)))
        if not isinstance(parsed, dict):
            raise ValueError("Claude enrichment response was not a JSON object.")
    except Exception:
        # Malformed / non-JSON model output used to propagate here and mark the
        # entire source as failed.  Degrade gracefully to the rule-based fallback.
        return _fallback_enrichment(title, content)

    fallback = _fallback_enrichment(title, content)
    return {
        "summary": str(parsed.get("summary", "")).strip() or fallback["summary"],
        "key_ideas": _as_string_list(parsed.get("key_ideas")),
        "concepts": _as_string_list(parsed.get("concepts")),
        "claims": _as_string_list(parsed.get("claims")),
        "questions": _as_string_list(parsed.get("questions")),
        "social_post": str(parsed.get("social_post", "")).strip() or fallback["social_post"],
    }


def answer_with_context(
    message: str,
    chunks: list[dict[str, Any]],
    graph_context: list[dict[str, Any]] | None = None,
) -> str:
    context = "\n\n".join(
        f"[{index + 1}] {chunk.get('source_title', 'Untitled')} / {chunk.get('section', 'Notes')}\n{chunk.get('text', '')}"
        for index, chunk in enumerate(chunks)
    )
    graph_lines = "\n".join(
        f"- {item.get('concept_label')}: connects {', '.join(item.get('source_titles', []))}"
        for item in (graph_context or [])
    )
    client = _client()
    if client is None:
        if not chunks:
            return "I do not have enough knowledge-base context to answer that yet."
        return (
            "Based on the most relevant saved notes, here is the closest match:\n\n"
            f"{chunks[0].get('text', '').strip()[:900]}"
        )

    prompt = f"""
You are a personal assistant that answers only from the user's saved knowledge base.
If the context is insufficient, say what is missing. Cite sources inline like [1].

User question:
{message}

Retrieved context:
{context or "No relevant context found."}

Graph context:
{graph_lines or "No graph-neighbor context found."}
""".strip()
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1200,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
    )
    return _text_from_content(response.content)


def _client() -> Anthropic | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    return Anthropic(api_key=api_key) if api_key else None


def _message_content_to_params(content: Any) -> list[dict[str, Any]]:
    params: list[dict[str, Any]] = []
    for block in content:
        if hasattr(block, "model_dump"):
            params.append(block.model_dump(exclude_none=True))
        else:
            params.append(dict(block))
    return params


def _text_from_content(content: Any) -> str:
    return "".join(
        block.text for block in content if getattr(block, "type", None) == "text"
    ).strip()


def answer_with_tools(
    message: str,
    execute_tool: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> tuple[str, list[str]]:
    client = _client()
    if client is None:
        raise ValueError("ANTHROPIC_API_KEY is required for tool-based answers.")
    messages: list[dict[str, Any]] = [{"role": "user", "content": message}]
    used_tools: list[str] = []
    system = """
You are a personal knowledge assistant. For simple greetings or conversational messages
(e.g. "hello", "thanks", "how are you"), respond naturally without searching.
For questions about specific topics, notes, or information, use the search_knowledge_base
tool to find relevant saved content and cite sources inline like [1].
If the saved context is insufficient, say what is missing.
""".strip()

    for turn_index in range(MAX_AGENT_TURNS):
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1200,
            temperature=0.1,
            system=system,
            tools=CHAT_TOOLS,
            tool_choice={"type": "auto"},
            messages=messages,
        )
        messages.append(
            {"role": "assistant", "content": _message_content_to_params(response.content)}
        )
        tool_uses = [
            block for block in response.content if getattr(block, "type", None) == "tool_use"
        ]
        if not tool_uses:
            return _text_from_content(response.content), used_tools

        tool_results: list[dict[str, Any]] = []
        for tool_use in tool_uses:
            tool_name = str(getattr(tool_use, "name", ""))
            tool_input = getattr(tool_use, "input", {}) or {}
            if tool_name:
                used_tools.append(tool_name)
            try:
                result = execute_tool(tool_name, dict(tool_input))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result),
                    }
                )
            except Exception as exc:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "is_error": True,
                        "content": str(exc),
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    final_response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=800,
        temperature=0.1,
        system=system,
        messages=messages
        + [
            {
                "role": "user",
                "content": (
                    "Answer now using the tool results already provided. If they are "
                    "insufficient, say what saved context is missing."
                ),
            }
        ],
    )
    return _text_from_content(final_response.content), used_tools



def stream_with_tools(
    message: str,
    execute_tool: Callable[[str, dict[str, Any]], dict[str, Any]],
) -> Generator[dict[str, Any], None, None]:
    """Stream the AI response token-by-token via a generator of SSE-compatible dicts.

    Yields:
        {"type": "tool_call", "name": "<tool_name>"}  – when a tool fires
        {"type": "text",      "text": "<chunk>"}       – streamed text tokens
        {"type": "done"}                               – end-of-stream sentinel
    """
    client = _client()
    if client is None:
        raise ValueError("ANTHROPIC_API_KEY is required for streaming.")

    messages: list[dict[str, Any]] = [{"role": "user", "content": message}]
    system = """
You are a personal knowledge assistant. For simple greetings or conversational messages
(e.g. "hello", "thanks", "how are you"), respond naturally without searching.
For questions about specific topics, notes, or information, use the search_knowledge_base
tool to find relevant saved content and cite sources inline like [1].
If the saved context is insufficient, say what is missing.
""".strip()

    for _turn in range(MAX_AGENT_TURNS):
        with client.messages.stream(
            model=MODEL_NAME,
            max_tokens=1200,
            temperature=0.1,
            system=system,
            tools=CHAT_TOOLS,
            tool_choice={"type": "auto"},
            messages=messages,
        ) as stream:
            for text_chunk in stream.text_stream:
                yield {"type": "text", "text": text_chunk}
            final_msg = stream.get_final_message()

        messages.append(
            {"role": "assistant", "content": _message_content_to_params(final_msg.content)}
        )

        tool_uses = [
            block for block in final_msg.content if getattr(block, "type", None) == "tool_use"
        ]
        if not tool_uses:
            # Text was already streamed above; we're done.
            break

        # Execute each tool and feed results back.
        tool_results: list[dict[str, Any]] = []
        for tool_use in tool_uses:
            tool_name = str(getattr(tool_use, "name", ""))
            tool_input = getattr(tool_use, "input", {}) or {}
            yield {"type": "tool_call", "name": tool_name}
            try:
                result = execute_tool(tool_name, dict(tool_input))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result),
                    }
                )
            except Exception as exc:
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "is_error": True,
                        "content": str(exc),
                    }
                )
        messages.append({"role": "user", "content": tool_results})

    yield {"type": "done"}

