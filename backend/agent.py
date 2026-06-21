from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import storage
from agent_tools import KnowledgeAgentTools
from config import Settings, get_settings
from knowledge_ai import (
    MODEL_NAME,
    _client,
    _message_content_to_params,
    _text_from_content,
)

SYSTEM_PROMPT = """
You are the Knowledge Librarian Agent for Second-Brain.

Your job is to process an uploaded PDF into:
1. searchable chunks,
2. vector embeddings,
3. memory posts,
4. knowledge graph nodes and edges,
5. a completed source status.

You have access to backend tools.
Call tools in the correct order.
Do not invent processing results.
Do not claim work is done unless the correct tool completed successfully.
If a tool fails, try a safe recovery if possible.
If processing cannot continue, call fail_source.

Use this preferred order:
1. inspect_source
2. extract_pdf_pages
3. clean_extracted_pages
4. chunk_clean_pages
5. embed_and_save_chunks
6. generate_and_save_memory_posts
7. build_and_save_graph
8. finalize_source

Keep tool inputs minimal.
Do not ask the user questions.
Do not output chain-of-thought.
At the end, return a short final JSON summary like:
{"status": "completed", "summary": "..."}
""".strip()

USER_PROMPT = """
Process this uploaded PDF source.

user_id: {user_id}
source_id: {source_id}
title: {title}

Use the available tools to complete the source processing.
""".strip()


def _minimal_schema(description: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "source_id": {"type": "string", "description": "The source_id being processed."}
        },
        "required": [],
        "additionalProperties": True,
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {"name": "inspect_source", "description": "Return stored metadata for the source.", "input_schema": _minimal_schema("inspect")},
    {"name": "extract_pdf_pages", "description": "Extract per-page text from the uploaded PDF (runtime state holds the bytes).", "input_schema": _minimal_schema("extract")},
    {"name": "clean_extracted_pages", "description": "Clean the extracted pages. Must run after extract_pdf_pages.", "input_schema": _minimal_schema("clean")},
    {
        "name": "chunk_clean_pages",
        "description": "Chunk cleaned pages for retrieval. Must run after clean_extracted_pages.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_tokens": {"type": "integer", "description": "Target chunk size in tokens (default 400)."},
                "overlap_tokens": {"type": "integer", "description": "Overlap between chunks in tokens (default 60)."},
            },
            "required": [],
            "additionalProperties": True,
        },
    },
    {"name": "embed_and_save_chunks", "description": "Create OpenAI embeddings and save chunks. Must run after chunk_clean_pages.", "input_schema": _minimal_schema("embed")},
    {"name": "generate_and_save_memory_posts", "description": "Generate memory posts from chunks and save them. Must run after chunk_clean_pages.", "input_schema": _minimal_schema("posts")},
    {"name": "build_and_save_graph", "description": "Extract concepts and save graph nodes/edges. Must run after chunk_clean_pages.", "input_schema": _minimal_schema("graph")},
    {
        "name": "finalize_source",
        "description": "Mark the source ready with final counts. Must run after chunks are saved.",
        "input_schema": {
            "type": "object",
            "properties": {
                "total_pages": {"type": "integer"},
                "total_chunks": {"type": "integer"},
                "total_posts": {"type": "integer"},
                "total_graph_nodes": {"type": "integer"},
                "total_graph_edges": {"type": "integer"},
            },
            "required": [],
            "additionalProperties": True,
        },
    },
    {
        "name": "fail_source",
        "description": "Mark the source failed when processing cannot continue.",
        "input_schema": {
            "type": "object",
            "properties": {"error_message": {"type": "string"}},
            "required": [],
            "additionalProperties": True,
        },
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_input(value: Any) -> dict[str, Any]:
    """Keep only small scalar inputs for the trace — never large arrays/text."""
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, (int, float, bool)):
            safe[key] = item
        elif isinstance(item, str):
            safe[key] = item[:200]
    return safe


class KnowledgeLibrarianAgent:
    """Claude-controlled PDF processing. Claude chooses tools; Python executes them."""

    def __init__(self, anthropic_client: Any = None, settings: Settings | None = None) -> None:
        self._client = anthropic_client
        self._settings = settings or get_settings()

    def _ensure_client(self) -> Any:
        client = self._client if self._client is not None else _client()
        if client is None:
            raise ValueError("ANTHROPIC_API_KEY is required for agentic processing.")
        return client

    def process_pdf_with_agent(
        self,
        account_id: str,
        source_id: str,
        file_bytes: bytes,
        title: str,
    ) -> dict[str, Any]:
        settings = self._settings
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        storage.create_agent_run(
            {
                "run_id": run_id,
                "user_id": account_id,
                "account_id": account_id,
                "source_id": source_id,
                "status": "running",
                "current_step": None,
                "tool_calls": [],
                "summary": None,
                "error_message": "",
                "created_at": now,
                "updated_at": now,
            }
        )
        storage.update_source_agent_status(account_id, source_id, run_id, "running")

        runtime_state: dict[str, Any] = {
            "file_bytes": file_bytes,
            "pages": [],
            "cleaned_pages": [],
            "chunks": [],
            "saved_chunk_ids": [],
            "stats": {},
        }
        tools = KnowledgeAgentTools(account_id, source_id, title, runtime_state)
        dispatch = {
            "inspect_source": tools.inspect_source,
            "extract_pdf_pages": tools.extract_pdf_pages,
            "clean_extracted_pages": tools.clean_extracted_pages,
            "chunk_clean_pages": tools.chunk_clean_pages,
            "embed_and_save_chunks": tools.embed_and_save_chunks,
            "generate_and_save_memory_posts": tools.generate_and_save_memory_posts,
            "build_and_save_graph": tools.build_and_save_graph,
            "finalize_source": tools.finalize_source,
            "fail_source": tools.fail_source,
        }

        try:
            client = self._ensure_client()
            messages: list[dict[str, Any]] = [
                {
                    "role": "user",
                    "content": USER_PROMPT.format(
                        user_id=account_id, source_id=source_id, title=title
                    ),
                }
            ]
            final_text = ""
            for _ in range(max(1, settings.agent_max_steps)):
                response = client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=1024,
                    temperature=0.1,
                    system=SYSTEM_PROMPT,
                    tools=TOOL_SCHEMAS,
                    messages=messages,
                )
                messages.append(
                    {"role": "assistant", "content": _message_content_to_params(response.content)}
                )
                tool_uses = [
                    block for block in response.content if getattr(block, "type", None) == "tool_use"
                ]
                if not tool_uses:
                    final_text = _text_from_content(response.content)
                    break

                tool_results: list[dict[str, Any]] = []
                for tool_use in tool_uses:
                    name = str(getattr(tool_use, "name", ""))
                    tool_input = dict(getattr(tool_use, "input", {}) or {})
                    storage.update_agent_run(
                        run_id, {"current_step": name, "updated_at": _now_iso()}
                    )
                    handler = dispatch.get(name)
                    if handler is None:
                        output: dict[str, Any] = {"error": f"Unknown tool: {name}"}
                    else:
                        try:
                            output = handler(**tool_input)
                        except Exception as exc:  # tool crashed — report, let Claude recover
                            output = {"error": str(exc)}
                    is_error = bool(isinstance(output, dict) and output.get("error"))
                    if settings.agent_save_trace:
                        storage.append_agent_tool_call(
                            run_id,
                            {
                                "tool_name": name,
                                "status": "error" if is_error else "success",
                                "input_summary": _safe_input(tool_input),
                                "output_summary": output,
                                "created_at": _now_iso(),
                            },
                        )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps(output),
                            "is_error": is_error,
                        }
                    )
                messages.append({"role": "user", "content": tool_results})
            else:
                # Loop exhausted without a final text response.
                return self._fail(
                    tools,
                    run_id,
                    account_id,
                    source_id,
                    "Agent exceeded AGENT_MAX_STEPS before completing.",
                )

            # Safety net: ensure the source is actually finalized.
            if not runtime_state.get("finalized") and not runtime_state.get("failed"):
                if runtime_state.get("saved_chunk_ids"):
                    tools.finalize_source()
                else:
                    return self._fail(
                        tools,
                        run_id,
                        account_id,
                        source_id,
                        "Agent stopped before saving chunks.",
                    )

            summary = self._summary_from(final_text, runtime_state)
            storage.update_agent_run(
                run_id,
                {
                    "status": "completed",
                    "current_step": "done",
                    "summary": summary,
                    "updated_at": _now_iso(),
                },
            )
            storage.update_source_agent_status(account_id, source_id, run_id, "completed")
            return {"run_id": run_id, "source_id": source_id, "status": "completed", "summary": summary}
        except Exception as exc:
            return self._fail(tools, run_id, account_id, source_id, str(exc))

    def _fail(
        self,
        tools: KnowledgeAgentTools,
        run_id: str,
        account_id: str,
        source_id: str,
        message: str,
    ) -> dict[str, Any]:
        try:
            tools.fail_source(error_message=message)
        except Exception:
            pass
        summary = f"Processing failed: {message}"
        storage.update_agent_run(
            run_id,
            {
                "status": "failed",
                "error_message": message,
                "summary": summary,
                "updated_at": _now_iso(),
            },
        )
        storage.update_source_agent_status(account_id, source_id, run_id, "failed")
        return {"run_id": run_id, "source_id": source_id, "status": "failed", "summary": summary}

    @staticmethod
    def _summary_from(final_text: str, runtime_state: dict[str, Any]) -> str:
        stripped = (final_text or "").strip()
        if stripped:
            try:
                from knowledge_ai import _strip_code_fence

                parsed = json.loads(_strip_code_fence(stripped))
                if isinstance(parsed, dict) and parsed.get("summary"):
                    return str(parsed["summary"])
            except Exception:
                pass
        stats = runtime_state.get("stats", {})
        return (
            f"Processed {stats.get('total_pages', 0)} pages into "
            f"{stats.get('total_chunks', 0)} chunks, created "
            f"{stats.get('total_posts', 0)} posts, and built a graph with "
            f"{stats.get('graph_nodes', 0)} nodes and {stats.get('graph_edges', 0)} edges."
        )


# --- Future agent skeletons (not implemented for the hackathon) -----------


class RecallCoachAgent:
    """
    Future agent:
    - reads user review history
    - finds weak topics
    - chooses due posts
    - generates follow-up quizzes
    - updates memory score
    """

    pass


class ConnectionAgent:
    """
    Future agent:
    - finds similar concepts across sources
    - merges duplicate graph nodes
    - recommends related chunks
    - creates cross-source graph edges
    """

    pass
