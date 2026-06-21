from __future__ import annotations

import os
import threading
from copy import deepcopy
from typing import Any

from storage_backends import (
    DEFAULT_ACCOUNT,
    DEFAULT_GRAPH_ID,
    FirestoreStorageBackend,
    MemoryStorageBackend,
    StorageBackend,
)

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


def get_default_account() -> dict[str, str]:
    return _backend().get_default_account()


def load_sources() -> list[dict[str, Any]]:
    return _backend().load_sources()


def save_sources(sources: list[dict[str, Any]]) -> None:
    _backend().save_sources(sources)


def load_chunks(*, copy_result: bool = True) -> list[dict[str, Any]]:
    chunks = _backend().load_chunks()
    return deepcopy(chunks) if copy_result else chunks


def save_chunks(chunks: list[dict[str, Any]]) -> None:
    _backend().save_chunks(chunks)


def load_posts() -> list[dict[str, Any]]:
    return _backend().load_posts()


def save_posts(posts: list[dict[str, Any]]) -> None:
    _backend().save_posts(posts)


def load_graph() -> dict[str, list[dict[str, Any]]]:
    return _backend().load_graph()


def save_graph(graph: dict[str, list[dict[str, Any]]]) -> None:
    _backend().save_graph(graph)


def append_source(source: dict[str, Any]) -> None:
    _backend().append_source(source)


def save_source_result(source: dict[str, Any]) -> None:
    _backend().save_source_result(source)


def commit_source_artifacts(
    source: dict[str, Any],
    chunks: list[dict[str, Any]],
    post: dict[str, Any],
    concepts: list[str],
    markdown: str,
) -> None:
    _backend().commit_source_artifacts(source, chunks, post, concepts, markdown)


def save_document(source_id: str, markdown: str) -> None:
    _backend().save_document(source_id, markdown)


def load_document(source_id: str) -> str:
    return _backend().load_document(source_id)
