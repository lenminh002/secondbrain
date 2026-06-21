from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any

from storage_backends.base import StorageBackend
from storage_backends.utils import coerce_graph, merge_graph


class MemoryStorageBackend(StorageBackend):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.sources: dict[str, dict[str, Any]] = {}
        self.chunks: dict[str, dict[str, Any]] = {}
        self.posts: dict[str, dict[str, Any]] = {}
        self.graphs: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self.accounts: dict[str, dict[str, str]] = {}

    def get_account(self, account_id: str) -> dict[str, str] | None:
        with self._lock:
            account = self.accounts.get(account_id)
            return deepcopy(account) if account else None

    def upsert_account(self, account: dict[str, str]) -> dict[str, str]:
        with self._lock:
            account_id = str(account["id"])
            merged = {**self.accounts.get(account_id, {}), **account}
            self.accounts[account_id] = deepcopy(merged)
            return deepcopy(merged)

    def _account_records(self, records: dict[str, dict[str, Any]], account_id: str) -> list[dict[str, Any]]:
        return [
            deepcopy(record)
            for record in records.values()
            if record.get("account_id") == account_id
        ]

    def load_sources(self, account_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return self._account_records(self.sources, account_id)

    def save_sources(self, account_id: str, sources: list[dict[str, Any]]) -> None:
        with self._lock:
            self.sources = {
                source_id: source
                for source_id, source in self.sources.items()
                if source.get("account_id") != account_id
            }
            for source in sources:
                if isinstance(source, dict) and source.get("id"):
                    record = {**source, "account_id": account_id}
                    self.sources[str(record["id"])] = deepcopy(record)

    def load_chunks(self, account_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return self._account_records(self.chunks, account_id)

    def save_chunks(self, account_id: str, chunks: list[dict[str, Any]]) -> None:
        with self._lock:
            self.chunks = {
                chunk_id: chunk
                for chunk_id, chunk in self.chunks.items()
                if chunk.get("account_id") != account_id
            }
            for chunk in chunks:
                if isinstance(chunk, dict) and chunk.get("id"):
                    record = {**chunk, "account_id": account_id}
                    self.chunks[str(record["id"])] = deepcopy(record)

    def load_posts(self, account_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return self._account_records(self.posts, account_id)

    def save_posts(self, account_id: str, posts: list[dict[str, Any]]) -> None:
        with self._lock:
            self.posts = {
                post_id: post
                for post_id, post in self.posts.items()
                if post.get("account_id") != account_id
            }
            for post in posts:
                if isinstance(post, dict) and post.get("id"):
                    record = {**post, "account_id": account_id}
                    self.posts[str(record["id"])] = deepcopy(record)

    def load_graph(self, account_id: str) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            return deepcopy(self.graphs.get(account_id, {"nodes": [], "edges": []}))

    def save_graph(self, account_id: str, graph: dict[str, list[dict[str, Any]]]) -> None:
        with self._lock:
            self.graphs[account_id] = deepcopy(coerce_graph(graph))

    def append_source(self, account_id: str, source: dict[str, Any]) -> None:
        with self._lock:
            record = {**source, "account_id": account_id}
            self.sources[str(record["id"])] = deepcopy(record)

    def save_source_result(self, account_id: str, source: dict[str, Any]) -> None:
        with self._lock:
            record = {**source, "account_id": account_id}
            self.sources[str(record["id"])] = deepcopy(record)

    def commit_source_artifacts(
        self,
        account_id: str,
        source: dict[str, Any],
        chunks: list[dict[str, Any]],
        post: dict[str, Any],
        concepts: list[str],
    ) -> None:
        with self._lock:
            self.chunks = {
                chunk_id: chunk
                for chunk_id, chunk in self.chunks.items()
                if chunk.get("account_id") != account_id or chunk.get("source_id") != source["id"]
            }
            for chunk in chunks:
                record = {**chunk, "account_id": account_id}
                self.chunks[str(record["id"])] = deepcopy(record)

            self.posts = {
                post_id: current_post
                for post_id, current_post in self.posts.items()
                if (
                    current_post.get("account_id") != account_id
                    or current_post.get("source_id") != source["id"]
                )
            }
            self.posts[str(post["id"])] = deepcopy({**post, "account_id": account_id})
            self.graphs[account_id] = merge_graph(
                self.graphs.get(account_id, {"nodes": [], "edges": []}),
                source,
                concepts,
            )
