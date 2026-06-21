from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StorageBackend(ABC):
    @abstractmethod
    def get_account(self, account_id: str) -> dict[str, str] | None:
        raise NotImplementedError

    @abstractmethod
    def upsert_account(self, account: dict[str, str]) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def load_sources(self, account_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_sources(self, account_id: str, sources: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_chunks(self, account_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_chunks(self, account_id: str, chunks: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_posts(self, account_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_posts(self, account_id: str, posts: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_graph(self, account_id: str) -> dict[str, list[dict[str, Any]]]:
        raise NotImplementedError

    @abstractmethod
    def save_graph(self, account_id: str, graph: dict[str, list[dict[str, Any]]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def append_source(self, account_id: str, source: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def save_source_result(self, account_id: str, source: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def commit_source_artifacts(
        self,
        account_id: str,
        source: dict[str, Any],
        chunks: list[dict[str, Any]],
        post: dict[str, Any],
        concepts: list[str],
    ) -> None:
        raise NotImplementedError

    # --- Agent runs -----------------------------------------------------

    @abstractmethod
    def create_agent_run(self, run: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def update_agent_run(self, run_id: str, updates: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def append_agent_tool_call(self, run_id: str, tool_call: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_agent_run(self, run_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def list_agent_runs_for_source(
        self, account_id: str, source_id: str
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def update_source_agent_status(
        self,
        account_id: str,
        source_id: str,
        agent_run_id: str,
        agent_status: str,
    ) -> None:
        raise NotImplementedError
