from __future__ import annotations

import threading
import os
from copy import deepcopy
from typing import Any

from storage_backends.base import StorageBackend
from storage_backends.utils import coerce_graph, merge_graph


def _seed_embeddings(texts: list[str]) -> list[list[float]]:
    """Compute real embeddings for seed data so dimensions match live queries."""
    try:
        from embeddings import embed_texts
        return embed_texts(texts)
    except Exception:
        # If embedding fails at seed time, return empty lists — chunks will be
        # skipped by _rank_chunks but won't break anything.
        return [[] for _ in texts]


class MemoryStorageBackend(StorageBackend):
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.sources: dict[str, dict[str, Any]] = {}
        self.chunks: dict[str, dict[str, Any]] = {}
        self.posts: dict[str, dict[str, Any]] = {}
        self.graphs: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self.accounts: dict[str, dict[str, str]] = {}
        self.agent_runs: dict[str, dict[str, Any]] = {}
        if os.getenv("SECONDBRAIN_SEED_MOCK_DATA", "1") != "0":
            self._seed_mock_data()

    def _seed_mock_data(self) -> None:
        account_id = "mock-user"
        self.accounts[account_id] = {
            "id": account_id,
            "name": "SecondBrain",
            "handle": "mock-vault",
            "initials": "SB",
            "email": "mock@example.com",
            "avatar_url": "",
        }
        self.sources = {
            "mock-source-rag": {
                "id": "mock-source-rag",
                "account_id": account_id,
                "type": "note",
                "title": "GraphRAG Notes",
                "source_url": None,
                "status": "ready",
                "error": None,
                "created_at": "2026-06-20T18:00:00+00:00",
                "content": "GraphRAG combines vector retrieval with graph neighborhoods to pull connected concepts into an answer.",
                "summary": "Graph-aware retrieval improves chat context by following relationships between sources and concepts.",
                "key_ideas": ["Rank chunks by semantic similarity", "Expand context through concept neighbors"],
                "concepts": ["GraphRAG", "Retrieval", "Knowledge Graph"],
                "claims": ["Graph structure can reveal useful adjacent context."],
                "questions": ["Which concepts connect otherwise separate notes?"],
            },
            "mock-source-attention": {
                "id": "mock-source-attention",
                "account_id": account_id,
                "type": "note",
                "title": "Attention Refresher",
                "source_url": None,
                "status": "ready",
                "error": None,
                "created_at": "2026-06-20T17:30:00+00:00",
                "content": "Attention lets a model weight relevant tokens so retrieved passages can be summarized with focus.",
                "summary": "Attention highlights relevant token relationships for focused summarization.",
                "key_ideas": ["Attention scores relationships", "Focused context helps generated answers"],
                "concepts": ["Attention", "Retrieval"],
                "claims": ["Attention helps models prioritize useful context."],
                "questions": ["How should retrieved chunks be ordered before answering?"],
            },
        }
        self.posts = {
            "mock-post-rag": {
                "id": "mock-post-rag",
                "account_id": account_id,
                "source_id": "mock-source-rag",
                "source_title": "GraphRAG Notes",
                "body": "GraphRAG is the difference between finding a matching note and following the trail of related ideas.",
                "created_at": "2026-06-20T18:01:00+00:00",
            },
            "mock-post-attention": {
                "id": "mock-post-attention",
                "account_id": account_id,
                "source_id": "mock-source-attention",
                "source_title": "Attention Refresher",
                "body": "Attention is a routing mechanism for focus: it helps a model decide which context deserves weight.",
                "created_at": "2026-06-20T17:31:00+00:00",
            },
        }

        # Compute embeddings using the real embedder so dimensions match live
        # queries. Hardcoded 2-dim vectors caused chat to return zero citations
        # because _rank_chunks skips chunks whose dim ≠ query dim.
        rag_summary = self.sources["mock-source-rag"]["summary"]
        attention_summary = self.sources["mock-source-attention"]["summary"]
        try:
            from embeddings import current_embedding_model
            embeddings = _seed_embeddings([rag_summary, attention_summary])
            model = current_embedding_model()
        except Exception:
            embeddings = [[], []]
            model = "unknown"

        rag_emb, attention_emb = embeddings[0], embeddings[1]
        self.chunks = {
            "mock-chunk-rag": {
                "id": "mock-chunk-rag",
                "account_id": account_id,
                "source_id": "mock-source-rag",
                "source_title": "GraphRAG Notes",
                "section": "Summary",
                "text": rag_summary,
                "embedding": rag_emb,
                "embedding_model": model,
                "embedding_dim": len(rag_emb),
            },
            "mock-chunk-attention": {
                "id": "mock-chunk-attention",
                "account_id": account_id,
                "source_id": "mock-source-attention",
                "source_title": "Attention Refresher",
                "section": "Summary",
                "text": attention_summary,
                "embedding": attention_emb,
                "embedding_model": model,
                "embedding_dim": len(attention_emb),
            },
        }
        self.graphs = {
            account_id: {
                "nodes": [
                    {"id": "source-mock-source-rag", "label": "GraphRAG Notes", "type": "source"},
                    {"id": "source-mock-source-attention", "label": "Attention Refresher", "type": "source"},
                    {"id": "concept-retrieval", "label": "Retrieval", "type": "concept"},
                    {"id": "concept-knowledge-graph", "label": "Knowledge Graph", "type": "concept"},
                    {"id": "concept-attention", "label": "Attention", "type": "concept"},
                ],
                "edges": [
                    {"source": "source-mock-source-rag", "target": "concept-retrieval", "relation": "mentions"},
                    {"source": "source-mock-source-rag", "target": "concept-knowledge-graph", "relation": "mentions"},
                    {"source": "source-mock-source-attention", "target": "concept-retrieval", "relation": "mentions"},
                    {"source": "source-mock-source-attention", "target": "concept-attention", "relation": "mentions"},
                ],
            }
        }

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

    def create_agent_run(self, run: dict[str, Any]) -> None:
        with self._lock:
            self.agent_runs[str(run["run_id"])] = deepcopy(run)

    def update_agent_run(self, run_id: str, updates: dict[str, Any]) -> None:
        with self._lock:
            run = self.agent_runs.get(str(run_id))
            if run is not None:
                run.update(deepcopy(updates))

    def append_agent_tool_call(self, run_id: str, tool_call: dict[str, Any]) -> None:
        with self._lock:
            run = self.agent_runs.get(str(run_id))
            if run is not None:
                run.setdefault("tool_calls", []).append(deepcopy(tool_call))

    def get_agent_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self.agent_runs.get(str(run_id))
            return deepcopy(run) if run else None

    def list_agent_runs_for_source(
        self, account_id: str, source_id: str
    ) -> list[dict[str, Any]]:
        with self._lock:
            return [
                deepcopy(run)
                for run in self.agent_runs.values()
                if run.get("account_id") == account_id and run.get("source_id") == source_id
            ]

    def update_source_agent_status(
        self,
        account_id: str,
        source_id: str,
        agent_run_id: str,
        agent_status: str,
    ) -> None:
        with self._lock:
            source = self.sources.get(str(source_id))
            if source is not None and source.get("account_id") == account_id:
                source["processing_mode"] = "agent"
                source["agent_run_id"] = agent_run_id
                source["agent_status"] = agent_status
