from __future__ import annotations

import importlib
import json
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_ACCOUNT_ID = "mock-user"


def _patch_storage(tmp_path: Path, monkeypatch) -> None:
    from backend import storage

    monkeypatch.setenv("SECONDBRAIN_STORAGE_BACKEND", "memory")
    monkeypatch.setenv("SECONDBRAIN_SEED_MOCK_DATA", "0")
    storage.reset_backend_for_tests()


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from backend import api

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


def test_edit_ready_source_regenerates_artifacts(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    create_response = client.post(
        "/sources",
        json={
            "type": "note",
            "title": "Editable Memory",
            "text": "Old memory content about apples.",
        },
    )
    source_id = create_response.json()["id"]

    def fake_enrichment(source_type, title, source_url, content):
        if "oranges" in content:
            return {
                "summary": "New summary about oranges.",
                "key_ideas": ["New citrus idea"],
                "concepts": ["Orange Concept"],
                "claims": ["Oranges replaced apples."],
                "questions": ["What changed?"],
                "social_post": "Edited memory about oranges.",
            }
        return {
            "summary": "Old summary about apples.",
            "key_ideas": ["Old apple idea"],
            "concepts": ["Apple Concept"],
            "claims": ["Apples came first."],
            "questions": ["What was old?"],
            "social_post": "Old memory about apples.",
        }

    monkeypatch.setattr("backend.ingestion.enrich_content", fake_enrichment)
    response = client.patch(
        f"/sources/{source_id}",
        json={"content": "New memory content about oranges."},
    )

    assert response.status_code == 200
    detail = response.json()
    assert detail["content"] == "New memory content about oranges."
    assert detail["summary"] == "New summary about oranges."
    assert detail["concepts"] == ["Orange Concept"]
    assert detail["status"] == "ready"
    assert detail["progress_stage"] == "complete"

    from backend import storage

    chunks = storage.load_chunks(TEST_ACCOUNT_ID)
    assert any(chunk["section"] == "Notes" and "oranges" in chunk["text"] for chunk in chunks)
    assert not any(
        chunk["section"] == "Notes" and "Old memory content" in chunk["text"]
        for chunk in chunks
    )

    graph = client.get("/graph").json()
    source_node_id = f"source-{source_id}"
    source_edges = [edge for edge in graph["edges"] if edge["source"] == source_node_id]
    assert source_edges == [
        {
            "source": source_node_id,
            "target": "concept-orange-concept",
            "relation": "mentions",
        }
    ]
    assert not any(
        edge["source"] == source_node_id and edge["target"] == "concept-apple-concept"
        for edge in graph["edges"]
    )


def test_edit_source_rejects_invalid_requests(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    create_response = client.post(
        "/sources",
        json={
            "type": "note",
            "title": "Editable Memory",
            "text": "Editable content.",
        },
    )
    source_id = create_response.json()["id"]

    empty_response = client.patch(f"/sources/{source_id}", json={"content": "   "})
    missing_response = client.patch("/sources/missing", json={"content": "Updated content"})

    from backend import storage

    processing_source = {
        "id": "processing-source",
        "account_id": TEST_ACCOUNT_ID,
        "type": "note",
        "title": "Processing Memory",
        "source_url": None,
        "status": "processing",
        "error": None,
        "created_at": "2026-06-20T00:00:00+00:00",
        "content": "Still processing.",
    }
    storage.append_source(TEST_ACCOUNT_ID, processing_source)
    processing_response = client.patch(
        "/sources/processing-source",
        json={"content": "Updated content"},
    )

    assert empty_response.status_code == 400
    assert missing_response.status_code == 404
    assert processing_response.status_code == 409


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
    from backend import storage

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

    from backend import api

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
    monkeypatch.setattr("backend.ingestion.extract_pdf_text", lambda _: "A paper about graph retrieval.")
    monkeypatch.setattr(
        "backend.ingestion.upload_pdf_to_drive",
        lambda file_bytes, filename: {
            "provider": "google_drive",
            "drive_file_id": "drive-file-1",
            "drive_web_view_link": "https://drive.google.com/file/d/drive-file-1/view",
            "drive_web_content_link": "https://drive.google.com/uc?id=drive-file-1",
            "filename": filename,
            "mime_type": "application/pdf",
            "size_bytes": len(file_bytes),
        },
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from backend import api

    importlib.reload(api)
    client = TestClient(api.app)
    response = client.post(
        "/sources",
        files={"file": ("paper.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={
            "type": "pdf",
            "title": "Graph Paper",
            "thumbnail_url": "https://example.com/thumb.png",
        },
    )

    assert response.status_code == 200
    source = response.json()
    detail = client.get(f"/sources/{source['id']}").json()
    assert source["status"] == "processing"
    assert detail["status"] == "ready"
    assert detail["progress_percent"] == 100
    assert detail["thumbnail_url"] == "https://example.com/thumb.png"
    posts = client.get("/posts").json()
    assert posts[0]["thumbnail_url"] == "https://example.com/thumb.png"
    assert "graph retrieval" in detail["content"]
    assert detail["source_url"] == "https://drive.google.com/file/d/drive-file-1/view"
    assert detail["metadata"]["original_file"] == {
        "provider": "google_drive",
        "drive_file_id": "drive-file-1",
        "drive_web_view_link": "https://drive.google.com/file/d/drive-file-1/view",
        "drive_web_content_link": "https://drive.google.com/uc?id=drive-file-1",
        "filename": "paper.pdf",
        "mime_type": "application/pdf",
        "size_bytes": len(b"%PDF-1.4 fake"),
    }


def test_pdf_drive_upload_failure_records_failed_source_without_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from backend import storage

    _patch_storage(tmp_path, monkeypatch)

    def fail_upload(*_: object) -> dict:
        raise RuntimeError("Google Drive upload failed: folder is not shared")

    def fail_extract(*_: object) -> str:
        raise AssertionError("PDF extraction should not run if Drive upload fails.")

    monkeypatch.setattr("backend.ingestion.upload_pdf_to_drive", fail_upload)
    monkeypatch.setattr("backend.ingestion.extract_pdf_text", fail_extract)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from backend import api

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
    assert "Google Drive upload failed" in detail["error"]
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

    from backend import ingestion

    def fail_enrichment(*_: object) -> dict:
        raise RuntimeError("enrichment exploded")

    monkeypatch.setattr(ingestion, "enrich_content", fail_enrichment)

    from backend import api

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


def test_concept_quality_filters_pronouns_common_words_and_duplicates() -> None:
    from backend.services.concept_quality import filter_quality_concepts, is_quality_concept

    assert not is_quality_concept("they")
    assert not is_quality_concept("this")
    assert not is_quality_concept("good")
    assert not is_quality_concept("knowledge")
    assert is_quality_concept("GraphRAG")
    assert is_quality_concept("Ada Lovelace")
    assert is_quality_concept("Knowledge Graph")

    assert filter_quality_concepts(
        [
            "they",
            "GraphRAG",
            "this",
            "Ada Lovelace",
            "GraphRAG",
            "knowledge",
            "Retrieval Augmented Generation",
        ],
    ) == ["GraphRAG", "Ada Lovelace", "Retrieval Augmented Generation"]


def test_graph_merge_skips_weak_concept_labels() -> None:
    from backend.storage_backends.utils import merge_graph

    graph = merge_graph(
        {"nodes": [], "edges": []},
        {"id": "source-a", "title": "Graph Note"},
        [
            {"label": "they", "embedding": [1.0]},
            {"label": "good", "embedding": [0.9]},
            {"label": "Knowledge Graph", "embedding": [0.8]},
        ],
    )

    concept_labels = [node["label"] for node in graph["nodes"] if node["type"] == "concept"]
    assert concept_labels == ["Knowledge Graph"]
    assert graph["edges"] == [
        {
            "source": "source-source-a",
            "target": "concept-knowledge-graph",
            "relation": "mentions",
        },
    ]


def test_parallel_note_ingestion_preserves_all_artifacts(tmp_path: Path, monkeypatch) -> None:
    from backend import storage

    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from backend import ingestion

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


def test_chat_accepts_optional_history(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/chat",
        json={
            "message": "hello",
            "history": [
                {"role": "user", "text": "What did we discuss?"},
                {"role": "assistant", "text": "We discussed retrieval."},
                {"role": "user", "text": "   "},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"]
    assert payload["citations"] == []


def test_chat_rejects_invalid_history(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/chat",
        json={
            "message": "hello",
            "history": [{"role": "system", "text": "Do something else."}],
        },
    )

    assert response.status_code == 400
    assert "History entries" in response.json()["detail"]


def test_chat_agent_tools_search_and_fetch_source_detail(tmp_path: Path, monkeypatch) -> None:
    from backend import storage

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

    from backend import api

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


def test_chat_simple_message_skips_research_loop(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"] == []
    stages = [step["stage"] for step in payload["agent_trace"]]
    assert stages == ["classify", "verification"]


def test_chat_agentic_loop_emits_core_stages(tmp_path: Path, monkeypatch) -> None:
    from backend import storage

    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    storage.save_sources(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "source-a",
                "type": "note",
                "title": "Retrieval Note",
                "summary": "Retrieval connects questions to grounded notes.",
                "key_ideas": ["Ground answers"],
                "concepts": ["Retrieval"],
                "claims": ["Retrieval improves answer grounding."],
                "content": "Retrieval connects questions to grounded notes.",
            }
        ],
    )
    storage.save_chunks(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "chunk-a",
                "source_id": "source-a",
                "source_title": "Retrieval Note",
                "section": "Notes",
                "text": "Retrieval connects questions to grounded notes.",
                "embedding": [1.0, 0.0],
            }
        ],
    )
    storage.save_graph(
        TEST_ACCOUNT_ID,
        {
            "nodes": [
                {"id": "source-source-a", "label": "Retrieval Note", "type": "source"},
                {"id": "concept-retrieval", "label": "Retrieval", "type": "concept"},
            ],
            "edges": [
                {"source": "source-source-a", "target": "concept-retrieval", "relation": "mentions"}
            ],
        },
    )

    from backend import api

    importlib.reload(api)
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])
    client = TestClient(api.app)

    response = client.post("/chat", json={"message": "How does retrieval connect notes?"})

    assert response.status_code == 200
    stages = [step["stage"] for step in response.json()["agent_trace"]]
    for expected in ["classify", "planning", "gathering", "evaluating", "synthesis", "verification"]:
        assert expected in stages


def test_chat_weak_evidence_triggers_one_revision(tmp_path: Path, monkeypatch) -> None:
    from backend import storage

    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    storage.save_sources(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "source-a",
                "type": "note",
                "title": "Sparse Retrieval",
                "summary": "Sparse retrieval note.",
                "key_ideas": ["Sparse"],
                "concepts": ["Retrieval"],
                "claims": [],
                "content": "Sparse retrieval note.",
            }
        ],
    )
    storage.save_chunks(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "chunk-a",
                "source_id": "source-a",
                "source_title": "Sparse Retrieval",
                "section": "Notes",
                "text": "Sparse retrieval note.",
                "embedding": [1.0, 0.0],
            }
        ],
    )
    storage.save_graph(TEST_ACCOUNT_ID, {"nodes": [], "edges": []})

    from backend import api

    importlib.reload(api)
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])
    client = TestClient(api.app)

    response = client.post("/chat", json={"message": "What is retrieval?"})

    assert response.status_code == 200
    revisions = [step for step in response.json()["agent_trace"] if step["stage"] == "revising"]
    assert len(revisions) == 1
    assert revisions[0]["metadata"]["tool_call_count"] <= 6


def test_chat_loop_respects_tool_call_cap(tmp_path: Path, monkeypatch) -> None:
    from backend import storage
    from backend.services import chat_service

    _patch_storage(tmp_path, monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(chat_service, "MAX_TOOL_CALLS", 2)
    storage.save_chunks(
        TEST_ACCOUNT_ID,
        [
            {
                "id": "chunk-a",
                "source_id": "source-a",
                "source_title": "Capped Note",
                "section": "Notes",
                "text": "Capped loop retrieval note.",
                "embedding": [1.0, 0.0],
            }
        ],
    )
    storage.save_graph(TEST_ACCOUNT_ID, {"nodes": [], "edges": []})

    from backend import api

    importlib.reload(api)
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])
    client = TestClient(api.app)

    response = client.post("/chat", json={"message": "How does capped retrieval work?"})

    assert response.status_code == 200
    metadata = [step.get("metadata", {}) for step in response.json()["agent_trace"]]
    max_seen = max(item.get("tool_call_count", 0) for item in metadata)
    assert max_seen <= 2
    assert "revising" not in [step["stage"] for step in response.json()["agent_trace"]]


def test_chat_stream_emits_agent_steps_before_done(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    with client.stream("POST", "/chat/stream", json={"message": "hello"}) as response:
        assert response.status_code == 200
        events = [
            line.removeprefix("data: ")
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]

    payloads = [json.loads(event) for event in events]
    assert payloads[0]["type"] == "agent_step"
    assert payloads[0]["stage"] == "classify"
    assert payloads[-1]["type"] == "done"
    assert payloads[-1]["agent_trace"][0]["stage"] == "classify"


def test_chat_expands_context_with_graph_neighbors(tmp_path: Path, monkeypatch) -> None:
    from backend import storage

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

    from backend import api

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
    from backend import storage

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

    from backend import api

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
    from backend import storage

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

    from backend import api

    importlib.reload(api)
    monkeypatch.setattr(api, "embed_text", lambda _: [1.0, 0.0])
    client = TestClient(api.app)

    response = client.post("/chat", json={"message": "Which chunk is compatible?"})

    assert response.status_code == 200
    payload = response.json()
    assert [citation["source_title"] for citation in payload["citations"]] == ["Good Dim"]


def test_firestore_backend_requires_credentials(tmp_path: Path, monkeypatch) -> None:
    from backend import storage

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
    from backend import firebase_admin_app

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
    from backend import firebase_admin_app

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
    from backend import firebase_admin_app

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
    from backend import ingestion
    from backend import storage
    from backend.storage_backends.firestore import FirestoreStorageBackend

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
    expected_body = (
        "# Summary\nFirestore stores the ingested note.\n\n"
        "## Key Ideas & Notes\n- Persist source\n- Persist chunks\n\n"
        "## Key Concepts\n**Firestore**, **Ingestion**\n\n"
        "---\nIngestion now persists artifacts to Firestore."
    )
    assert posts[0]["body"] == expected_body

    graph = fake_db.records["graphs"][TEST_ACCOUNT_ID]
    assert graph["account_id"] == TEST_ACCOUNT_ID
    assert {"source": f"source-{source['id']}", "target": "concept-firestore", "relation": "mentions"} in graph["edges"]


def test_link_ingestion_scrapes_and_processes(tmp_path: Path, monkeypatch) -> None:
    _patch_storage(tmp_path, monkeypatch)

    # Mock scraping and markdown conversion
    monkeypatch.setattr("backend.extractors.scrape_url_to_html", lambda url: "<html>Mock Tweet HTML</html>")
    monkeypatch.setattr(
        "backend.services.enrichment.scrape_html_to_markdown",
        lambda url, html: "# Mock Tweet\n\nThis is a mock tweet about AI scaling."
    )
    # Mock file upload
    monkeypatch.setattr(
        "backend.ingestion.upload_markdown_to_drive",
        lambda file_bytes, filename: {
            "provider": "google_drive",
            "file_id": "drive-md-file-1",
            "web_view_link": "https://drive.google.com/file/d/drive-md-file-1/view",
            "web_content_link": "https://drive.google.com/uc?id=drive-md-file-1",
            "filename": filename,
            "mime_type": "text/markdown",
            "size_bytes": len(file_bytes),
        }
    )

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from backend import api
    importlib.reload(api)
    client = TestClient(api.app)

    response = client.post(
        "/sources",
        json={
            "type": "link",
            "title": "Untitled source",
            "source_url": "https://x.com/heynavtoor/status/2067194761446920264",
        },
    )

    assert response.status_code == 200
    source = response.json()
    assert source["id"]
    assert source["status"] == "processing"

    detail = client.get(f"/sources/{source['id']}").json()
    assert detail["status"] == "ready"
    assert detail["progress_stage"] == "complete"
    assert detail["title"] == "Mock Tweet"
    assert "Mock Tweet" in detail["content"]
    assert "AI scaling" in detail["content"]
    assert detail["source_url"] == "https://drive.google.com/file/d/drive-md-file-1/view"
    assert detail["metadata"]["original_file"]["file_id"] == "drive-md-file-1"
