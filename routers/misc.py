from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from services.account_service import current_account
from services.retrieval import _sort_newest
from storage import load_graph, load_posts

router = APIRouter()


@router.get("/posts")
def get_posts() -> list[dict[str, Any]]:
    account = current_account()
    return _sort_newest(load_posts(account["id"]))


@router.get("/account")
def get_account() -> dict[str, str]:
    return current_account()


@router.get("/graph")
def get_graph() -> dict[str, list[dict[str, Any]]]:
    account = current_account()
    return load_graph(account["id"])
