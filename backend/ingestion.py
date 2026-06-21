from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from config import get_settings
from embeddings import current_embedding_model, embed_texts
from extractors import extract_pdf_text
from file_storage import store_original_file
from knowledge_ai import _client as _anthropic_client
from knowledge_ai import enrich_content
from storage import (
    append_source,
    commit_source_artifacts,
    load_sources,
    save_source_result,
)

SOURCE_TYPES = {"note", "pdf", "link", "youtube"}
ACTIVE_SOURCE_TYPES = {"note", "pdf", "link"}
VIDEO_DEFERRED_MESSAGE = "Video ingestion is currently disabled and to be fixed."
INGEST_PROGRESS: dict[str, tuple[str, int]] = {
    "validating": ("Validating source", 5),
    "uploading": ("Uploading original PDF", 15),
    "reading_text": ("Reading note text", 20),
    "extracting": ("Extracting PDF text", 25),
    "enriching": ("Generating structured memory", 45),
    "embedding": ("Creating retrieval chunks", 70),
    "graphing": ("Updating knowledge graph", 90),
    "complete": ("Ingestion complete", 100),
}

ProgressStage = Literal[
    "validating",
    "uploading",
    "reading_text",
    "extracting",
    "enriching",
    "embedding",
    "graphing",
    "complete",
]


class VideoIngestionDeferred(ValueError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_progress(source: dict[str, Any], stage: ProgressStage, *, persist: bool = True) -> None:
    label, percent = INGEST_PROGRESS[stage]
    source["progress_stage"] = stage
    source["progress_label"] = label
    source["progress_percent"] = percent
    if persist:
        save_source_result(str(source["account_id"]), source)


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
    _set_progress(source, "embedding")
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
    _set_progress(source, "graphing")
    commit_source_artifacts(
        account_id,
        source,
        chunks,
        post,
        enrichment["concepts"],
    )


def _attach_original_file_metadata(
    source: dict[str, Any],
    original_file: dict[str, Any],
) -> None:
    metadata = source.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["original_file"] = original_file
    source["metadata"] = metadata
    source["source_url"] = original_file.get("web_view_link")


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
        raise ValueError("Source type must be note, pdf, or link.")
    if source_type == "note" and not (text or "").strip():
        raise ValueError("Note text is required.")
    if source_type == "pdf" and not file_bytes:
        raise ValueError("PDF upload is required.")
    if source_type == "link" and not (source_url or "").strip():
        raise ValueError("Link URL is required.")


def create_processing_source(
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
    _set_progress(source, "validating", persist=False)
    append_source(account_id, source)
    return source


def _agent_pdf_enabled() -> bool:
    settings = get_settings()
    return (
        settings.agent_enabled
        and settings.agent_processing_mode == "agent"
        and _anthropic_client() is not None
    )


def _reload_source(account_id: str, source_id: str, fallback: dict[str, Any]) -> dict[str, Any]:
    for source in load_sources(account_id):
        if str(source.get("id")) == str(source_id):
            return source
    return fallback


def _process_pdf_with_agent(
    source: dict[str, Any],
    pdf_bytes: bytes,
) -> dict[str, Any]:
    # Import here to avoid importing the Anthropic-dependent agent module unless
    # the agentic path is actually taken.
    from agent import KnowledgeLibrarianAgent

    account_id = str(source["account_id"])
    source["processing_mode"] = "agent"
    save_source_result(account_id, source)
    KnowledgeLibrarianAgent().process_pdf_with_agent(
        account_id=account_id,
        source_id=str(source["id"]),
        file_bytes=pdf_bytes,
        title=str(source["title"]),
    )
    return _reload_source(account_id, str(source["id"]), source)


def process_source(
    source: dict[str, Any],
    text: str | None = None,
    source_url: str | None = None,
    file_bytes: bytes | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    account_id = str(source["account_id"])
    source_type = str(source["type"])
    try:
        if source_type == "note":
            _set_progress(source, "reading_text")
            content = (text or "").strip()
        elif source_type == "link":
            _set_progress(source, "reading_text")
            content = (source.get("source_url") or source_url or "").strip()
        else:
            pdf_bytes = file_bytes or b""
            _set_progress(source, "uploading")
            _attach_original_file_metadata(
                source,
                store_original_file(pdf_bytes, filename),
            )
            if filename and source["title"] in {"Untitled source", filename}:
                source["title"] = filename.rsplit(".", 1)[0]

            # Agentic path: Claude drives the rest of PDF processing via tools.
            if _agent_pdf_enabled():
                return _process_pdf_with_agent(source, pdf_bytes)

            _set_progress(source, "extracting")
            content = extract_pdf_text(pdf_bytes)

        _set_progress(source, "enriching")
        enrichment = enrich_content(source_type, source["title"], source.get("source_url") or source_url, content)

        # Persist raw content and structured enrichment on the source record
        source["content"] = content
        source["summary"] = enrichment["summary"]
        source["key_ideas"] = enrichment["key_ideas"]
        source["concepts"] = enrichment["concepts"]
        source["claims"] = enrichment["claims"]
        source["questions"] = enrichment["questions"]

        _replace_source_artifacts(source, content, enrichment)
        source["status"] = "ready"
        _set_progress(source, "complete")
    except Exception as exc:
        source["status"] = "failed"
        source["error"] = str(exc)
        save_source_result(account_id, source)

    return source


def ingest_source(
    account_id: str,
    source_type: str,
    title: str | None = None,
    text: str | None = None,
    source_url: str | None = None,
    file_bytes: bytes | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    source = create_processing_source(
        account_id=account_id,
        source_type=source_type,
        title=title,
        text=text,
        source_url=source_url,
        file_bytes=file_bytes,
        filename=filename,
    )
    return process_source(
        source,
        text=text,
        source_url=source_url,
        file_bytes=file_bytes,
        filename=filename,
    )
