from __future__ import annotations

import importlib
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ACCOUNT_ID = "google-user-1"
AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def _patch_storage(tmp_path: Path, monkeypatch) -> None:
    import storage

    monkeypatch.setenv("SKYWATCH_STORAGE_BACKEND", "memory")
    storage.reset_backend_for_tests()


def _patch_auth(api, monkeypatch, account_id: str = TEST_ACCOUNT_ID) -> None:
    monkeypatch.setattr(
        api,
        "verify_firebase_token",
        lambda _: {
            "uid": account_id,
            "email": f"{account_id}@example.com",
            "name": "Test User",
            "picture": "https://example.com/avatar.png",
        },
    )


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import api

    importlib.reload(api)
    _patch_auth(api, monkeypatch)
    client = TestClient(api.app)
    client.headers.update(AUTH_HEADERS)
    return client


def test_note_ingestion_creates_knowledge_artifacts(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/sources",
        json={
            "type": "note",
            "title": "Transformers",
            "text": "Transformers use self-attention to connect tokens. Attention helps models scale.",
        },
    )

    assert response.status_code == 200
    source = response.json()
    assert source["status"] == "ready"

    sources = client.get("/sources").json()
    posts = client.get("/posts").json()
    graph = client.get("/graph").json()
    detail = client.get(f"/sources/{source['id']}").json()

    assert sources[0]["title"] == "Transformers"
    assert detail["summary"]
    assert isinstance(detail["key_ideas"], list)
    assert isinstance(detail["concepts"], list)
    assert "Transformers" in detail["content"] or "self-attention" in detail["content"]
    assert posts[0]["source_id"] == source["id"]
    assert posts[0]["account_id"] == TEST_ACCOUNT_ID
    assert any(node["type"] == "concept" for node in graph["nodes"])


def test_account_endpoint_returns_google_account(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/account")

    assert response.status_code == 200
    assert response.json() == {
        "id": TEST_ACCOUNT_ID,
        "name": "Test User",
        "handle": TEST_ACCOUNT_ID,
        "initials": "TU",
        "email": f"{TEST_ACCOUNT_ID}@example.com",
        "avatar_url": "https://example.com/avatar.png",
    }


def test_unauthenticated_request_is_rejected(tmp_path: Path, monkeypatch) -> None:
    _patch_storage(tmp_path, monkeypatch)

    import api

    importlib.reload(api)
    client = TestClient(api.app)

    response = client.get("/sources")

    assert response.status_code == 401


def test_posts_endpoint_filters_by_account(tmp_path: Path, monkeypatch) -> None:
    import storage

    _patch_storage(tmp_path, monkeypatch)
    storage.save_posts(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "user-post",
                "account_id": TEST_ACCOUNT_ID,
                "source_id": "user-source",
                "source_title": "User Source",
                "body": "User body",
                "created_at": "2026-06-20T00:00:00+00:00",
            }
        ]
    )
    storage.save_posts(
        "other-user",
        [
            {
                "id": "other-post",
                "account_id": "other-user",
                "source_id": "other-source",
                "source_title": "Other Source",
                "body": "Other body",
                "created_at": "2026-06-20T01:00:00+00:00",
            }
        ],
    )

    import api

    importlib.reload(api)
    _patch_auth(api, monkeypatch)
    client = TestClient(api.app)
    client.headers.update(AUTH_HEADERS)

    response = client.get("/posts")

    assert response.status_code == 200
    assert [post["id"] for post in response.json()] == ["user-post"]


def test_invalid_note_does_not_persist_source(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post("/sources", json={"type": "note", "title": "Empty", "text": "   "})

    assert response.status_code == 400
    assert "Note text is required" in response.json()["detail"]
    assert client.get("/sources").json() == []
    assert client.get("/posts").json() == []
    assert client.get("/graph").json() == {"nodes": [], "edges": []}


def test_source_detail_is_account_scoped(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    created = client.post(
        "/sources",
        json={
            "type": "note",
            "title": "Private Note",
            "text": "This note belongs to one Google account.",
        },
    )
    source_id = created.json()["id"]

    import api

    _patch_auth(api, monkeypatch, account_id="other-user")
    other_client = TestClient(api.app)
    other_client.headers.update(AUTH_HEADERS)

    response = other_client.get(f"/sources/{source_id}")

    assert response.status_code == 404


def test_pdf_ingestion_uses_extractor(tmp_path: Path, monkeypatch) -> None:
    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.setattr("ingestion.extract_pdf_text", lambda _: "A paper about graph retrieval.")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import api

    importlib.reload(api)
    _patch_auth(api, monkeypatch)
    client = TestClient(api.app)
    client.headers.update(AUTH_HEADERS)
    response = client.post(
        "/sources",
        files={"file": ("paper.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"type": "pdf", "title": "Graph Paper"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert "graph retrieval" in client.get(f"/sources/{response.json()['id']}").json()["content"]


def test_missing_pdf_does_not_persist_source(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post("/sources", data={"type": "pdf", "title": "Missing PDF"})

    assert response.status_code == 400
    assert "PDF upload is required" in response.json()["detail"]
    assert client.get("/sources").json() == []
    assert client.get("/posts").json() == []


def test_youtube_ingestion_is_deferred_without_persistence(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/sources",
        json={"type": "youtube", "title": "Talk", "source_url": "https://youtu.be/abc123456"},
    )

    assert response.status_code == 501
    assert "Video ingestion" in response.json()["detail"]
    assert client.get("/sources").json() == []
    assert client.get("/posts").json() == []


def test_parallel_note_ingestion_preserves_all_artifacts(tmp_path: Path, monkeypatch) -> None:
    import storage

    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import ingestion

    importlib.reload(ingestion)

    def ingest(index: int) -> dict:
        return ingestion.ingest_source(
            account_id=TEST_ACCOUNT_ID,
            source_type="note",
            title=f"Note {index}",
            text=f"Concurrent note {index} about storage and retrieval.",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(ingest, range(2)))

    assert all(source["status"] == "ready" for source in results)
    assert len(storage.load_sources(TEST_ACCOUNT_ID)) == 2
    assert len(storage.load_posts(TEST_ACCOUNT_ID)) == 2
    chunk_source_ids = {chunk["source_id"] for chunk in storage.load_chunks(TEST_ACCOUNT_ID)}
    assert {source["id"] for source in results}.issubset(chunk_source_ids)


def test_chat_returns_answer_and_citations(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    client.post(
        "/sources",
        json={
            "type": "note",
            "title": "Retrieval",
            "text": "Vector search retrieves relevant chunks for chatbot answers.",
        },
    )

    response = client.post("/chat", json={"message": "How does retrieval help chat?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]
    assert payload["citations"]
    assert payload["citations"][0]["source_title"] == "Retrieval"


def test_chat_expands_context_with_graph_neighbors(tmp_path: Path, monkeypatch) -> None:
    import storage

    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    storage.save_chunks(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "chunk-a",
                "source_id": "source-a",
                "source_title": "Attention Note",
                "section": "Notes",
                "text": "Attention mechanisms help retrieval focus on relevant tokens.",
                "embedding": [1.0, 0.0],
            },
            {
                "id": "chunk-b",
                "source_id": "source-b",
                "source_title": "Graph Note",
                "section": "Notes",
                "text": "GraphRAG follows related concepts to bring connected sources into context.",
                "embedding": [-1.0, 0.0],
            },
            {
                "id": "chunk-c",
                "source_id": "source-c",
                "source_title": "Filler C",
                "section": "Notes",
                "text": "Unrelated filler chunk C.",
                "embedding": [0.9, 0.0],
            },
            {
                "id": "chunk-d",
                "source_id": "source-d",
                "source_title": "Filler D",
                "section": "Notes",
                "text": "Unrelated filler chunk D.",
                "embedding": [0.8, 0.0],
            },
            {
                "id": "chunk-e",
                "source_id": "source-e",
                "source_title": "Filler E",
                "section": "Notes",
                "text": "Unrelated filler chunk E.",
                "embedding": [0.7, 0.0],
            },
            {
                "id": "chunk-f",
                "source_id": "source-f",
                "source_title": "Filler F",
                "section": "Notes",
                "text": "Unrelated filler chunk F.",
                "embedding": [0.6, 0.0],
            },
            {
                "id": "chunk-g",
                "source_id": "source-g",
                "source_title": "Filler G",
                "section": "Notes",
                "text": "Unrelated filler chunk G.",
                "embedding": [0.5, 0.0],
            },
        ]
    )
    storage.save_graph(
        TEST_ACCOUNT_ID,
        {
            "nodes": [
                {"id": "source-source-a", "label": "Attention Note", "type": "source"},
                {"id": "source-source-b", "label": "Graph Note", "type": "source"},
                {"id": "concept-retrieval", "label": "Retrieval", "type": "concept"},
            ],
            "edges": [
                {"source": "source-source-a", "target": "concept-retrieval", "relation": "mentions"},
                {"source": "source-source-b", "target": "concept-retrieval", "relation": "mentions"},
            ],
        }
    )

    import api

    importlib.reload(api)
    _patch_auth(api, monkeypatch)
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])
    client = TestClient(api.app)
    client.headers.update(AUTH_HEADERS)

    response = client.post("/chat", json={"message": "How does attention connect to graph retrieval?"})

    assert response.status_code == 200
    payload = response.json()
    assert any(citation["source_title"] == "Graph Note" for citation in payload["citations"])
    assert any(citation.get("retrieval") == "graph_neighbor" for citation in payload["citations"])
    assert payload["graph_context"][0]["concept_label"] == "Retrieval"


def test_chat_graphrag_falls_back_without_graph(tmp_path: Path, monkeypatch) -> None:
    import storage

    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    storage.save_chunks(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "chunk-a",
                "source_id": "source-a",
                "source_title": "Solo Note",
                "section": "Notes",
                "text": "Solo vector context still works without graph data.",
                "embedding": [1.0, 0.0],
            }
        ]
    )
    storage.save_graph(TEST_ACCOUNT_ID, {"nodes": [], "edges": []})

    import api

    importlib.reload(api)
    _patch_auth(api, monkeypatch)
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])
    client = TestClient(api.app)
    client.headers.update(AUTH_HEADERS)

    response = client.post("/chat", json={"message": "Does chat still work?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"][0]["source_title"] == "Solo Note"
    assert payload["graph_context"] == []


def test_chat_skips_chunks_with_incompatible_embedding_dimensions(
    tmp_path: Path, monkeypatch
) -> None:
    import storage

    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    storage.save_chunks(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "bad-dim",
                "source_id": "bad",
                "source_title": "Bad Dim",
                "section": "Notes",
                "text": "This chunk should be ignored.",
                "embedding": [1.0],
            },
            {
                "id": "good-dim",
                "source_id": "good",
                "source_title": "Good Dim",
                "section": "Notes",
                "text": "Compatible embedding dimensions should be ranked.",
                "embedding": [1.0, 0.0],
            },
        ]
    )
    storage.save_graph(TEST_ACCOUNT_ID, {"nodes": [], "edges": []})

    import api

    importlib.reload(api)
    _patch_auth(api, monkeypatch)
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])
    client = TestClient(api.app)
    client.headers.update(AUTH_HEADERS)

    response = client.post("/chat", json={"message": "Which chunk is compatible?"})

    assert response.status_code == 200
    payload = response.json()
    assert [citation["source_title"] for citation in payload["citations"]] == ["Good Dim"]


def test_firestore_backend_requires_credentials(tmp_path: Path, monkeypatch) -> None:
    import storage

    monkeypatch.delenv("SKYWATCH_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    storage.reset_backend_for_tests()

    with pytest.raises(RuntimeError, match="Firebase credentials are required"):
        storage.load_sources(TEST_ACCOUNT_ID)


def test_firebase_admin_app_initialization_is_thread_safe(monkeypatch) -> None:
    import firebase_admin_app

    calls = {"get": 0, "initialize": 0}
    fake_firebase_admin = types.ModuleType("firebase_admin")
    fake_credentials = types.SimpleNamespace(Certificate=lambda path: f"cert:{path}")
    app = object()

    def get_app() -> object:
        calls["get"] += 1
        if calls["initialize"]:
            return app
        raise ValueError("missing")

    def initialize_app(credential=None) -> object:
        calls["initialize"] += 1
        if calls["initialize"] > 1:
            raise ValueError("duplicate")
        return app

    fake_firebase_admin.get_app = get_app
    fake_firebase_admin.initialize_app = initialize_app
    monkeypatch.setitem(sys.modules, "firebase_admin", fake_firebase_admin)
    monkeypatch.setitem(sys.modules, "firebase_admin.credentials", fake_credentials)
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_FILE", "/tmp/service-account.json")

    importlib.reload(firebase_admin_app)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: firebase_admin_app.get_firebase_admin_app(), range(2)))

    assert results == [app, app]
    assert calls["initialize"] == 1
