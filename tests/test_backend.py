from __future__ import annotations

import importlib
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ACCOUNT_ID = "mock-user"


def _patch_storage(tmp_path: Path, monkeypatch) -> None:
    import storage

    monkeypatch.setenv("SECONDBRAIN_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("SECONDBRAIN_SEED_MOCK_DATA", "0")
    storage.reset_backend_for_tests()


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import api

    importlib.reload(api)
    client = TestClient(api.app)
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
    assert source["id"]
    assert source["status"] == "processing"
    assert source["progress_stage"] == "validating"
    assert source["progress_percent"] == 5

    sources = client.get("/sources").json()
    posts = client.get("/posts").json()
    graph = client.get("/graph").json()
    detail = client.get(f"/sources/{source['id']}").json()

    assert detail["status"] == "ready"
    assert detail["progress_stage"] == "complete"
    assert detail["progress_percent"] == 100
    assert sources[0]["title"] == "Transformers"
    assert detail["summary"]
    assert isinstance(detail["key_ideas"], list)
    assert isinstance(detail["concepts"], list)
    assert "Transformers" in detail["content"] or "self-attention" in detail["content"]
    assert posts[0]["source_id"] == source["id"]
    assert posts[0]["account_id"] == TEST_ACCOUNT_ID
    assert any(node["type"] == "concept" for node in graph["nodes"])


def test_account_endpoint_returns_mock_account(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/account")

    assert response.status_code == 200
    assert response.json() == {
        "id": TEST_ACCOUNT_ID,
        "name": "SecondBrain",
        "handle": "mock-vault",
        "initials": "SB",
        "email": "mock@example.com",
        "avatar_url": "",
    }


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
    client = TestClient(api.app)

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


def test_pdf_ingestion_uses_extractor(tmp_path: Path, monkeypatch) -> None:
    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.setattr("ingestion.extract_pdf_text", lambda _: "A paper about graph retrieval.")
    monkeypatch.setattr(
        "ingestion.store_original_file",
        lambda file_bytes, filename: {
            "provider": "github",
            "file_id": "abc123sha",
            "web_view_link": "https://github.com/acme/uploads/blob/main/uploads/x/paper.pdf",
            "web_content_link": "https://raw.githubusercontent.com/acme/uploads/main/uploads/x/paper.pdf",
            "filename": filename,
            "mime_type": "application/pdf",
            "size_bytes": len(file_bytes),
        },
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import api

    importlib.reload(api)
    client = TestClient(api.app)
    response = client.post(
        "/sources",
        files={"file": ("paper.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"type": "pdf", "title": "Graph Paper"},
    )

    assert response.status_code == 200
    source = response.json()
    detail = client.get(f"/sources/{source['id']}").json()
    assert source["status"] == "processing"
    assert detail["status"] == "ready"
    assert detail["progress_percent"] == 100
    assert "graph retrieval" in detail["content"]
    assert detail["source_url"] == "https://github.com/acme/uploads/blob/main/uploads/x/paper.pdf"
    assert detail["metadata"]["original_file"] == {
        "provider": "github",
        "file_id": "abc123sha",
        "web_view_link": "https://github.com/acme/uploads/blob/main/uploads/x/paper.pdf",
        "web_content_link": "https://raw.githubusercontent.com/acme/uploads/main/uploads/x/paper.pdf",
        "filename": "paper.pdf",
        "mime_type": "application/pdf",
        "size_bytes": len(b"%PDF-1.4 fake"),
    }


def test_pdf_upload_failure_records_failed_source_without_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import storage

    _patch_storage(tmp_path, monkeypatch)

    def fail_upload(*_: object) -> dict:
        raise RuntimeError("GitHub upload failed: 403 forbidden")

    def fail_extract(*_: object) -> str:
        raise AssertionError("PDF extraction should not run if the upload fails.")

    monkeypatch.setattr("ingestion.store_original_file", fail_upload)
    monkeypatch.setattr("ingestion.extract_pdf_text", fail_extract)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import api

    importlib.reload(api)
    client = TestClient(api.app)

    response = client.post(
        "/sources",
        files={"file": ("paper.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"type": "pdf", "title": "Graph Paper"},
    )

    assert response.status_code == 200
    source = response.json()
    detail = client.get(f"/sources/{source['id']}").json()
    assert detail["status"] == "failed"
    assert "GitHub upload failed" in detail["error"]
    assert detail["progress_stage"] == "uploading"
    assert detail["progress_percent"] == 15
    assert storage.load_chunks(TEST_ACCOUNT_ID) == []
    assert client.get("/posts").json() == []
    assert client.get("/graph").json() == {"nodes": [], "edges": []}


def test_ingestion_failure_records_failed_source_with_progress(
    tmp_path: Path, monkeypatch
) -> None:
    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import ingestion

    def fail_enrichment(*_: object) -> dict:
        raise RuntimeError("enrichment exploded")

    monkeypatch.setattr(ingestion, "enrich_content", fail_enrichment)

    import api

    importlib.reload(api)
    client = TestClient(api.app)

    response = client.post(
        "/sources",
        json={
            "type": "note",
            "title": "Broken",
            "text": "This note validates but fails while enriching.",
        },
    )

    assert response.status_code == 200
    source = response.json()
    assert source["status"] == "processing"

    detail = client.get(f"/sources/{source['id']}").json()
    assert detail["status"] == "failed"
    assert detail["error"] == "enrichment exploded"
    assert detail["progress_stage"] == "enriching"
    assert detail["progress_percent"] == 45


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


def test_chat_agent_tools_search_and_fetch_source_detail(tmp_path: Path, monkeypatch) -> None:
    import storage

    _patch_storage(tmp_path, monkeypatch)
    storage.save_sources(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "source-a",
                "type": "note",
                "title": "Retrieval Detail",
                "summary": "Retrieval narrows context before answering.",
                "key_ideas": ["Search first"],
                "concepts": ["Retrieval"],
                "claims": ["Tool search keeps answers grounded."],
                "content": "Full source content about retrieval and citations.",
            }
        ],
    )
    storage.save_chunks(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "chunk-a",
                "source_id": "source-a",
                "source_title": "Retrieval Detail",
                "section": "Notes",
                "text": "Tool search returns compact snippets before final answers.",
                "embedding": [1.0, 0.0],
            }
        ],
    )
    storage.save_graph(TEST_ACCOUNT_ID, {"nodes": [], "edges": []})

    import api

    importlib.reload(api)
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])

    def fake_answer_with_tools(message, execute_tool):
        search_result = execute_tool("search_knowledge_base", {"query": message})
        detail = execute_tool(
            "get_source_detail",
            {"source_id": search_result["snippets"][0]["source_id"]},
        )
        return f"{detail['summary']} [1]", ["search_knowledge_base", "get_source_detail"]

    monkeypatch.setattr(api, "answer_with_tools", fake_answer_with_tools)
    client = TestClient(api.app)

    response = client.post("/chat", json={"message": "How should retrieval work?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Retrieval narrows context before answering. [1]"
    assert payload["citations"][0]["source_id"] == "source-a"
    assert payload["citations"][0]["retrieval"] == "vector"
    assert payload["tool_calls"] == [
        {"name": "search_knowledge_base"},
        {"name": "get_source_detail"},
    ]


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
                "id": "chunk-b-extra",
                "source_id": "source-b",
                "source_title": "Graph Note",
                "section": "Summary",
                "text": "A duplicate source chunk should not create another graph-neighbor citation.",
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
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])
    client = TestClient(api.app)

    response = client.post("/chat", json={"message": "How does attention connect to graph retrieval?"})

    assert response.status_code == 200
    payload = response.json()
    assert any(citation["source_title"] == "Graph Note" for citation in payload["citations"])
    assert any(citation.get("retrieval") == "graph_neighbor" for citation in payload["citations"])
    graph_citations = [
        citation for citation in payload["citations"] if citation.get("retrieval") == "graph_neighbor"
    ]
    assert len([citation for citation in graph_citations if citation["source_id"] == "source-b"]) == 1
    assert graph_citations[0]["matched_concept_id"] == "concept-retrieval"
    assert graph_citations[0]["matched_concept_label"] == "Retrieval"
    assert payload["graph_context"][0]["concept_label"] == "Retrieval"
    assert payload["graph_context"][0]["expanded_source_ids"] == ["source-b"]


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
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])
    client = TestClient(api.app)

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
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])
    client = TestClient(api.app)

    response = client.post("/chat", json={"message": "Which chunk is compatible?"})

    assert response.status_code == 200
    payload = response.json()
    assert [citation["source_title"] for citation in payload["citations"]] == ["Good Dim"]


def test_firestore_backend_requires_credentials(tmp_path: Path, monkeypatch) -> None:
    import storage

    monkeypatch.setenv("SECONDBRAIN_STORAGE_BACKEND", "firestore")
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_FILE", "")
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "")
    storage.reset_backend_for_tests()

    with pytest.raises(
        RuntimeError,
        match="Firebase credentials are required|Firebase service account file was not found",
    ):
        storage.load_sources(TEST_ACCOUNT_ID)


def test_firebase_admin_app_initialization_is_thread_safe(tmp_path: Path, monkeypatch) -> None:
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

    def initialize_app(credential=None, options=None) -> object:
        calls["initialize"] += 1
        if calls["initialize"] > 1:
            raise ValueError("duplicate")
        return app

    fake_firebase_admin.get_app = get_app
    fake_firebase_admin.initialize_app = initialize_app
    monkeypatch.setitem(sys.modules, "firebase_admin", fake_firebase_admin)
    monkeypatch.setitem(sys.modules, "firebase_admin.credentials", fake_credentials)
    service_account = tmp_path / "service-account.json"
    service_account.write_text("{}")
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_FILE", str(service_account))

    importlib.reload(firebase_admin_app)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: firebase_admin_app.get_firebase_admin_app(), range(2)))

    assert results == [app, app]
    assert calls["initialize"] == 1


def test_firebase_admin_app_accepts_inline_service_account_json(monkeypatch) -> None:
    import firebase_admin_app

    calls: dict[str, object] = {}
    fake_firebase_admin = types.ModuleType("firebase_admin")

    def certificate(value: object) -> str:
        calls["certificate"] = value
        return "cert"

    fake_credentials = types.SimpleNamespace(Certificate=certificate)
    app = object()

    def get_app() -> object:
        raise ValueError("missing")

    def initialize_app(credential=None, options=None) -> object:
        calls["credential"] = credential
        calls["options"] = options
        return app

    fake_firebase_admin.get_app = get_app
    fake_firebase_admin.initialize_app = initialize_app
    monkeypatch.setitem(sys.modules, "firebase_admin", fake_firebase_admin)
    monkeypatch.setitem(sys.modules, "firebase_admin.credentials", fake_credentials)
    monkeypatch.setenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        '{"project_id":"secondbrain-test","client_email":"test@example.com"}',
    )
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "secondbrain-test")
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    importlib.reload(firebase_admin_app)

    assert firebase_admin_app.get_firebase_admin_app(require_credentials=True) is app
    assert calls["certificate"] == {
        "project_id": "secondbrain-test",
        "client_email": "test@example.com",
    }
    assert calls["credential"] == "cert"
    assert calls["options"] == {"projectId": "secondbrain-test"}


def test_firebase_admin_app_allows_firestore_emulator(monkeypatch) -> None:
    import firebase_admin_app

    calls: dict[str, object] = {}
    fake_firebase_admin = types.ModuleType("firebase_admin")
    fake_credentials = types.SimpleNamespace(Certificate=lambda value: value)
    app = object()

    def get_app() -> object:
        raise ValueError("missing")

    def initialize_app(credential=None, options=None) -> object:
        calls["credential"] = credential
        calls["options"] = options
        return app

    fake_firebase_admin.get_app = get_app
    fake_firebase_admin.initialize_app = initialize_app
    monkeypatch.setitem(sys.modules, "firebase_admin", fake_firebase_admin)
    monkeypatch.setitem(sys.modules, "firebase_admin.credentials", fake_credentials)
    monkeypatch.setenv("SECONDBRAIN_STORAGE_BACKEND", "firestore")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "secondbrain-local")
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("FIREBASE_SERVICE_ACCOUNT_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)

    importlib.reload(firebase_admin_app)

    assert firebase_admin_app.get_firebase_admin_app(require_credentials=True) is app
    assert calls["credential"] is None
    assert calls["options"] == {"projectId": "secondbrain-local"}


class _FakeFirestoreSnapshot:
    def __init__(self, reference: "_FakeFirestoreDocument", data: dict | None) -> None:
        self.reference = reference
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict | None:
        return dict(self._data) if self._data is not None else None


class _FakeFirestoreDocument:
    def __init__(self, db: "_FakeFirestoreDb", collection_name: str, document_id: str) -> None:
        self._db = db
        self._collection_name = collection_name
        self._document_id = document_id

    def get(self) -> _FakeFirestoreSnapshot:
        data = self._db.records.get(self._collection_name, {}).get(self._document_id)
        return _FakeFirestoreSnapshot(self, data)

    def set(self, data: dict) -> None:
        self._db.records.setdefault(self._collection_name, {})[self._document_id] = dict(data)

    def delete(self) -> None:
        self._db.records.setdefault(self._collection_name, {}).pop(self._document_id, None)


class _FakeFirestoreQuery:
    def __init__(self, db: "_FakeFirestoreDb", collection_name: str, filters: list[tuple[str, object]]) -> None:
        self._db = db
        self._collection_name = collection_name
        self._filters = filters

    def where(self, field: str, operator: str, value: object) -> "_FakeFirestoreQuery":
        assert operator == "=="
        return _FakeFirestoreQuery(self._db, self._collection_name, self._filters + [(field, value)])

    def stream(self) -> list[_FakeFirestoreSnapshot]:
        snapshots: list[_FakeFirestoreSnapshot] = []
        for document_id, data in self._db.records.get(self._collection_name, {}).items():
            if all(data.get(field) == value for field, value in self._filters):
                reference = _FakeFirestoreDocument(self._db, self._collection_name, document_id)
                snapshots.append(_FakeFirestoreSnapshot(reference, data))
        return snapshots


class _FakeFirestoreCollection:
    def __init__(self, db: "_FakeFirestoreDb", collection_name: str) -> None:
        self._db = db
        self._collection_name = collection_name

    def document(self, document_id: str) -> _FakeFirestoreDocument:
        return _FakeFirestoreDocument(self._db, self._collection_name, document_id)

    def where(self, field: str, operator: str, value: object) -> _FakeFirestoreQuery:
        assert operator == "=="
        return _FakeFirestoreQuery(self._db, self._collection_name, [(field, value)])


class _FakeFirestoreDb:
    def __init__(self) -> None:
        self.records: dict[str, dict[str, dict]] = {}

    def collection(self, name: str) -> _FakeFirestoreCollection:
        return _FakeFirestoreCollection(self, name)


def test_note_ingestion_persists_artifacts_to_firestore(monkeypatch) -> None:
    import ingestion
    import storage
    from storage_backends.firestore import FirestoreStorageBackend

    fake_db = _FakeFirestoreDb()
    monkeypatch.setenv("SECONDBRAIN_STORAGE_BACKEND", "firestore")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(FirestoreStorageBackend, "_build_client", lambda _: fake_db)
    monkeypatch.setattr(
        ingestion,
        "enrich_content",
        lambda *_: {
            "summary": "Firestore stores the ingested note.",
            "key_ideas": ["Persist source", "Persist chunks"],
            "concepts": ["Firestore", "Ingestion"],
            "claims": ["Ingestion writes all artifacts."],
            "questions": ["Which collections are updated?"],
            "social_post": "Ingestion now persists artifacts to Firestore.",
        },
    )
    monkeypatch.setattr(ingestion, "embed_texts", lambda texts: [[1.0, 0.0] for _ in texts])
    storage.reset_backend_for_tests()

    source = ingestion.ingest_source(
        account_id=TEST_ACCOUNT_ID,
        source_type="note",
        title="Firebase Check",
        text="This note should be stored through the Firestore backend.",
    )

    assert source["status"] == "ready"
    stored_source = fake_db.records["sources"][source["id"]]
    assert stored_source["status"] == "ready"
    assert stored_source["progress_stage"] == "complete"
    assert stored_source["content"] == "This note should be stored through the Firestore backend."
    assert stored_source["summary"] == "Firestore stores the ingested note."

    chunks = list(fake_db.records["chunks"].values())
    assert chunks
    assert {chunk["account_id"] for chunk in chunks} == {TEST_ACCOUNT_ID}
    assert {chunk["source_id"] for chunk in chunks} == {source["id"]}
    assert all(chunk["embedding"] == [1.0, 0.0] for chunk in chunks)

    posts = list(fake_db.records["posts"].values())
    assert len(posts) == 1
    assert posts[0]["account_id"] == TEST_ACCOUNT_ID
    assert posts[0]["source_id"] == source["id"]
    assert posts[0]["body"] == "Ingestion now persists artifacts to Firestore."

    graph = fake_db.records["graphs"][TEST_ACCOUNT_ID]
    assert graph["account_id"] == TEST_ACCOUNT_ID
    assert {"source": f"source-{source['id']}", "target": "concept-firestore", "relation": "mentions"} in graph["edges"]


# --- Knowledge Librarian Agent -------------------------------------------------


class _FakeBlock:
    def __init__(self, data: dict) -> None:
        self._data = data

    def __getattr__(self, name: str):
        try:
            return self._data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def model_dump(self, **_: object) -> dict:
        return dict(self._data)


class _FakeResponse:
    def __init__(self, content: list[_FakeBlock]) -> None:
        self.content = content


class _FakeMessages:
    def __init__(self, script: list[list[_FakeBlock]]) -> None:
        self._script = list(script)
        self._index = 0

    def create(self, **_: object) -> _FakeResponse:
        content = self._script[self._index]
        self._index += 1
        return _FakeResponse(content)


class _FakeAnthropic:
    def __init__(self, script: list[list[_FakeBlock]]) -> None:
        self.messages = _FakeMessages(script)


def _tool_use(name: str, source_id: str = "src-agent") -> list[_FakeBlock]:
    return [
        _FakeBlock(
            {
                "type": "tool_use",
                "id": f"tu_{name}",
                "name": name,
                "input": {"source_id": source_id},
            }
        )
    ]


def test_knowledge_agent_processes_pdf_end_to_end(monkeypatch) -> None:
    import agent_tools
    import storage
    from agent import KnowledgeLibrarianAgent

    monkeypatch.setenv("SECONDBRAIN_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("SECONDBRAIN_SEED_MOCK_DATA", "0")
    storage.reset_backend_for_tests()

    monkeypatch.setattr(
        agent_tools,
        "extract_pdf_pages",
        lambda _bytes: [
            {"page": 1, "text": "Graphs connect related concepts. Retrieval finds relevant chunks for answers."},
            {"page": 2, "text": "Embeddings encode meaning into vectors so similarity search can rank context."},
        ],
    )

    storage.append_source(
        TEST_ACCOUNT_ID,
        {
            "id": "src-agent",
            "account_id": TEST_ACCOUNT_ID,
            "type": "pdf",
            "title": "Agent Paper",
            "status": "processing",
        },
    )

    script = [
        _tool_use("inspect_source"),
        _tool_use("extract_pdf_pages"),
        _tool_use("clean_extracted_pages"),
        _tool_use("chunk_clean_pages"),
        _tool_use("embed_and_save_chunks"),
        _tool_use("generate_and_save_memory_posts"),
        _tool_use("build_and_save_graph"),
        _tool_use("finalize_source"),
        [_FakeBlock({"type": "text", "text": '{"status": "completed", "summary": "all done"}'})],
    ]
    agent = KnowledgeLibrarianAgent(anthropic_client=_FakeAnthropic(script))

    result = agent.process_pdf_with_agent(
        account_id=TEST_ACCOUNT_ID,
        source_id="src-agent",
        file_bytes=b"%PDF-1.4 fake",
        title="Agent Paper",
    )

    assert result["status"] == "completed"
    assert result["summary"] == "all done"

    sources = {source["id"]: source for source in storage.load_sources(TEST_ACCOUNT_ID)}
    assert sources["src-agent"]["status"] == "ready"
    assert sources["src-agent"]["agent_status"] == "completed"
    assert sources["src-agent"]["processing_mode"] == "agent"
    assert sources["src-agent"]["total_chunks"] >= 1

    chunks = storage.load_chunks(TEST_ACCOUNT_ID)
    assert chunks and all(chunk["source_id"] == "src-agent" for chunk in chunks)
    assert storage.load_posts(TEST_ACCOUNT_ID)
    assert storage.load_graph(TEST_ACCOUNT_ID)["nodes"]

    run = storage.get_agent_run(result["run_id"])
    assert run["status"] == "completed"
    tool_names = [call["tool_name"] for call in run["tool_calls"]]
    assert tool_names[:3] == ["inspect_source", "extract_pdf_pages", "clean_extracted_pages"]
    assert "finalize_source" in tool_names
    # The trace must never carry raw page/chunk payloads.
    assert all("file_bytes" not in call["input_summary"] for call in run["tool_calls"])


def test_knowledge_agent_validates_tool_order(monkeypatch) -> None:
    import storage
    from agent_tools import KnowledgeAgentTools

    monkeypatch.setenv("SECONDBRAIN_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("SECONDBRAIN_SEED_MOCK_DATA", "0")
    storage.reset_backend_for_tests()

    tools = KnowledgeAgentTools(TEST_ACCOUNT_ID, "src-x", "Title", {})

    # Cleaning before extracting must error, not crash.
    assert tools.clean_extracted_pages()["error"]
    assert tools.chunk_clean_pages()["error"]
    assert tools.embed_and_save_chunks()["error"]
    assert tools.finalize_source()["error"]


def test_agent_run_failure_marks_source_failed(monkeypatch) -> None:
    import agent_tools
    import storage
    from agent import KnowledgeLibrarianAgent

    monkeypatch.setenv("SECONDBRAIN_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("SECONDBRAIN_SEED_MOCK_DATA", "0")
    storage.reset_backend_for_tests()

    def boom(_bytes):
        raise RuntimeError("no readable text")

    monkeypatch.setattr(agent_tools, "extract_pdf_pages", boom)
    storage.append_source(
        TEST_ACCOUNT_ID,
        {"id": "src-bad", "account_id": TEST_ACCOUNT_ID, "type": "pdf", "title": "Bad", "status": "processing"},
    )

    # Claude tries to extract, the tool errors; then Claude gives up with text.
    script = [
        _tool_use("extract_pdf_pages", "src-bad"),
        [_FakeBlock({"type": "text", "text": '{"status": "failed", "summary": "no text"}'})],
    ]
    agent = KnowledgeLibrarianAgent(anthropic_client=_FakeAnthropic(script))
    result = agent.process_pdf_with_agent(
        account_id=TEST_ACCOUNT_ID,
        source_id="src-bad",
        file_bytes=b"%PDF-1.4 fake",
        title="Bad",
    )

    assert result["status"] == "failed"
    sources = {source["id"]: source for source in storage.load_sources(TEST_ACCOUNT_ID)}
    assert sources["src-bad"]["status"] == "failed"


def _rate_limit_error():
    import httpx
    from anthropic import RateLimitError

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, request=request)
    return RateLimitError("rate limited", response=response, body=None)


def test_resilient_anthropic_switches_to_fallback_on_rate_limit() -> None:
    from knowledge_ai import ResilientAnthropic

    error = _rate_limit_error()

    class _Primary:
        def __init__(self) -> None:
            self.messages = self
            self.calls = 0

        def create(self, **_):
            self.calls += 1
            raise error

    class _Fallback:
        def __init__(self) -> None:
            self.messages = self
            self.calls = 0

        def create(self, **_):
            self.calls += 1
            return "FALLBACK_OK"

    primary, fallback = _Primary(), _Fallback()
    client = ResilientAnthropic(primary, fallback)

    assert client.messages.create(model="m", messages=[]) == "FALLBACK_OK"
    assert fallback.calls == 1
    # After a limit hit the primary is on cooldown, so the next call skips it.
    assert client.messages.create(model="m", messages=[]) == "FALLBACK_OK"
    assert primary.calls == 1
    assert fallback.calls == 2


def test_resilient_anthropic_reraises_when_no_fallback() -> None:
    import pytest
    from anthropic import RateLimitError

    from knowledge_ai import ResilientAnthropic

    class _Primary:
        def __init__(self) -> None:
            self.messages = self

        def create(self, **_):
            raise _rate_limit_error()

    client = ResilientAnthropic(_Primary(), None)
    with pytest.raises(RateLimitError):
        client.messages.create(model="m", messages=[])


def test_resilient_anthropic_switches_on_credit_balance_error() -> None:
    import httpx
    from anthropic import BadRequestError

    from knowledge_ai import ResilientAnthropic

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(400, request=request)
    credit_error = BadRequestError(
        "Your credit balance is too low to access the Anthropic API.",
        response=response,
        body=None,
    )

    class _Primary:
        def __init__(self) -> None:
            self.messages = self

        def create(self, **_):
            raise credit_error

    class _Fallback:
        def __init__(self) -> None:
            self.messages = self
            self.calls = 0

        def create(self, **_):
            self.calls += 1
            return "FALLBACK_OK"

    fallback = _Fallback()
    client = ResilientAnthropic(_Primary(), fallback)
    # A 400 credit-balance error is a "limit", so it should fail over.
    assert client.messages.create(model="m", messages=[]) == "FALLBACK_OK"
    assert fallback.calls == 1


def test_resilient_anthropic_reraises_non_limit_errors() -> None:
    import httpx
    import pytest
    from anthropic import BadRequestError

    from knowledge_ai import ResilientAnthropic

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(400, request=request)
    bad_request = BadRequestError("messages: invalid field", response=response, body=None)

    class _Primary:
        def __init__(self) -> None:
            self.messages = self

        def create(self, **_):
            raise bad_request

    class _Fallback:
        def __init__(self) -> None:
            self.messages = self
            self.calls = 0

        def create(self, **_):
            self.calls += 1
            return "FALLBACK_OK"

    fallback = _Fallback()
    client = ResilientAnthropic(_Primary(), fallback)
    # A genuine bad request is NOT a limit — it must propagate, not fail over.
    with pytest.raises(BadRequestError):
        client.messages.create(model="m", messages=[])
    assert fallback.calls == 0


# --- Original-file storage (GitHub default, Drive optional) --------------------


def test_github_storage_upload_returns_neutral_metadata(monkeypatch) -> None:
    import github_storage

    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GITHUB_STORAGE_REPO", "acme/uploads")
    monkeypatch.setenv("GITHUB_STORAGE_BRANCH", "main")

    captured: dict = {}

    def fake_put(repo, path, payload, token):
        captured.update(repo=repo, path=path, payload=payload, token=token)
        return {"content": {"sha": "deadbeef", "html_url": f"https://github.com/{repo}/blob/main/{path}"}}

    monkeypatch.setattr(github_storage, "_put_contents", fake_put)

    result = github_storage.upload_pdf_to_github(b"%PDF-1.4 fake", "My Paper.pdf")

    assert result["provider"] == "github"
    assert result["file_id"] == "deadbeef"
    assert result["mime_type"] == "application/pdf"
    assert result["size_bytes"] == len(b"%PDF-1.4 fake")
    assert result["web_content_link"].startswith("https://raw.githubusercontent.com/acme/uploads/main/uploads/")
    assert result["web_content_link"].endswith("/My-Paper.pdf")
    # request shape: base64 content, branch, unique path under prefix
    import base64

    assert base64.b64decode(captured["payload"]["content"]) == b"%PDF-1.4 fake"
    assert captured["payload"]["branch"] == "main"
    assert captured["token"] == "tok"
    assert captured["path"].startswith("uploads/")


def test_github_storage_requires_token(monkeypatch) -> None:
    import pytest

    import github_storage

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_STORAGE_REPO", "acme/uploads")
    with pytest.raises(github_storage.GitHubStorageError):
        github_storage.upload_pdf_to_github(b"%PDF-1.4 fake", "p.pdf")


def test_file_storage_dispatch_selects_provider(monkeypatch) -> None:
    import file_storage

    monkeypatch.setattr(file_storage, "upload_pdf_to_github", lambda b, fn: {"provider": "github"})
    monkeypatch.setattr(file_storage, "upload_pdf_to_drive", lambda b, fn: {"provider": "google_drive"})

    monkeypatch.setenv("ORIGINAL_FILE_STORAGE", "github")
    assert file_storage.store_original_file(b"x", "f.pdf")["provider"] == "github"

    monkeypatch.setenv("ORIGINAL_FILE_STORAGE", "drive")
    assert file_storage.store_original_file(b"x", "f.pdf")["provider"] == "google_drive"

    # Default (unset) is github.
    monkeypatch.delenv("ORIGINAL_FILE_STORAGE", raising=False)
    assert file_storage.store_original_file(b"x", "f.pdf")["provider"] == "github"
