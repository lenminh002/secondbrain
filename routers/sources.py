from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from starlette.datastructures import UploadFile

from ingestion import create_processing_source, edit_source_content, process_source
from services.account_service import current_account
from services.retrieval import _sort_newest
from storage import load_sources

router = APIRouter()

_SOURCE_LIST_EXCLUDE = {"content"}


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


@router.get("/sources")
def get_sources() -> list[dict[str, Any]]:
    account = current_account()
    sources = load_sources(account["id"])
    # Strip heavy content field from list responses; use GET /sources/{id} for full detail
    return _sort_newest([{k: v for k, v in s.items() if k not in _SOURCE_LIST_EXCLUDE} for s in sources])


@router.get("/sources/{source_id}")
def get_source(source_id: str) -> dict[str, Any]:
    account = current_account()
    for source in load_sources(account["id"]):
        if source.get("id") == source_id:
            return source
    raise HTTPException(status_code=404, detail="Source not found")


@router.patch("/sources/{source_id}")
async def update_source(source_id: str, request: Request) -> dict[str, Any]:
    account = current_account()
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object.")
    content = str(payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Memory content is required.")

    source = next(
        (item for item in load_sources(account["id"]) if item.get("id") == source_id),
        None,
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.get("status") != "ready":
        raise HTTPException(status_code=409, detail="Only ready memories can be edited.")

    try:
        return edit_source_content(source, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/sources")
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
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
