from __future__ import annotations

from typing import Any

import anyio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import asyncio
import json
import threading

from services.account_service import current_account
from services.chat_service import run_agent

router = APIRouter()

MAX_CHAT_HISTORY_MESSAGES = 20
MAX_CHAT_HISTORY_TEXT_LENGTH = 4000


def _validated_history(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw_history = payload.get("history", [])
    if raw_history is None:
        return []
    if not isinstance(raw_history, list):
        raise HTTPException(status_code=400, detail="History must be a list.")

    history: list[dict[str, str]] = []
    for item in raw_history:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="History entries must be objects.")
        role = item.get("role")
        text = item.get("text")
        if role not in {"user", "assistant"} or not isinstance(text, str):
            raise HTTPException(
                status_code=400,
                detail="History entries must include role and text.",
            )
        cleaned_text = text.strip()
        if not cleaned_text:
            continue
        history.append(
            {
                "role": role,
                "text": cleaned_text[:MAX_CHAT_HISTORY_TEXT_LENGTH],
            }
        )

    return history[-MAX_CHAT_HISTORY_MESSAGES:]


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
    history = _validated_history(payload)

    return await anyio.to_thread.run_sync(
        lambda: chat_response(account["id"], message, history=history)
    )


@router.post("/chat/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    account = current_account()
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object.")
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")
    history = _validated_history(payload)

    account_id = account["id"]

    async def event_generator():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def sync_worker() -> None:
            def emit(event: dict[str, Any]) -> None:
                asyncio.run_coroutine_threadsafe(
                    queue.put(f"data: {json.dumps(event)}\n\n"), loop
                ).result()

            try:
                result = run_agent(
                    account_id,
                    message,
                    history=history,
                    emit_event=emit,
                    stream_text=True,
                )
                emit(
                    {
                        "type": "done",
                        "citations": result["citations"],
                        "graph_context": result["graph_context"],
                        "tool_calls": result["tool_calls"],
                        "agent_trace": result["agent_trace"],
                    }
                )
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
