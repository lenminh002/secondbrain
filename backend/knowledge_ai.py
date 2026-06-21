from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable
from typing import Any

from anthropic import Anthropic, APIStatusError, RateLimitError

logger = logging.getLogger(__name__)

# Substrings that mark a credential/usage limit worth failing over for. Anthropic
# returns 429 for rate limits but 400 for an exhausted credit balance, so we match
# on the message too rather than the status code alone.
_LIMIT_HINTS = ("credit balance", "quota", "billing", "rate limit", "usage limit", "insufficient")


def _is_limit_error(exc: Exception) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        message = str(getattr(exc, "message", "") or exc).lower()
        return any(hint in message for hint in _LIMIT_HINTS)
    return False

MODEL_NAME = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MAX_AGENT_TURNS = 3

# After the primary credential is rate-limited, prefer the fallback for this long
# before retrying the primary, so an agent run making many calls doesn't keep
# hammering a limited key.
_PRIMARY_COOLDOWN_SECONDS = 60

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
    {
        "name": "create_note",
        "description": (
            "Create and save a new note in the user's knowledge base. Use this when the "
            "user asks to add, create, write, or save a note. The note is saved immediately."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "A short title for the note."},
                "text": {"type": "string", "description": "The full note body content."},
            },
            "required": ["title", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_delete_source",
        "description": (
            "Propose deleting a saved source (note or PDF). This does NOT delete anything; "
            "it asks the user to confirm first. Use when the user asks to delete or remove a "
            "source. Prefer the source_id from search_knowledge_base; otherwise pass a title."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "description": "The source_id to delete."},
                "title": {"type": "string", "description": "A title to match if the id is unknown."},
            },
            "required": [],
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


MEMORY_POST_TYPES = ["summary", "quiz", "fill_blank", "explain_simple", "reflection"]


def _fallback_memory_posts(text: str) -> list[dict[str, str]]:
    snippet = " ".join(text.split())[:280]
    if not snippet:
        return []
    return [{"type": "summary", "body": snippet}]


def generate_memory_posts(
    source_title: str,
    chunks: list[dict[str, Any]],
    *,
    max_chunks: int = 12,
) -> list[dict[str, str]]:
    """Turn source chunks into learning posts (summary/quiz/fill_blank/...).

    Returns a flat list of {"type", "body"} dicts. One Claude call per chunk so a
    single failing chunk can be skipped without losing the rest. Capped at
    ``max_chunks`` to keep hackathon runs fast and cheap.
    """
    client = _client()
    posts: list[dict[str, str]] = []
    for chunk in chunks[:max_chunks]:
        text = str(chunk.get("text", "")).strip()
        if not text:
            continue
        if client is None:
            posts.extend(_fallback_memory_posts(text))
            continue
        prompt = f"""
You are creating spaced-repetition study posts from one passage of "{source_title}".

Return ONLY a JSON array. Each item:
{{"type": one of {MEMORY_POST_TYPES}, "body": "the post text"}}

Create 2-3 varied posts grounded strictly in the passage. Use a fill_blank as
"sentence with ____" and a quiz as a question (optionally with the answer).

Passage:
{text[:4000]}
""".strip()
        try:
            message = client.messages.create(
                model=MODEL_NAME,
                max_tokens=900,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = json.loads(_strip_code_fence(_text_from_content(message.content)))
            if not isinstance(parsed, list):
                raise ValueError("memory posts response was not a JSON array")
        except Exception:
            # Skip this chunk and continue with the rest.
            continue
        for item in parsed:
            if not isinstance(item, dict):
                continue
            post_type = str(item.get("type", "")).strip().lower()
            body = str(item.get("body", "")).strip()
            if body and post_type in MEMORY_POST_TYPES:
                posts.append({"type": post_type, "body": body})
    return posts


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


class _ResilientMessages:
    def __init__(self, owner: "ResilientAnthropic") -> None:
        self._owner = owner

    def create(self, **kwargs: Any) -> Any:
        return self._owner._create(**kwargs)


class ResilientAnthropic:
    """Anthropic client that falls back to a backup credential on rate limits.

    ``primary`` uses ``ANTHROPIC_API_KEY``; ``fallback`` uses ``CLAUDE_OAUTH_TOKEN``
    (Bearer auth). On a ``RateLimitError`` from the primary we switch to the
    fallback and keep preferring it for a short cooldown. Exposes the same
    ``.messages.create(...)`` surface as ``anthropic.Anthropic`` so callers and the
    agent loop need no changes.
    """

    def __init__(self, primary: Anthropic | None, fallback: Anthropic | None) -> None:
        self._primary = primary
        self._fallback = fallback
        self._primary_blocked_until = 0.0
        self.messages = _ResilientMessages(self)

    def _create(self, **kwargs: Any) -> Any:
        use_primary = self._primary is not None and time.monotonic() >= self._primary_blocked_until
        if use_primary:
            try:
                return self._primary.messages.create(**kwargs)
            except Exception as exc:
                if self._fallback is None or not _is_limit_error(exc):
                    raise
                self._primary_blocked_until = time.monotonic() + _PRIMARY_COOLDOWN_SECONDS
                logger.warning(
                    "ANTHROPIC_API_KEY hit a limit (%s); switching to CLAUDE_OAUTH_TOKEN fallback.",
                    type(exc).__name__,
                )
        client = self._fallback if self._fallback is not None else self._primary
        if client is None:
            raise ValueError("No Anthropic credential is configured.")
        return client.messages.create(**kwargs)


def _client() -> ResilientAnthropic | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    oauth_token = os.getenv("CLAUDE_OAUTH_TOKEN")
    primary = Anthropic(api_key=api_key) if api_key else None
    fallback = Anthropic(auth_token=oauth_token) if oauth_token else None
    if primary is None and fallback is None:
        return None
    return ResilientAnthropic(primary, fallback)


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
You are a personal assistant for the user's saved knowledge base. You can answer
questions, create notes, and propose deletions.

- For questions, answer only from tool results as your source of truth. If the saved
  context is insufficient, say what is missing. Cite sources inline with the citation
  indexes from tool results, like [1].
- When the user asks to add or save a note, call create_note. Confirm what you saved.
- When the user asks to delete or remove something, call propose_delete_source. This
  does not delete immediately; the user must confirm in the UI. Tell them you have
  queued the deletion for confirmation and name the source.
""".strip()

    for turn_index in range(MAX_AGENT_TURNS):
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1200,
            temperature=0.1,
            system=system,
            tools=CHAT_TOOLS,
            tool_choice={
                "type": "tool",
                "name": "search_knowledge_base",
            }
            if turn_index == 0
            else {"type": "auto"},
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
