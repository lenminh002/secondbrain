from __future__ import annotations

import json
import re
from typing import Any

from backend.services.anthropic_client import MODEL_NAME, _client, _text_from_content


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


def _extract_tag_content(text: str, tag: str) -> str:
    start_tag = f"<{tag}>"
    end_tag = f"</{tag}>"
    start_idx = text.find(start_tag)
    if start_idx == -1:
        return ""
    end_idx = text.find(end_tag, start_idx + len(start_tag))
    if end_idx == -1:
        return text[start_idx + len(start_tag):].strip()
    return text[start_idx + len(start_tag):end_idx].strip()


def _extract_list_from_tag(text: str, tag: str) -> list[str]:
    content = _extract_tag_content(text, tag)
    if not content:
        return []
    lines = [line.strip().lstrip("-*•").strip() for line in content.split("\n")]
    return [line for line in lines if line]


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
        "social_post": f"Insights from '{title}': {summary[:600]}",
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

Please analyze the content and wrap your outputs in the following XML-like tags:

<summary>
one concise paragraph summarizing the source.
</summary>

<key_ideas>
- short bullet point 1
- short bullet point 2
</key_ideas>

<concepts>
- canonical concept or entity name 1
- canonical concept or entity name 2
</concepts>

<claims>
- claim or useful assertion 1
- claim or useful assertion 2
</claims>

<questions>
- open question for future learning 1
</questions>

<social_post>
A structured, recall-friendly study guide in clean Markdown that captures the document’s main argument, workflow, key details, mental models, and practical uses. Follow this exact Markdown structure (do NOT wrap the entire string in a code fence):
# Full Recall Summary

## 1. One-sentence summary
> This document says: **[main idea in plain language].**

## 2. Memory hook
> **[Short memory hook phrase, acronym, or simple chain]**
[Brief explanation of the hook]

## 3. Big picture
- What problem is it trying to solve?
- What is the main method, argument, or framework?
- Why does it matter?

## 4. Section-by-section breakdown
Preserve the document's structure (phases, chapters, slides, pages, or steps).
### [Section name]
**Main idea:** [1-3 clear sentences]
**What to remember:** [bullet points]
**Why it matters:** [purpose]

## 5. Key concepts explained simply
For each important term:
**[Concept]**
- Simple explanation:
- Example:
- Why it matters:

## 6. The workflow / process
If the document teaches a method, convert it into a Markdown table with columns: | Step | What to do | Output |
If no workflow exists, write 'No direct workflow, but the logic is:' and explain the flow of ideas.

## 7. Main lessons
Rank by importance. State the lesson, explain it simply, and say where/how the user can apply it.

## 8. Practical uses
Explain how the user can use the information in real life, school, coding, business, research, or projects with concrete examples.

## 9. What people usually misunderstand
**Misunderstanding:** [common trap]
**Correct understanding:** [correct explanation]

## 10. Quick recall version
> **[Topic] = [core idea].**
> Remember: **A -> B -> C -> D.**

## 11. Active recall questions
Create 8-15 short questions with answers that test understanding.
**Q1. [Question]**
A: [Answer]

## 12. Final cheat sheet
A Markdown table or list containing the main idea, key terms, key steps, main warning, and best use case.
</social_post>

<tags>
- broad-topic-tag-1
- broad-topic-tag-2
</tags>

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
        response_text = _text_from_content(message.content)
        
        summary = _extract_tag_content(response_text, "summary")
        if not summary:
            raise ValueError("Failed to extract summary from XML response.")
            
        key_ideas = _extract_list_from_tag(response_text, "key_ideas")
        concepts = _extract_list_from_tag(response_text, "concepts")
        claims = _extract_list_from_tag(response_text, "claims")
        questions = _extract_list_from_tag(response_text, "questions")
        social_post = _extract_tag_content(response_text, "social_post")
        tags = _extract_list_from_tag(response_text, "tags")
        
        parsed = {
            "summary": summary,
            "key_ideas": key_ideas,
            "concepts": concepts,
            "claims": claims,
            "questions": questions,
            "social_post": social_post,
            "tags": tags,
        }
    except Exception:
        # Degrading to rule-based fallback if model fails
        return _fallback_enrichment(title, content)

    fallback = _fallback_enrichment(title, content)
    return {
        "summary": parsed.get("summary", "").strip() or fallback["summary"],
        "key_ideas": parsed.get("key_ideas") or fallback["key_ideas"],
        "concepts": parsed.get("concepts") or fallback["concepts"],
        "claims": parsed.get("claims") or fallback["claims"],
        "questions": parsed.get("questions") or fallback["questions"],
        "social_post": parsed.get("social_post", "").strip() or fallback["social_post"],
        "tags": parsed.get("tags") or fallback["tags"],
    }


def scrape_html_to_markdown(url: str, html_content: str) -> str:
    client = _client()
    if client is None:
        return f"# Scraped Content from {url}\n\n{html_content[:2000]}"

    prompt = f"""
You are turning a scraped web page into a clean Markdown document for a personal knowledge base.

URL: {url}

Return ONLY the clean Markdown content representing the page.
Guidelines:
- Extract the core page/tweet body, title, author, date/timestamp, and any replies/metrics if it's a social post.
- Omit boilerplate, sidebars, navigation panels, advertisements, headers, and footers.
- Do NOT wrap your output in code blocks (like ```markdown) or write any meta-talk/preface/afterword. Start directly with the document title or content.

Scraped Content:
{html_content[:40000]}
""".strip()

    try:
        message = client.messages.create(
            model=MODEL_NAME,
            max_tokens=4000,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        return _text_from_content(message.content)
    except Exception as exc:
        return f"# Scraped Content from {url}\n\nError processing with Claude: {exc}\n\nRaw text snippet:\n\n{html_content[:1500]}"

