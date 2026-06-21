from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from storage_backends.base import DEFAULT_ACCOUNT, DEFAULT_GRAPH_ID, StorageBackend
from storage_backends.utils import coerce_graph, coerce_list, merge_graph, post_with_default_account


class FirestoreStorageBackend(StorageBackend):
    def __init__(self) -> None:
        self._db = self._build_client()

    def _build_client(self) -> Any:
        credentials_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE") or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        if not credentials_path:
            raise RuntimeError(
                "Firebase credentials are required. Set FIREBASE_SERVICE_ACCOUNT_FILE "
                "or GOOGLE_APPLICATION_CREDENTIALS to a Firebase service account JSON file."
            )

        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
        except ImportError as exc:
            raise RuntimeError(
                "firebase-admin is required for Firestore storage. Run `uv sync` first."
            ) from exc

        try:
            app = firebase_admin.get_app()
        except ValueError:
            app = firebase_admin.initialize_app(credentials.Certificate(credentials_path))
        return firestore.client(app)

    def _collection_items(self, name: str) -> list[dict[str, Any]]:
        return [snapshot.to_dict() or {} for snapshot in self._db.collection(name).stream()]

    def _delete_collection(self, name: str) -> None:
        for snapshot in self._db.collection(name).stream():
            snapshot.reference.delete()

    def _delete_query(self, query: Any) -> None:
        for snapshot in query.stream():
            snapshot.reference.delete()

    def get_default_account(self) -> dict[str, str]:
        account_ref = self._db.collection("accounts").document(DEFAULT_ACCOUNT["id"])
        snapshot = account_ref.get()
        if not snapshot.exists:
            account_ref.set(DEFAULT_ACCOUNT)
            return deepcopy(DEFAULT_ACCOUNT)
        account = snapshot.to_dict() or {}
        return deepcopy({**DEFAULT_ACCOUNT, **account})

    def load_sources(self) -> list[dict[str, Any]]:
        return coerce_list(self._collection_items("sources"))

    def save_sources(self, sources: list[dict[str, Any]]) -> None:
        self._delete_collection("sources")
        for source in sources:
            if isinstance(source, dict) and source.get("id"):
                self._db.collection("sources").document(str(source["id"])).set(source)

    def load_chunks(self) -> list[dict[str, Any]]:
        return coerce_list(self._collection_items("chunks"))

    def save_chunks(self, chunks: list[dict[str, Any]]) -> None:
        self._delete_collection("chunks")
        for chunk in chunks:
            if isinstance(chunk, dict) and chunk.get("id"):
                self._db.collection("chunks").document(str(chunk["id"])).set(chunk)

    def load_posts(self) -> list[dict[str, Any]]:
        return [post_with_default_account(post) for post in coerce_list(self._collection_items("posts"))]

    def save_posts(self, posts: list[dict[str, Any]]) -> None:
        self._delete_collection("posts")
        for post in posts:
            if isinstance(post, dict) and post.get("id"):
                self._db.collection("posts").document(str(post["id"])).set(post)

    def load_graph(self) -> dict[str, list[dict[str, Any]]]:
        snapshot = self._db.collection("graphs").document(DEFAULT_GRAPH_ID).get()
        return coerce_graph(snapshot.to_dict() if snapshot.exists else {})

    def save_graph(self, graph: dict[str, list[dict[str, Any]]]) -> None:
        self._db.collection("graphs").document(DEFAULT_GRAPH_ID).set(coerce_graph(graph))

    def append_source(self, source: dict[str, Any]) -> None:
        self._db.collection("sources").document(str(source["id"])).set(source)

    def save_source_result(self, source: dict[str, Any]) -> None:
        self._db.collection("sources").document(str(source["id"])).set(source)

    def commit_source_artifacts(
        self,
        source: dict[str, Any],
        chunks: list[dict[str, Any]],
        post: dict[str, Any],
        concepts: list[str],
        markdown: str,
    ) -> None:
        source_id = str(source["id"])
        chunk_query = self._db.collection("chunks").where("source_id", "==", source_id)
        self._delete_query(chunk_query)
        for chunk in chunks:
            self._db.collection("chunks").document(str(chunk["id"])).set(chunk)

        post_query = self._db.collection("posts").where("source_id", "==", source_id)
        self._delete_query(post_query)
        self._db.collection("posts").document(str(post["id"])).set(post)

        graph = merge_graph(self.load_graph(), source, concepts)
        self.save_graph(graph)
        self.save_document(source_id, markdown)

    def save_document(self, source_id: str, markdown: str) -> None:
        self._db.collection("documents").document(str(source_id)).set({"markdown": markdown})

    def load_document(self, source_id: str) -> str:
        snapshot = self._db.collection("documents").document(str(source_id)).get()
        if not snapshot.exists:
            return ""
        data = snapshot.to_dict() or {}
        return str(data.get("markdown") or "")
