from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from backend.embeddings import current_embedding_model, embed_texts
from backend.extractors import extract_pdf_text
from backend.file_storage import store_original_file, store_original_markdown_file
from backend.services.enrichment import enrich_content

from backend.storage import (
    append_source,
    commit_source_artifacts,
    load_graph,
    save_source_result,
)

SOURCE_TYPES = {"note", "pdf", "link"}
INGEST_PROGRESS: dict[str, tuple[str, int]] = {
    "validating": ("Validating source", 5),
    "uploading": ("Uploading source file", 15),
    "reading_text": ("Reading note text", 20),
    "extracting": ("Extracting source text", 25),
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


def upload_pdf_to_drive(file_bytes: bytes, filename: str | None) -> dict[str, Any]:
    return store_original_file(file_bytes, filename)


def upload_markdown_to_drive(file_bytes: bytes, filename: str | None) -> dict[str, Any]:
    return store_original_markdown_file(file_bytes, filename)


def _enrich_content(
    source_type: str,
    title: str,
    source_url: str | None,
    content: str,
    existing_tags: list[str],
) -> dict[str, Any]:
    try:
        return enrich_content(
            source_type,
            title,
            source_url,
            content,
            existing_tags=existing_tags,
        )
    except TypeError as exc:
        if "existing_tags" not in str(exc):
            raise
        return enrich_content(source_type, title, source_url, content)


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

    body_parts = []
    if enrichment.get("summary"):
        body_parts.append(f"# Summary\n{enrichment['summary']}")
    if enrichment.get("key_ideas"):
        ideas_list = "\n".join(f"- {idea}" for idea in enrichment["key_ideas"])
        body_parts.append(f"## Key Ideas & Notes\n{ideas_list}")
    if enrichment.get("concepts"):
        concepts_list = ", ".join(f"**{concept}**" for concept in enrichment["concepts"])
        body_parts.append(f"## Key Concepts\n{concepts_list}")
    if enrichment.get("social_post"):
        body_parts.append(f"---\n{enrichment['social_post']}")
    post_body = "\n\n".join(body_parts)

    post = {
        "id": str(uuid.uuid4()),
        "account_id": account_id,
        "source_id": source["id"],
        "source_title": source["title"],
        "body": post_body,
        "created_at": now_iso(),
    }
    if source.get("thumbnail_url"):
        post["thumbnail_url"] = source["thumbnail_url"]
    
    raw_concepts = enrichment.get("concepts", [])
    concept_embeddings = embed_texts(raw_concepts) if raw_concepts else []
    embedded_concepts = [
        {"label": label, "embedding": emb} 
        for label, emb in zip(raw_concepts, concept_embeddings)
    ]
    
    _set_progress(source, "graphing")
    commit_source_artifacts(
        account_id,
        source,
        chunks,
        post,
        embedded_concepts,
        tags=enrichment.get("tags", []),
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
    # GitHub backend returns web_view_link; Drive returns drive_web_view_link.
    source["source_url"] = original_file.get("web_view_link") or original_file.get(
        "drive_web_view_link"
    )


def validate_source_input(
    source_type: str,
    text: str | None = None,
    source_url: str | None = None,
    file_bytes: bytes | None = None,
) -> None:
    if source_type not in SOURCE_TYPES:
        raise ValueError("Source type must be note, pdf, or link.")
    if source_type == "note" and not (text or "").strip():
        raise ValueError("Note text is required.")
    if source_type == "pdf" and not file_bytes:
        raise ValueError("PDF upload is required.")
    if source_type == "link" and not (source_url or "").strip():
        raise ValueError("Source URL is required for link type.")



def create_processing_source(
    account_id: str,
    source_type: str,
    title: str | None = None,
    text: str | None = None,
    source_url: str | None = None,
    thumbnail_url: str | None = None,
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
        "thumbnail_url": thumbnail_url,
        "status": "processing",
        "error": None,
        "created_at": now_iso(),
    }
    _set_progress(source, "validating", persist=False)
    append_source(account_id, source)
    return source


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
            _set_progress(source, "uploading")
            url_to_scrape = source_url or source.get("source_url") or ""
            if not url_to_scrape:
                raise ValueError("Source URL is required for link type.")

            from backend.extractors import scrape_url_to_html
            from backend.services.enrichment import scrape_html_to_markdown

            html_content = scrape_url_to_html(url_to_scrape)
            markdown_content = scrape_html_to_markdown(url_to_scrape, html_content)

            domain = ""
            if "://" in url_to_scrape:
                domain = url_to_scrape.split("://")[1].split("/")[0]
            md_filename = f"scraped-{domain or 'site'}-{uuid.uuid4().hex[:8]}.md"

            metadata = upload_markdown_to_drive(markdown_content.encode("utf-8"), md_filename)
            _attach_original_file_metadata(source, metadata)

            content = markdown_content

            first_line = markdown_content.strip().split("\n")[0]
            if first_line.startswith("# ") and source["title"] in {"Untitled source", md_filename, url_to_scrape}:
                source["title"] = first_line.lstrip("# ").strip()

            _set_progress(source, "extracting")
        else:
            pdf_bytes = file_bytes or b""
            _set_progress(source, "uploading")
            _attach_original_file_metadata(
                source,
                upload_pdf_to_drive(pdf_bytes, filename),
            )
            _set_progress(source, "extracting")
            content = extract_pdf_text(pdf_bytes)
            if filename and source["title"] in {"Untitled source", filename}:
                source["title"] = filename.rsplit(".", 1)[0]

        _set_progress(source, "enriching")
        existing_graph = load_graph(account_id)
        existing_tags = [n["label"] for n in existing_graph.get("nodes", []) if n.get("type") == "tag"]
        enrichment = _enrich_content(
            source_type,
            source["title"],
            source.get("source_url") or source_url,
            content,
            existing_tags,
        )

        # Persist raw content and structured enrichment on the source record
        source["content"] = content
        source["summary"] = enrichment["summary"]
        source["key_ideas"] = enrichment["key_ideas"]
        source["concepts"] = enrichment["concepts"]
        source["claims"] = enrichment["claims"]
        source["questions"] = enrichment["questions"]
        source["tags"] = enrichment.get("tags", [])

        _replace_source_artifacts(source, content, enrichment)
        source["status"] = "ready"
        _set_progress(source, "complete")
    except Exception as exc:
        source["status"] = "failed"
        source["error"] = str(exc)
        save_source_result(account_id, source)

    return source


def edit_source_content(source: dict[str, Any], content: str) -> dict[str, Any]:
    content = content.strip()
    if not content:
        raise ValueError("Memory content is required.")
    if source.get("status") != "ready":
        raise RuntimeError("Only ready memories can be edited.")

    source_type = str(source["type"])
    source["error"] = None
    _set_progress(source, "enriching")
    existing_graph = load_graph(str(source["account_id"]))
    existing_tags = [n["label"] for n in existing_graph.get("nodes", []) if n.get("type") == "tag"]
    enrichment = _enrich_content(
        source_type,
        str(source.get("title") or "Untitled source"),
        source.get("source_url"),
        content,
        existing_tags,
    )

    source["content"] = content
    source["summary"] = enrichment["summary"]
    source["key_ideas"] = enrichment["key_ideas"]
    source["concepts"] = enrichment["concepts"]
    source["claims"] = enrichment["claims"]
    source["questions"] = enrichment["questions"]
    source["tags"] = enrichment.get("tags", [])

    _replace_source_artifacts(source, content, enrichment)
    source["status"] = "ready"
    _set_progress(source, "complete")
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
