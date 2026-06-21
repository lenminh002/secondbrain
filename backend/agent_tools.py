from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import storage
from embeddings import current_embedding_model, embed_texts
from extractors import extract_pdf_pages
from knowledge_ai import MEMORY_POST_TYPES, enrich_content, generate_memory_posts
from storage_backends.utils import merge_graph


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _preview(text: str, limit: int = 500) -> str:
    return " ".join(text.split())[:limit]


def _clean_text(text: str) -> str:
    """Collapse whitespace and drop control noise from extracted page text."""
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class KnowledgeAgentTools:
    """Backend tools exposed to the Knowledge Librarian Agent.

    Claude calls these with minimal inputs (typically just ``source_id``); the
    large intermediate data (pages, chunks) lives in ``runtime_state`` so it is
    never echoed back through the model. Every method returns a small, safe
    summary dict — and validates ordering, returning ``{"error": ...}`` when a
    tool is called before its prerequisites exist so Claude can recover.
    """

    def __init__(
        self,
        account_id: str,
        source_id: str,
        source_title: str,
        runtime_state: dict[str, Any],
    ) -> None:
        self.account_id = account_id
        self.source_id = source_id
        self.source_title = source_title
        self.state = runtime_state
        self.state.setdefault("stats", {})

    # --- helpers --------------------------------------------------------

    def _load_source(self) -> dict[str, Any]:
        for source in storage.load_sources(self.account_id):
            if str(source.get("id")) == str(self.source_id):
                return source
        return {
            "id": self.source_id,
            "account_id": self.account_id,
            "type": "pdf",
            "title": self.source_title,
        }

    def _source_ref(self) -> dict[str, Any]:
        return {"id": self.source_id, "title": self.source_title}

    # --- tool 1 ---------------------------------------------------------

    def inspect_source(self, **_: Any) -> dict[str, Any]:
        source = self._load_source()
        original = (source.get("metadata") or {}).get("original_file") or {}
        return {
            "source_id": self.source_id,
            "title": source.get("title", self.source_title),
            "status": source.get("status", "processing"),
            "source_type": source.get("type", "pdf"),
            "drive_file_id": original.get("drive_file_id"),
        }

    # --- tool 2 ---------------------------------------------------------

    def extract_pdf_pages(self, **_: Any) -> dict[str, Any]:
        file_bytes = self.state.get("file_bytes")
        if not file_bytes:
            return {"error": "No PDF bytes are available for this source."}
        pages = extract_pdf_pages(file_bytes)
        self.state["pages"] = pages
        empty_pages = sum(1 for page in pages if not page["text"].strip())
        preview_source = next((page["text"] for page in pages if page["text"].strip()), "")
        self.state["stats"].update({"total_pages": len(pages), "empty_pages": empty_pages})
        return {
            "total_pages": len(pages),
            "empty_pages": empty_pages,
            "text_preview": _preview(preview_source),
        }

    # --- tool 3 ---------------------------------------------------------

    def clean_extracted_pages(self, **_: Any) -> dict[str, Any]:
        pages = self.state.get("pages")
        if not pages:
            return {"error": "Cannot clean pages before extracting PDF pages."}
        cleaned: list[dict[str, Any]] = []
        for page in pages:
            text = _clean_text(str(page.get("text", "")))
            if text:
                cleaned.append({"page": page.get("page"), "text": text})
        self.state["cleaned_pages"] = cleaned
        self.state["full_text"] = "\n\n".join(page["text"] for page in cleaned)
        return {
            "total_pages": len(pages),
            "cleaned_pages": len(cleaned),
            "text_preview": _preview(self.state["full_text"]),
        }

    # --- tool 4 ---------------------------------------------------------

    def chunk_clean_pages(
        self,
        max_tokens: int = 400,
        overlap_tokens: int = 60,
        **_: Any,
    ) -> dict[str, Any]:
        cleaned_pages = self.state.get("cleaned_pages")
        if not cleaned_pages:
            return {"error": "Cannot chunk pages before cleaning extracted pages."}

        # Approximate tokens with characters (~4 chars/token) to keep this
        # dependency-free and predictable for a hackathon.
        window = max(200, int(max_tokens) * 4)
        overlap = min(max(0, int(overlap_tokens) * 4), window - 1)
        step = max(1, window - overlap)

        chunks: list[dict[str, Any]] = []
        for page in cleaned_pages:
            body = str(page.get("text", "")).strip()
            for start in range(0, len(body), step):
                piece = body[start : start + window].strip()
                if piece:
                    chunks.append(
                        {
                            "id": str(uuid.uuid4()),
                            "source_id": self.source_id,
                            "source_title": self.source_title,
                            "section": f"Page {page.get('page')}",
                            "text": piece,
                            "embedding": [],
                        }
                    )
        self.state["chunks"] = chunks
        self.state["stats"]["total_chunks"] = len(chunks)
        average = sum(len(chunk["text"]) for chunk in chunks) // len(chunks) if chunks else 0
        return {
            "total_chunks": len(chunks),
            "average_chunk_length": average,
            "first_chunk_preview": _preview(chunks[0]["text"]) if chunks else "",
        }

    # --- tool 5 ---------------------------------------------------------

    def embed_and_save_chunks(self, **_: Any) -> dict[str, Any]:
        chunks = self.state.get("chunks")
        if not chunks:
            return {"error": "Cannot embed chunks before chunking cleaned pages."}
        embeddings = embed_texts([chunk["text"] for chunk in chunks])
        model = current_embedding_model()
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding
            chunk["embedding_model"] = model
            chunk["embedding_dim"] = len(embedding)

        # Scoped write: replace only this source's chunks, mirroring
        # commit_source_artifacts so other sources are untouched.
        others = [
            chunk
            for chunk in storage.load_chunks(self.account_id)
            if str(chunk.get("source_id")) != str(self.source_id)
        ]
        storage.save_chunks(self.account_id, others + chunks)
        self.state["saved_chunk_ids"] = [chunk["id"] for chunk in chunks]
        return {"saved_chunks": len(chunks), "embedding_model": model}

    # --- tool 6 ---------------------------------------------------------

    def generate_and_save_memory_posts(self, **_: Any) -> dict[str, Any]:
        chunks = self.state.get("chunks")
        if not chunks:
            return {"error": "Cannot generate posts before chunking cleaned pages."}
        generated = generate_memory_posts(self.source_title, chunks)
        records: list[dict[str, Any]] = []
        post_types: dict[str, int] = {post_type: 0 for post_type in MEMORY_POST_TYPES}
        for post in generated:
            post_type = post["type"]
            records.append(
                {
                    "id": str(uuid.uuid4()),
                    "account_id": self.account_id,
                    "source_id": self.source_id,
                    "source_title": self.source_title,
                    "post_type": post_type,
                    "body": post["body"],
                    "created_at": _now_iso(),
                }
            )
            post_types[post_type] = post_types.get(post_type, 0) + 1

        others = [
            post
            for post in storage.load_posts(self.account_id)
            if str(post.get("source_id")) != str(self.source_id)
        ]
        storage.save_posts(self.account_id, others + records)
        self.state["stats"]["total_posts"] = len(records)
        self.state["stats"]["post_types"] = {k: v for k, v in post_types.items() if v}
        return {
            "created_posts": len(records),
            "post_types": {k: v for k, v in post_types.items() if v},
        }

    # --- tool 7 ---------------------------------------------------------

    def build_and_save_graph(self, **_: Any) -> dict[str, Any]:
        chunks = self.state.get("chunks")
        if not chunks:
            return {"error": "Cannot build the graph before chunking cleaned pages."}
        full_text = self.state.get("full_text") or "\n\n".join(
            chunk["text"] for chunk in chunks
        )
        enrichment = enrich_content("pdf", self.source_title, None, full_text)
        concepts = enrichment.get("concepts") or []

        # Persist source enrichment so the existing detail/chat UI stays populated.
        source = self._load_source()
        source.update(
            {
                "content": full_text,
                "summary": enrichment.get("summary", source.get("summary")),
                "key_ideas": enrichment.get("key_ideas", []),
                "concepts": concepts,
                "claims": enrichment.get("claims", []),
                "questions": enrichment.get("questions", []),
            }
        )
        storage.save_source_result(self.account_id, source)

        graph = merge_graph(storage.load_graph(self.account_id), self._source_ref(), concepts)
        storage.save_graph(self.account_id, graph)
        node_count = len(graph.get("nodes", []))
        edge_count = len(graph.get("edges", []))
        self.state["stats"].update({"graph_nodes": node_count, "graph_edges": edge_count})
        return {"graph_nodes": node_count, "graph_edges": edge_count}

    # --- tool 8 ---------------------------------------------------------

    def finalize_source(
        self,
        total_pages: int | None = None,
        total_chunks: int | None = None,
        total_posts: int | None = None,
        total_graph_nodes: int | None = None,
        total_graph_edges: int | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if not self.state.get("saved_chunk_ids"):
            return {"error": "Cannot finalize before chunks are embedded and saved."}
        stats = self.state.get("stats", {})
        source = self._load_source()
        source.update(
            {
                "status": "ready",
                "error": None,
                "progress_stage": "complete",
                "progress_label": "Ingestion complete",
                "progress_percent": 100,
                "total_pages": total_pages if total_pages is not None else stats.get("total_pages", 0),
                "total_chunks": total_chunks if total_chunks is not None else stats.get("total_chunks", 0),
                "total_posts": total_posts if total_posts is not None else stats.get("total_posts", 0),
                "graph_status": "ready",
                "total_graph_nodes": total_graph_nodes
                if total_graph_nodes is not None
                else stats.get("graph_nodes", 0),
                "total_graph_edges": total_graph_edges
                if total_graph_edges is not None
                else stats.get("graph_edges", 0),
            }
        )
        storage.save_source_result(self.account_id, source)
        self.state["finalized"] = True
        return {"status": "ready"}

    # --- tool 9 ---------------------------------------------------------

    def fail_source(self, error_message: str = "Processing failed.", **_: Any) -> dict[str, Any]:
        source = self._load_source()
        source.update(
            {
                "status": "failed",
                "error": error_message,
                "graph_status": "failed",
            }
        )
        storage.save_source_result(self.account_id, source)
        self.state["failed"] = True
        return {"status": "failed", "error_message": error_message}
