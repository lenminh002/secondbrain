from __future__ import annotations

import heapq
from functools import partial
from typing import Any

import anyio
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import UploadFile

from embeddings import cosine_similarity, embed_text
from ingestion import VideoIngestionDeferred, ingest_source
from knowledge_ai import answer_with_context
from storage import get_default_account, load_chunks, load_document, load_graph, load_posts, load_sources

app = FastAPI(title="Personal Knowledge Base API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sort_newest(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda record: str(record.get("created_at", "")), reverse=True)


def _source_node_id(source_id: str) -> str:
    return f"source-{source_id}"


def _source_id_from_node(node_id: str) -> str | None:
    return node_id.removeprefix("source-") if node_id.startswith("source-") else None


def _build_graph_context(
    top_chunks: list[dict[str, Any]],
    all_chunks: list[dict[str, Any]],
    graph: dict[str, list[dict[str, Any]]],
    max_extra_sources: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_by_id = {str(node.get("id")): node for node in nodes if isinstance(node, dict)}
    source_title_by_id = {
        str(chunk.get("source_id")): str(chunk.get("source_title", "Untitled"))
        for chunk in all_chunks
        if chunk.get("source_id")
    }
    top_source_ids = {
        str(chunk.get("source_id"))
        for chunk in top_chunks
        if chunk.get("source_id")
    }
    if not top_source_ids or not edges:
        return top_chunks, []

    concept_to_sources: dict[str, set[str]] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        source_id = _source_id_from_node(source)
        concept_id = target if target.startswith("concept-") else ""
        if not source_id or not concept_id:
            continue
        concept_to_sources.setdefault(concept_id, set()).add(source_id)

    related_source_ids: set[str] = set()
    graph_context: list[dict[str, Any]] = []
    for concept_id, source_ids in concept_to_sources.items():
        if not source_ids.intersection(top_source_ids):
            continue
        neighbors = source_ids - top_source_ids
        related_source_ids.update(neighbors)
        concept_node = node_by_id.get(concept_id, {})
        graph_context.append(
            {
                "concept_id": concept_id,
                "concept_label": concept_node.get("label", concept_id),
                "source_ids": sorted(source_ids),
                "source_titles": sorted(
                    source_title_by_id.get(source_id, source_id) for source_id in source_ids
                ),
            }
        )

    existing_chunk_ids = {chunk.get("id") for chunk in top_chunks}
    first_chunk_by_source_id: dict[str, dict[str, Any]] = {}
    for chunk in all_chunks:
        source_id = str(chunk.get("source_id", ""))
        if (
            source_id
            and source_id not in first_chunk_by_source_id
            and chunk.get("id") not in existing_chunk_ids
        ):
            first_chunk_by_source_id[source_id] = chunk

    extra_chunks: list[dict[str, Any]] = []
    for source_id in sorted(related_source_ids):
        if len(extra_chunks) >= max_extra_sources:
            break
        chunk = first_chunk_by_source_id.get(source_id)
        if chunk:
            extra_chunks.append({**chunk, "score": 0, "retrieval": "graph_neighbor"})
            existing_chunk_ids.add(chunk.get("id"))

    return top_chunks + extra_chunks, graph_context[:8]


def _rank_chunks(
    question_embedding: list[float],
    chunks: list[dict[str, Any]],
    limit: int = 5,
) -> list[dict[str, Any]]:
    def scored_chunks() -> Any:
        for chunk in chunks:
            embedding = chunk.get("embedding")
            if not isinstance(embedding, list) or len(embedding) != len(question_embedding):
                continue
            score = cosine_similarity(question_embedding, embedding)
            yield (score, chunk)

    return [
        {**chunk, "score": round(score, 4)}
        for score, chunk in heapq.nlargest(limit, scored_chunks(), key=lambda item: item[0])
    ]


def _chat_response(message: str) -> dict[str, Any]:
    question_embedding = embed_text(message)
    chunks = load_chunks(copy_result=False)
    top_chunks = _rank_chunks(question_embedding, chunks)
    expanded_chunks, graph_context = _build_graph_context(top_chunks, chunks, load_graph())
    answer = answer_with_context(message, expanded_chunks, graph_context)
    return {
        "answer": answer,
        "citations": [
            {
                "source_id": chunk.get("source_id"),
                "source_title": chunk.get("source_title"),
                "section": chunk.get("section"),
                "text": chunk.get("text"),
                "score": chunk.get("score"),
                "retrieval": chunk.get("retrieval", "vector"),
            }
            for chunk in expanded_chunks
        ],
        "graph_context": graph_context,
    }


async def _parse_source_request(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")
        return payload

    form = await request.form()
    upload = form.get("file")
    file_bytes = None
    filename = None
    if isinstance(upload, UploadFile):
        file_bytes = await upload.read()
        filename = upload.filename

    return {
        "type": form.get("type"),
        "title": form.get("title"),
        "text": form.get("text"),
        "source_url": form.get("source_url"),
        "file_bytes": file_bytes,
        "filename": filename,
    }


@app.get("/sources")
def get_sources() -> list[dict[str, Any]]:
    return _sort_newest(load_sources())


@app.get("/sources/{source_id}")
def get_source(source_id: str) -> dict[str, Any]:
    for source in load_sources():
        if source.get("id") == source_id:
            return {**source, "markdown": load_document(source_id)}
    raise HTTPException(status_code=404, detail="Source not found")


@app.post("/sources")
async def create_source(request: Request) -> dict[str, Any]:
    payload = await _parse_source_request(request)
    source_type = str(payload.get("type") or "").strip().lower()
    if not source_type:
        raise HTTPException(status_code=400, detail="Source type is required.")

    try:
        return await anyio.to_thread.run_sync(
            partial(
                ingest_source,
                source_type=source_type,
                title=str(payload.get("title") or "").strip() or None,
                text=str(payload.get("text") or "").strip() or None,
                source_url=str(payload.get("source_url") or "").strip() or None,
                file_bytes=payload.get("file_bytes"),
                filename=payload.get("filename"),
            )
        )
    except VideoIngestionDeferred as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/posts")
def get_posts() -> list[dict[str, Any]]:
    return _sort_newest(load_posts())


@app.get("/account")
def get_account() -> dict[str, str]:
    return get_default_account()


@app.get("/graph")
def get_graph() -> dict[str, list[dict[str, Any]]]:
    return load_graph()


@app.post("/chat")
async def chat(request: Request) -> dict[str, Any]:
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object.")
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")

    return await anyio.to_thread.run_sync(_chat_response, message)


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
