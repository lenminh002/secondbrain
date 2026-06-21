from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from embeddings import current_embedding_model, embed_texts
from extractors import extract_pdf_text
from knowledge_ai import enrich_content
from storage import (
    append_source,
    commit_source_artifacts,
    save_source_result,
)

SOURCE_TYPES = {"note", "pdf", "youtube"}
ACTIVE_SOURCE_TYPES = {"note", "pdf"}
VIDEO_DEFERRED_MESSAGE = "Video ingestion is currently disabled and to be fixed."


class VideoIngestionDeferred(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _chunk_sections(
    sections: list[tuple[str, str]],
    source: dict[str, Any],
    max_chars: int = 1400,
) -> list[dict[str, Any]]:
    """Chunk labeled text sections into ≤max_chars pieces, preserving section names."""
    chunks: list[dict[str, Any]] = []
    for section_name, text in sections:
        body = text.strip()
        if not body:
            continue
        for start in range(0, len(body), max_chars):
            piece = body[start : start + max_chars].strip()
            if piece:
                chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "source_id": source["id"],
                        "source_title": source["title"],
                        "section": section_name,
                        "text": piece,
                        "embedding": [],
                    }
                )
    return chunks


def _replace_source_artifacts(source: dict[str, Any], content: str, enrichment: dict[str, Any]) -> None:
    account_id = str(source["account_id"])
    sections = [
        ("Summary", enrichment["summary"]),
        ("Key Ideas", "\n".join(enrichment["key_ideas"])),
        ("Notes", content),
        ("Concepts", "\n".join(enrichment["concepts"])),
        ("Claims", "\n".join(enrichment["claims"])),
        ("Questions", "\n".join(enrichment["questions"])),
    ]
    chunks = _chunk_sections(sections, source)
    embeddings = embed_texts([chunk["text"] for chunk in chunks]) if chunks else []
    embedding_model = current_embedding_model()
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding
        chunk["embedding_model"] = embedding_model
        chunk["embedding_dim"] = len(embedding)

    post = {
        "id": str(uuid.uuid4()),
        "account_id": account_id,
        "source_id": source["id"],
        "source_title": source["title"],
        "body": enrichment["social_post"],
        "created_at": now_iso(),
    }
    commit_source_artifacts(
        account_id,
        source,
        chunks,
        post,
        enrichment["concepts"],
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
    account_id: str,
    source_type: str,
    title: str | None = None,
    text: str | None = None,
    source_url: str | None = None,
    file_bytes: bytes | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    account_id = account_id.strip()
    if not account_id:
        raise ValueError("Account ID is required.")
    validate_source_input(
        source_type=source_type,
        text=text,
        source_url=source_url,
        file_bytes=file_bytes,
    )

    source = {
        "id": str(uuid.uuid4()),
        "account_id": account_id,
        "type": source_type,
        "title": (title or filename or source_url or "Untitled source").strip(),
        "source_url": source_url,
        "status": "processing",
        "error": None,
        "created_at": now_iso(),
    }
    append_source(account_id, source)

    try:
        if source_type == "note":
            content = (text or "").strip()
        else:
            content = extract_pdf_text(file_bytes or b"")
            if not title and filename:
                source["title"] = filename.rsplit(".", 1)[0]

        enrichment = enrich_content(source_type, source["title"], source_url, content)

        # Persist raw content and structured enrichment on the source record
        source["content"] = content
        source["summary"] = enrichment["summary"]
        source["key_ideas"] = enrichment["key_ideas"]
        source["concepts"] = enrichment["concepts"]
        source["claims"] = enrichment["claims"]
        source["questions"] = enrichment["questions"]

        _replace_source_artifacts(source, content, enrichment)
        source["status"] = "ready"
    except Exception as exc:
        source["status"] = "failed"
        source["error"] = str(exc)

    save_source_result(account_id, source)
    return source
