from __future__ import annotations

import json
import os
import re
from typing import Any

from anthropic import Anthropic

MODEL_NAME = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL | re.IGNORECASE)
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
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
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

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1800,
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = "".join(
        block.text for block in message.content if getattr(block, "type", None) == "text"
    )
    parsed = json.loads(_strip_code_fence(response_text))
    if not isinstance(parsed, dict):
        raise ValueError("Claude enrichment response was not a JSON object.")
    return {
        "summary": str(parsed.get("summary", "")).strip() or _fallback_enrichment(title, content)["summary"],
        "key_ideas": _as_string_list(parsed.get("key_ideas")),
        "concepts": _as_string_list(parsed.get("concepts")),
        "claims": _as_string_list(parsed.get("claims")),
        "questions": _as_string_list(parsed.get("questions")),
        "social_post": str(parsed.get("social_post", "")).strip()
        or _fallback_enrichment(title, content)["social_post"],
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
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
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
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1200,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if getattr(block, "type", None) == "text").strip()
