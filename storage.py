from __future__ import annotations

import os
import threading
from copy import deepcopy
from typing import Any

from storage_backends import FirestoreStorageBackend, MemoryStorageBackend, StorageBackend

_LOCK = threading.RLock()
_BACKEND: StorageBackend | None = None


def _create_backend() -> StorageBackend:
    if os.getenv("SKYWATCH_STORAGE_BACKEND") == "memory":
        return MemoryStorageBackend()
    return FirestoreStorageBackend()


def _backend() -> StorageBackend:
    global _BACKEND
    with _LOCK:
        if _BACKEND is None:
            _BACKEND = _create_backend()
        return _BACKEND


def reset_backend_for_tests() -> None:
    global _BACKEND
    with _LOCK:
        _BACKEND = None


def get_account(account_id: str) -> dict[str, str] | None:
    return _backend().get_account(account_id)


def upsert_account(account: dict[str, str]) -> dict[str, str]:
    return _backend().upsert_account(account)


def load_sources(account_id: str) -> list[dict[str, Any]]:
    return _backend().load_sources(account_id)


def save_sources(account_id: str, sources: list[dict[str, Any]]) -> None:
    _backend().save_sources(account_id, sources)


def load_chunks(account_id: str, *, copy_result: bool = True) -> list[dict[str, Any]]:
    chunks = _backend().load_chunks(account_id)
    return deepcopy(chunks) if copy_result else chunks


def save_chunks(account_id: str, chunks: list[dict[str, Any]]) -> None:
    _backend().save_chunks(account_id, chunks)


def load_posts(account_id: str) -> list[dict[str, Any]]:
    return _backend().load_posts(account_id)


def save_posts(account_id: str, posts: list[dict[str, Any]]) -> None:
    _backend().save_posts(account_id, posts)


def load_graph(account_id: str) -> dict[str, list[dict[str, Any]]]:
    return _backend().load_graph(account_id)


def save_graph(account_id: str, graph: dict[str, list[dict[str, Any]]]) -> None:
    _backend().save_graph(account_id, graph)


def append_source(account_id: str, source: dict[str, Any]) -> None:
    _backend().append_source(account_id, source)


def save_source_result(account_id: str, source: dict[str, Any]) -> None:
    _backend().save_source_result(account_id, source)


def commit_source_artifacts(
    account_id: str,
    source: dict[str, Any],
    chunks: list[dict[str, Any]],
    post: dict[str, Any],
    concepts: list[str],
    markdown: str,
) -> None:
    _backend().commit_source_artifacts(account_id, source, chunks, post, concepts, markdown)


def save_document(account_id: str, source_id: str, markdown: str) -> None:
    _backend().save_document(account_id, source_id, markdown)


def load_document(account_id: str, source_id: str) -> str:
    return _backend().load_document(account_id, source_id)
