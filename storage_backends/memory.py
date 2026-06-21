from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any

from storage_backends.base import DEFAULT_ACCOUNT, StorageBackend
from storage_backends.utils import coerce_graph, merge_graph, post_with_default_account


class MemoryStorageBackend(StorageBackend):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.sources: dict[str, dict[str, Any]] = {}
        self.chunks: dict[str, dict[str, Any]] = {}
        self.posts: dict[str, dict[str, Any]] = {}
        self.documents: dict[str, str] = {}
        self.graph: dict[str, list[dict[str, Any]]] = {"nodes": [], "edges": []}
        self.accounts: dict[str, dict[str, str]] = {}

    def get_default_account(self) -> dict[str, str]:
        with self._lock:
            account = self.accounts.setdefault(DEFAULT_ACCOUNT["id"], deepcopy(DEFAULT_ACCOUNT))
            return deepcopy(account)

    def load_sources(self) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(list(self.sources.values()))

    def save_sources(self, sources: list[dict[str, Any]]) -> None:
        with self._lock:
            self.sources = {
                str(source["id"]): deepcopy(source)
                for source in sources
                if isinstance(source, dict) and source.get("id")
            }

    def load_chunks(self) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(list(self.chunks.values()))

    def save_chunks(self, chunks: list[dict[str, Any]]) -> None:
        with self._lock:
            self.chunks = {
                str(chunk["id"]): deepcopy(chunk)
                for chunk in chunks
                if isinstance(chunk, dict) and chunk.get("id")
            }

    def load_posts(self) -> list[dict[str, Any]]:
        with self._lock:
            return [post_with_default_account(post) for post in deepcopy(list(self.posts.values()))]

    def save_posts(self, posts: list[dict[str, Any]]) -> None:
        with self._lock:
            self.posts = {
                str(post["id"]): deepcopy(post)
                for post in posts
                if isinstance(post, dict) and post.get("id")
            }

    def load_graph(self) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            return deepcopy(self.graph)

    def save_graph(self, graph: dict[str, list[dict[str, Any]]]) -> None:
        with self._lock:
            self.graph = deepcopy(coerce_graph(graph))

    def append_source(self, source: dict[str, Any]) -> None:
        with self._lock:
            self.sources[str(source["id"])] = deepcopy(source)

    def save_source_result(self, source: dict[str, Any]) -> None:
        with self._lock:
            self.sources[str(source["id"])] = deepcopy(source)

    def commit_source_artifacts(
        self,
        source: dict[str, Any],
        chunks: list[dict[str, Any]],
        post: dict[str, Any],
        concepts: list[str],
        markdown: str,
    ) -> None:
        with self._lock:
            self.chunks = {
                chunk_id: chunk
                for chunk_id, chunk in self.chunks.items()
                if chunk.get("source_id") != source["id"]
            }
            for chunk in chunks:
                self.chunks[str(chunk["id"])] = deepcopy(chunk)

            self.posts = {
                post_id: current_post
                for post_id, current_post in self.posts.items()
                if current_post.get("source_id") != source["id"]
            }
            self.posts[str(post["id"])] = deepcopy(post)
            self.graph = merge_graph(self.graph, source, concepts)
            self.documents[str(source["id"])] = markdown

    def save_document(self, source_id: str, markdown: str) -> None:
        with self._lock:
            self.documents[str(source_id)] = markdown

    def load_document(self, source_id: str) -> str:
        with self._lock:
            return self.documents.get(str(source_id), "")
