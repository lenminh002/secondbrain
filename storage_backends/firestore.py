from __future__ import annotations

from copy import deepcopy
from typing import Any

from firebase_admin_app import get_firebase_admin_app
from storage_backends.base import StorageBackend
from storage_backends.utils import coerce_graph, coerce_list, merge_graph


class FirestoreStorageBackend(StorageBackend):
    def __init__(self) -> None:
        self._db = self._build_client()

    def _build_client(self) -> Any:
        try:
            from firebase_admin import firestore
        except ImportError as exc:
            raise RuntimeError(
                "firebase-admin is required for Firestore storage. Run `uv sync` first."
            ) from exc

        app = get_firebase_admin_app(require_credentials=True)
        return firestore.client(app)

    def _account_query_items(self, name: str, account_id: str) -> list[dict[str, Any]]:
        query = self._db.collection(name).where("account_id", "==", account_id)
        return [snapshot.to_dict() or {} for snapshot in query.stream()]

    def _delete_query(self, query: Any) -> None:
        for snapshot in query.stream():
            snapshot.reference.delete()

    def get_account(self, account_id: str) -> dict[str, str] | None:
        snapshot = self._db.collection("accounts").document(account_id).get()
        if not snapshot.exists:
            return None
        account = snapshot.to_dict() or {}
        return deepcopy(account)

    def upsert_account(self, account: dict[str, str]) -> dict[str, str]:
        account_id = str(account["id"])
        account_ref = self._db.collection("accounts").document(account_id)
        existing = account_ref.get().to_dict() or {}
        merged = {**existing, **account}
        account_ref.set(merged)
        return deepcopy(merged)

    def load_sources(self, account_id: str) -> list[dict[str, Any]]:
        return coerce_list(self._account_query_items("sources", account_id))

    def save_sources(self, account_id: str, sources: list[dict[str, Any]]) -> None:
        self._delete_query(self._db.collection("sources").where("account_id", "==", account_id))
        for source in sources:
            if isinstance(source, dict) and source.get("id"):
                record = {**source, "account_id": account_id}
                self._db.collection("sources").document(str(record["id"])).set(record)

    def load_chunks(self, account_id: str) -> list[dict[str, Any]]:
        return coerce_list(self._account_query_items("chunks", account_id))

    def save_chunks(self, account_id: str, chunks: list[dict[str, Any]]) -> None:
        self._delete_query(self._db.collection("chunks").where("account_id", "==", account_id))
        for chunk in chunks:
            if isinstance(chunk, dict) and chunk.get("id"):
                record = {**chunk, "account_id": account_id}
                self._db.collection("chunks").document(str(record["id"])).set(record)

    def load_posts(self, account_id: str) -> list[dict[str, Any]]:
        return coerce_list(self._account_query_items("posts", account_id))

    def save_posts(self, account_id: str, posts: list[dict[str, Any]]) -> None:
        self._delete_query(self._db.collection("posts").where("account_id", "==", account_id))
        for post in posts:
            if isinstance(post, dict) and post.get("id"):
                record = {**post, "account_id": account_id}
                self._db.collection("posts").document(str(record["id"])).set(record)

    def load_graph(self, account_id: str) -> dict[str, list[dict[str, Any]]]:
        snapshot = self._db.collection("graphs").document(account_id).get()
        return coerce_graph(snapshot.to_dict() if snapshot.exists else {})

    def save_graph(self, account_id: str, graph: dict[str, list[dict[str, Any]]]) -> None:
        self._db.collection("graphs").document(account_id).set(
            {**coerce_graph(graph), "account_id": account_id}
        )

    def append_source(self, account_id: str, source: dict[str, Any]) -> None:
        record = {**source, "account_id": account_id}
        self._db.collection("sources").document(str(record["id"])).set(record)

    def save_source_result(self, account_id: str, source: dict[str, Any]) -> None:
        record = {**source, "account_id": account_id}
        self._db.collection("sources").document(str(record["id"])).set(record)

    def commit_source_artifacts(
        self,
        account_id: str,
        source: dict[str, Any],
        chunks: list[dict[str, Any]],
        post: dict[str, Any],
        concepts: list[str],
        markdown: str,
    ) -> None:
        source_id = str(source["id"])
        chunk_query = (
            self._db.collection("chunks")
            .where("account_id", "==", account_id)
            .where("source_id", "==", source_id)
        )
        self._delete_query(chunk_query)
        for chunk in chunks:
            record = {**chunk, "account_id": account_id}
            self._db.collection("chunks").document(str(record["id"])).set(record)

        post_query = (
            self._db.collection("posts")
            .where("account_id", "==", account_id)
            .where("source_id", "==", source_id)
        )
        self._delete_query(post_query)
        self._db.collection("posts").document(str(post["id"])).set(
            {**post, "account_id": account_id}
        )

        graph = merge_graph(self.load_graph(account_id), source, concepts)
        self.save_graph(account_id, graph)
        self.save_document(account_id, source_id, markdown)

    def save_document(self, account_id: str, source_id: str, markdown: str) -> None:
        self._db.collection("documents").document(str(source_id)).set(
            {"account_id": account_id, "markdown": markdown}
        )

    def load_document(self, account_id: str, source_id: str) -> str:
        snapshot = self._db.collection("documents").document(str(source_id)).get()
        if not snapshot.exists:
            return ""
        data = snapshot.to_dict() or {}
        if data.get("account_id") != account_id:
            return ""
        return str(data.get("markdown") or "")
