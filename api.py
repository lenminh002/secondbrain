from __future__ import annotations

import asyncio
import heapq
import json
import threading
from typing import Any

import anyio
import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile

load_dotenv()

from contextlib import asynccontextmanager

from embeddings import cosine_similarity, embed_text
from ingestion import VideoIngestionDeferred, create_processing_source, process_source
from knowledge_ai import answer_with_context, answer_with_tools, stream_with_tools
from storage import get_account as storage_get_account
from storage import load_chunks, load_graph, load_posts, load_sources, upsert_account, save_source_result


def cleanup_stuck_processing_sources() -> None:
    try:
        account = storage_get_account("mock-user") or upsert_account(MOCK_ACCOUNT)
        account_id = account["id"]
        sources = load_sources(account_id)
        for source in sources:
            if source.get("status") == "processing":
                source["status"] = "failed"
                source["error"] = "Server was restarted while processing this source."
                source["progress_stage"] = "complete"
                source["progress_percent"] = 100
                save_source_result(account_id, source)
    except Exception as exc:
        print(f"Failed to cleanup stuck processing sources on startup: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_stuck_processing_sources()
    yield


app = FastAPI(title="Personal Knowledge Base API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



MOCK_ACCOUNT = {
    "id": "mock-user",
    "name": "SecondBrain",
    "handle": "mock-vault",
    "initials": "SB",
    "email": "mock@example.com",
    "avatar_url": "",
}


def current_account() -> dict[str, str]:
    # Read first; only write when the account doesn't exist yet.  Calling
    # upsert_account on every request caused an unnecessary write (get + set)
    # on every single endpoint hit when using the Firestore backend.
    return storage_get_account(MOCK_ACCOUNT["id"]) or upsert_account(MOCK_ACCOUNT)


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
    graph_match_by_source_id: dict[str, dict[str, str]] = {}
    graph_context: list[dict[str, Any]] = []
    for concept_id, source_ids in sorted(concept_to_sources.items()):
        if not source_ids.intersection(top_source_ids):
            continue
        neighbors = source_ids - top_source_ids
        related_source_ids.update(neighbors)
        concept_node = node_by_id.get(concept_id, {})
        concept_label = str(concept_node.get("label", concept_id))
        for source_id in sorted(neighbors):
            graph_match_by_source_id.setdefault(
                source_id,
                {
                    "matched_concept_id": concept_id,
                    "matched_concept_label": concept_label,
                },
            )
        graph_context.append(
            {
                "concept_id": concept_id,
                "concept_label": concept_label,
                "source_ids": sorted(source_ids),
                "source_titles": sorted(
                    source_title_by_id.get(source_id, source_id) for source_id in source_ids
                ),
                "expanded_source_ids": sorted(neighbors),
                "expanded_source_titles": sorted(
                    source_title_by_id.get(source_id, source_id) for source_id in neighbors
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
            extra_chunks.append(
                {
                    **chunk,
                    **graph_match_by_source_id.get(source_id, {}),
                    "score": 0,
                    "retrieval": "graph_neighbor",
                }
            )
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


def _citation_from_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    citation = {
        "source_id": chunk.get("source_id"),
        "source_title": chunk.get("source_title"),
        "section": chunk.get("section"),
        "text": chunk.get("text"),
        "score": chunk.get("score"),
        "retrieval": chunk.get("retrieval", "vector"),
    }
    if chunk.get("matched_concept_id"):
        citation["matched_concept_id"] = chunk.get("matched_concept_id")
    if chunk.get("matched_concept_label"):
        citation["matched_concept_label"] = chunk.get("matched_concept_label")
    return citation


def _search_knowledge_base(
    account_id: str,
    query: str,
    limit: int = 5,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    question_embedding = embed_text(query)
    chunks = load_chunks(account_id, copy_result=False)
    top_chunks = _rank_chunks(question_embedding, chunks, limit=limit)
    expanded_chunks, graph_context = _build_graph_context(top_chunks, chunks, load_graph(account_id))
    citations = [_citation_from_chunk(chunk) for chunk in expanded_chunks]
    result = {
        "query": query,
        "snippets": [
            {
                "citation_index": index + 1,
                "source_id": chunk.get("source_id"),
                "source_title": chunk.get("source_title"),
                "section": chunk.get("section"),
                "text": str(chunk.get("text", ""))[:1200],
                "score": chunk.get("score"),
                "retrieval": chunk.get("retrieval", "vector"),
                "matched_concept_id": chunk.get("matched_concept_id"),
                "matched_concept_label": chunk.get("matched_concept_label"),
            }
            for index, chunk in enumerate(expanded_chunks)
        ],
        "graph_context": graph_context,
    }
    return result, citations, graph_context


def _get_source_detail(account_id: str, source_id: str) -> dict[str, Any]:
    for source in load_sources(account_id):
        if source.get("id") == source_id:
            return {
                "source_id": source.get("id"),
                "title": source.get("title"),
                "type": source.get("type"),
                "summary": source.get("summary", ""),
                "key_ideas": source.get("key_ideas", []),
                "concepts": source.get("concepts", []),
                "claims": source.get("claims", []),
                "content": str(source.get("content", ""))[:6000],
            }
    raise ValueError("Source not found.")


def _chat_response(account_id: str, message: str) -> dict[str, Any]:
    citations: list[dict[str, Any]] = []
    graph_context: list[dict[str, Any]] = []
    tool_calls: list[dict[str, str]] = []

    def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        nonlocal citations, graph_context
        if tool_name == "search_knowledge_base":
            query = str(tool_input.get("query") or message).strip() or message
            result, citations, graph_context = _search_knowledge_base(account_id, query)
            return result
        if tool_name == "get_source_detail":
            source_id = str(tool_input.get("source_id") or "").strip()
            if not source_id:
                raise ValueError("source_id is required.")
            return _get_source_detail(account_id, source_id)
        raise ValueError(f"Unknown tool: {tool_name}")

    try:
        answer, used_tools = answer_with_tools(message, execute_tool)
        tool_calls = [{"name": name} for name in used_tools]
    except ValueError:
        top_chunks = [
            {
                "source_id": citation.get("source_id"),
                "source_title": citation.get("source_title"),
                "section": citation.get("section"),
                "text": citation.get("text"),
                "score": citation.get("score"),
                "retrieval": citation.get("retrieval", "vector"),
                "matched_concept_id": citation.get("matched_concept_id"),
                "matched_concept_label": citation.get("matched_concept_label"),
            }
            for citation in citations
        ]
        answer = answer_with_context(message, top_chunks, graph_context)

    return {
        "answer": answer,
        "citations": citations,
        "graph_context": graph_context,
        "tool_calls": tool_calls,
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


_SOURCE_LIST_EXCLUDE = {"content"}


@app.get("/sources")
def get_sources() -> list[dict[str, Any]]:
    account = current_account()
    sources = load_sources(account["id"])
    # Strip heavy content field from list responses; use GET /sources/{id} for full detail
    return _sort_newest([{k: v for k, v in s.items() if k not in _SOURCE_LIST_EXCLUDE} for s in sources])


@app.get("/sources/{source_id}")
def get_source(
    source_id: str,
) -> dict[str, Any]:
    account = current_account()
    account_id = account["id"]
    for source in load_sources(account_id):
        if source.get("id") == source_id:
            return source
    raise HTTPException(status_code=404, detail="Source not found")


@app.post("/sources")
async def create_source(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    account = current_account()
    payload = await _parse_source_request(request)
    source_type = str(payload.get("type") or "").strip().lower()
    if not source_type:
        raise HTTPException(status_code=400, detail="Source type is required.")

    title = str(payload.get("title") or "").strip() or None
    text = str(payload.get("text") or "").strip() or None
    source_url = str(payload.get("source_url") or "").strip() or None
    file_bytes = payload.get("file_bytes")
    filename = payload.get("filename")

    try:
        source = create_processing_source(
            account_id=account["id"],
            source_type=source_type,
            title=title,
            text=text,
            source_url=source_url,
            file_bytes=file_bytes,
            filename=filename,
        )
        background_tasks.add_task(
            process_source,
            source,
            text=text,
            source_url=source_url,
            file_bytes=file_bytes,
            filename=filename,
        )
        return source
    except VideoIngestionDeferred as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/posts")
def get_posts() -> list[dict[str, Any]]:
    account = current_account()
    return _sort_newest(load_posts(account["id"]))


@app.get("/account")
def get_account() -> dict[str, str]:
    return current_account()


@app.get("/graph")
def get_graph() -> dict[str, list[dict[str, Any]]]:
    account = current_account()
    return load_graph(account["id"])


@app.post("/chat")
async def chat(
    request: Request,
) -> dict[str, Any]:
    account = current_account()
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object.")
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")

    return await anyio.to_thread.run_sync(_chat_response, account["id"], message)


@app.post("/chat/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    account = current_account()
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object.")
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")

    account_id = account["id"]

    async def event_generator():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        # Accumulated metadata updated by execute_tool calls in the worker thread.
        citations: list[dict] = []
        graph_context: list[dict] = []
        tool_calls: list[dict] = []

        def sync_worker() -> None:
            nonlocal citations, graph_context

            def execute_tool(tool_name: str, tool_input: dict) -> dict:
                nonlocal citations, graph_context
                if tool_name == "search_knowledge_base":
                    query = str(tool_input.get("query") or message).strip() or message
                    result, citations, graph_context = _search_knowledge_base(account_id, query)
                    return result
                if tool_name == "get_source_detail":
                    source_id = str(tool_input.get("source_id") or "").strip()
                    if not source_id:
                        raise ValueError("source_id is required.")
                    return _get_source_detail(account_id, source_id)
                raise ValueError(f"Unknown tool: {tool_name}")

            try:
                for event in stream_with_tools(message, execute_tool):
                    if event.get("type") == "tool_call":
                        tool_calls.append({"name": event.get("name", "")})
                    if event.get("type") == "done":
                        # Attach accumulated metadata to the done event.
                        done_payload = {
                            "type": "done",
                            "citations": citations,
                            "graph_context": graph_context,
                            "tool_calls": tool_calls,
                        }
                        asyncio.run_coroutine_threadsafe(
                            queue.put(f"data: {json.dumps(done_payload)}\n\n"), loop
                        ).result()
                    else:
                        asyncio.run_coroutine_threadsafe(
                            queue.put(f"data: {json.dumps(event)}\n\n"), loop
                        ).result()
            except Exception as exc:
                err = json.dumps({"type": "error", "message": str(exc)})
                asyncio.run_coroutine_threadsafe(queue.put(f"data: {err}\n\n"), loop).result()
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

        thread = threading.Thread(target=sync_worker, daemon=True)
        thread.start()

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
