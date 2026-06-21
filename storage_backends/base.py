from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

DEFAULT_ACCOUNT = {
    "id": "second-signal",
    "name": "Second Signal",
    "handle": "personal-kb",
    "initials": "SS",
}
DEFAULT_GRAPH_ID = "default"


class StorageBackend(ABC):
    @abstractmethod
    def get_default_account(self) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def load_sources(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_sources(self, sources: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_chunks(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_chunks(self, chunks: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_posts(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_posts(self, posts: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_graph(self) -> dict[str, list[dict[str, Any]]]:
        raise NotImplementedError

    @abstractmethod
    def save_graph(self, graph: dict[str, list[dict[str, Any]]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def append_source(self, source: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def save_source_result(self, source: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def commit_source_artifacts(
        self,
        source: dict[str, Any],
        chunks: list[dict[str, Any]],
        post: dict[str, Any],
        concepts: list[str],
        markdown: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def save_document(self, source_id: str, markdown: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_document(self, source_id: str) -> str:
        raise NotImplementedError
