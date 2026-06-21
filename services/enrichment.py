from __future__ import annotations

import json
import re
from typing import Any

from services.anthropic_client import MODEL_NAME, _client, _text_from_content


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
        "tags": [],
    }


def enrich_content(
    source_type: str,
    title: str,
    source_url: str | None,
    content: str,
    existing_tags: list[str] | None = None,
) -> dict[str, Any]:
    client = _client()
    if client is None:
        return _fallback_enrichment(title, content)

    existing_tags = existing_tags or []
    existing_tags_str = ", ".join(existing_tags) if existing_tags else "none yet"

    prompt = f"""
You are turning a consumed knowledge source into a personal knowledge-base entry.

Source type: {source_type}
Title: {title}
Source URL: {source_url or "none"}

Existing tags already in the knowledge base: {existing_tags_str}

Return ONLY valid JSON in this shape:
{{
  "summary": "one concise paragraph",
  "key_ideas": ["short bullet"],
  "concepts": ["canonical concept/entity name"],
  "claims": ["claim or useful assertion"],
  "questions": ["open question for future learning"],
  "social_post": "one social-media style post in first person, under 900 characters",
  "tags": ["broad-topic-tag"]
}}

Tags rules (IMPORTANT):
- Choose 2–4 broad topic tags for this source.
- PREFER exact or near-exact matches from the existing tags list above. Reuse them.
- Only create a new tag if no existing tag captures the topic. Max 1–2 new tags per source.
- Tags must be specific topics, not meta-descriptions. Bad: "interesting", "note", "new", "content", "file". Good: "machine-learning", "productivity", "cognitive-science", "distributed-systems".
- Use lowercase kebab-case for new tags.

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
        "tags": _as_string_list(parsed.get("tags"), limit=4),
    }
