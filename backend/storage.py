from __future__ import annotations

import os
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from storage_backends import FirestoreStorageBackend, MemoryStorageBackend, StorageBackend

load_dotenv(dotenv_path=Path.cwd() / ".env")

_LOCK = threading.RLock()
_BACKEND: StorageBackend | None = None


def _create_backend() -> StorageBackend:
    if os.getenv("SECONDBRAIN_STORAGE_BACKEND") == "firestore":
        return FirestoreStorageBackend()
    return MemoryStorageBackend()


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
) -> None:
    _backend().commit_source_artifacts(account_id, source, chunks, post, concepts)


def create_agent_run(run: dict[str, Any]) -> None:
    _backend().create_agent_run(run)


def update_agent_run(run_id: str, updates: dict[str, Any]) -> None:
    _backend().update_agent_run(run_id, updates)


def append_agent_tool_call(run_id: str, tool_call: dict[str, Any]) -> None:
    _backend().append_agent_tool_call(run_id, tool_call)


def get_agent_run(run_id: str) -> dict[str, Any] | None:
    return _backend().get_agent_run(run_id)


def list_agent_runs_for_source(account_id: str, source_id: str) -> list[dict[str, Any]]:
    return _backend().list_agent_runs_for_source(account_id, source_id)


def update_source_agent_status(
    account_id: str,
    source_id: str,
    agent_run_id: str,
    agent_status: str,
) -> None:
    _backend().update_source_agent_status(account_id, source_id, agent_run_id, agent_status)
