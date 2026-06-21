from __future__ import annotations

from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import asyncio
import json
import threading

from knowledge_ai import stream_with_tools
from services.retrieval import get_source_detail, search_knowledge_base
from services.account_service import current_account

router = APIRouter()


@router.post("/chat")
async def chat(request: Request) -> dict[str, Any]:
    from services.chat_service import chat_response

    account = current_account()
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object.")
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")

    return await anyio.to_thread.run_sync(chat_response, account["id"], message)


@router.post("/chat/stream")
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
                    result, new_citations, new_graph_context = search_knowledge_base(account_id, query)
                    citations[:] = new_citations
                    graph_context[:] = new_graph_context
                    return result
                if tool_name == "get_source_detail":
                    source_id = str(tool_input.get("source_id") or "").strip()
                    if not source_id:
                        raise ValueError("source_id is required.")
                    return get_source_detail(account_id, source_id)
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
