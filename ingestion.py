from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from embeddings import current_embedding_model, embed_texts
from extractors import extract_pdf_text
from knowledge_ai import enrich_content
from storage import (
    append_source,
    commit_source_artifacts,
    get_default_account,
    save_source_result,
)

SOURCE_TYPES = {"note", "pdf", "youtube"}
ACTIVE_SOURCE_TYPES = {"note", "pdf"}
VIDEO_DEFERRED_MESSAGE = "Video ingestion is currently disabled and to be fixed."


class VideoIngestionDeferred(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None captured"


def _canonical_markdown(
    source: dict[str, Any],
    content: str,
    enrichment: dict[str, Any],
) -> str:
    source_url = source.get("source_url") or ""
    return f"""---
id: "{source["id"]}"
type: "{source["type"]}"
title: "{source["title"]}"
source_url: "{source_url}"
created_at: "{source["created_at"]}"
---

# Summary

{enrichment["summary"]}

# Key Ideas

{_markdown_list(enrichment["key_ideas"])}

# Notes

{content.strip()}

# Concepts

{_markdown_list(enrichment["concepts"])}

# Claims

{_markdown_list(enrichment["claims"])}

# Questions

{_markdown_list(enrichment["questions"])}
"""


def _chunk_markdown(markdown: str, source: dict[str, Any], max_chars: int = 1400) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current_section = "Document"
    buffer: list[str] = []

    def flush() -> None:
        joined = "\n".join(buffer).strip()
        if not joined:
            return
        for start in range(0, len(joined), max_chars):
            text = joined[start : start + max_chars].strip()
            if text:
                chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "source_id": source["id"],
                        "source_title": source["title"],
                        "section": current_section,
                        "text": text,
                        "embedding": [],
                    }
                )

    for line in markdown.splitlines():
        heading = re.match(r"^#\s+(.+)$", line)
        if heading:
            flush()
            buffer = []
            current_section = heading.group(1).strip()
            continue
        buffer.append(line)
    flush()
    return chunks


def _replace_source_artifacts(source: dict[str, Any], markdown: str, enrichment: dict[str, Any]) -> None:
    chunks = _chunk_markdown(markdown, source)
    embeddings = embed_texts([chunk["text"] for chunk in chunks]) if chunks else []
    embedding_model = current_embedding_model()
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding
        chunk["embedding_model"] = embedding_model
        chunk["embedding_dim"] = len(embedding)

    post = {
        "id": str(uuid.uuid4()),
        "account_id": get_default_account()["id"],
        "source_id": source["id"],
        "source_title": source["title"],
        "body": enrichment["social_post"],
        "created_at": now_iso(),
    }
    commit_source_artifacts(
        source,
        chunks,
        post,
        enrichment["concepts"],
        markdown,
    )


def validate_source_input(
    source_type: str,
    text: str | None = None,
    source_url: str | None = None,
    file_bytes: bytes | None = None,
) -> None:
    if source_type not in SOURCE_TYPES:
        raise ValueError("Source type must be one of note, pdf, or youtube.")
    if source_type == "youtube":
        raise VideoIngestionDeferred(VIDEO_DEFERRED_MESSAGE)
    if source_type not in ACTIVE_SOURCE_TYPES:
        raise ValueError("Source type must be note or pdf.")
    if source_type == "note" and not (text or "").strip():
        raise ValueError("Note text is required.")
    if source_type == "pdf" and not file_bytes:
        raise ValueError("PDF upload is required.")


def ingest_source(
    source_type: str,
    title: str | None = None,
    text: str | None = None,
    source_url: str | None = None,
    file_bytes: bytes | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    validate_source_input(
        source_type=source_type,
        text=text,
        source_url=source_url,
        file_bytes=file_bytes,
    )

    source = {
        "id": str(uuid.uuid4()),
        "type": source_type,
        "title": (title or filename or source_url or "Untitled source").strip(),
        "source_url": source_url,
        "status": "processing",
        "error": None,
        "created_at": now_iso(),
    }
    append_source(source)

    try:
        if source_type == "note":
            content = (text or "").strip()
        else:
            content = extract_pdf_text(file_bytes or b"")
            if not title and filename:
                source["title"] = filename.rsplit(".", 1)[0]

        enrichment = enrich_content(source_type, source["title"], source_url, content)
        markdown = _canonical_markdown(source, content, enrichment)
        _replace_source_artifacts(source, markdown, enrichment)
        source["status"] = "ready"
    except Exception as exc:
        source["status"] = "failed"
        source["error"] = str(exc)

    save_source_result(source)
    return source
