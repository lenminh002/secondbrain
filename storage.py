from __future__ import annotations

import json
import re
import threading
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DOCUMENTS_DIR = DATA_DIR / "documents"
SOURCES_FILE = DATA_DIR / "sources.json"
CHUNKS_FILE = DATA_DIR / "chunks.json"
POSTS_FILE = DATA_DIR / "posts.json"
GRAPH_FILE = DATA_DIR / "graph.json"
DEFAULT_ACCOUNT = {
    "id": "second-signal",
    "name": "Second Signal",
    "handle": "personal-kb",
    "initials": "SS",
}

_LOCK = threading.RLock()
_CACHE: dict[Path, tuple[tuple[int, int], Any]] = {}


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


def _default_for(path: Path) -> Any:
    if path == GRAPH_FILE:
        return {"nodes": [], "edges": []}
    return []


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or str(uuid.uuid4())


def _signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


def _load_json_unlocked(path: Path, default: Any | None = None, *, copy_result: bool = True) -> Any:
    ensure_data_dirs()
    fallback = _default_for(path) if default is None else default
    if not path.exists():
        path.write_text(json.dumps(fallback, indent=2) + "\n", encoding="utf-8")
        _CACHE.pop(path, None)
        return deepcopy(fallback) if copy_result else fallback

    signature = _signature(path)
    cached = _CACHE.get(path)
    if cached and cached[0] == signature:
        return deepcopy(cached[1]) if copy_result else cached[1]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(fallback) if copy_result else fallback

    _CACHE[path] = (signature, data)
    return deepcopy(data) if copy_result else data


def load_json(path: Path, default: Any | None = None, *, copy_result: bool = True) -> Any:
    with _LOCK:
        return _load_json_unlocked(path, default, copy_result=copy_result)


def _save_json_unlocked(path: Path, data: Any) -> None:
    ensure_data_dirs()
    tmp_file = path.with_suffix(path.suffix + ".tmp")
    tmp_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp_file.replace(path)
    _CACHE.pop(path, None)


def save_json(path: Path, data: Any) -> None:
    with _LOCK:
        _save_json_unlocked(path, data)


def load_sources() -> list[dict[str, Any]]:
    data = load_json(SOURCES_FILE, [])
    return data if isinstance(data, list) else []


def save_sources(sources: list[dict[str, Any]]) -> None:
    save_json(SOURCES_FILE, sources)


def load_chunks(*, copy_result: bool = True) -> list[dict[str, Any]]:
    data = load_json(CHUNKS_FILE, [], copy_result=copy_result)
    return data if isinstance(data, list) else []


def save_chunks(chunks: list[dict[str, Any]]) -> None:
    save_json(CHUNKS_FILE, chunks)


def get_default_account() -> dict[str, str]:
    return deepcopy(DEFAULT_ACCOUNT)


def _post_with_default_account(post: dict[str, Any]) -> dict[str, Any]:
    return {"account_id": DEFAULT_ACCOUNT["id"], **post}


def load_posts() -> list[dict[str, Any]]:
    data = load_json(POSTS_FILE, [])
    if not isinstance(data, list):
        return []
    return [
        _post_with_default_account(post)
        for post in data
        if isinstance(post, dict)
    ]


def save_posts(posts: list[dict[str, Any]]) -> None:
    save_json(POSTS_FILE, posts)


def load_graph() -> dict[str, list[dict[str, Any]]]:
    data = load_json(GRAPH_FILE, {"nodes": [], "edges": []})
    if not isinstance(data, dict):
        return {"nodes": [], "edges": []}
    nodes = data.get("nodes") if isinstance(data.get("nodes"), list) else []
    edges = data.get("edges") if isinstance(data.get("edges"), list) else []
    return {"nodes": nodes, "edges": edges}


def save_graph(graph: dict[str, list[dict[str, Any]]]) -> None:
    save_json(GRAPH_FILE, graph)


def append_source(source: dict[str, Any]) -> None:
    with _LOCK:
        sources = _load_json_unlocked(SOURCES_FILE, [])
        if not isinstance(sources, list):
            sources = []
        sources.append(source)
        _save_json_unlocked(SOURCES_FILE, sources)


def save_source_result(source: dict[str, Any]) -> None:
    with _LOCK:
        sources = _load_json_unlocked(SOURCES_FILE, [])
        if not isinstance(sources, list):
            sources = []
        sources = [item for item in sources if item.get("id") != source["id"]]
        sources.append(source)
        _save_json_unlocked(SOURCES_FILE, sources)


def _merge_graph(
    graph: dict[str, list[dict[str, Any]]],
    source: dict[str, Any],
    concepts: list[str],
) -> dict[str, list[dict[str, Any]]]:
    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    nodes_by_id = {node.get("id"): node for node in nodes if isinstance(node, dict)}
    edge_keys = {
        (edge.get("source"), edge.get("target"), edge.get("relation"))
        for edge in edges
        if isinstance(edge, dict)
    }

    source_node_id = f"source-{source['id']}"
    nodes_by_id[source_node_id] = {
        "id": source_node_id,
        "label": source["title"],
        "type": "source",
    }

    for concept in concepts:
        concept_id = f"concept-{_slugify(concept)}"
        nodes_by_id[concept_id] = {"id": concept_id, "label": concept, "type": "concept"}
        key = (source_node_id, concept_id, "mentions")
        if key not in edge_keys:
            edges.append({"source": source_node_id, "target": concept_id, "relation": "mentions"})
            edge_keys.add(key)

    return {"nodes": list(nodes_by_id.values()), "edges": edges}


def commit_source_artifacts(
    source: dict[str, Any],
    chunks: list[dict[str, Any]],
    post: dict[str, Any],
    concepts: list[str],
    markdown: str,
) -> None:
    with _LOCK:
        existing_chunks = _load_json_unlocked(CHUNKS_FILE, [])
        if not isinstance(existing_chunks, list):
            existing_chunks = []
        existing_chunks = [
            chunk for chunk in existing_chunks if chunk.get("source_id") != source["id"]
        ]
        _save_json_unlocked(CHUNKS_FILE, existing_chunks + chunks)

        posts = _load_json_unlocked(POSTS_FILE, [])
        if not isinstance(posts, list):
            posts = []
        posts = [item for item in posts if item.get("source_id") != source["id"]]
        posts.append(post)
        _save_json_unlocked(POSTS_FILE, posts)

        graph = _load_json_unlocked(GRAPH_FILE, {"nodes": [], "edges": []})
        if not isinstance(graph, dict):
            graph = {"nodes": [], "edges": []}
        _save_json_unlocked(GRAPH_FILE, _merge_graph(graph, source, concepts))

        document_path(source["id"]).write_text(markdown, encoding="utf-8")


def document_path(source_id: str) -> Path:
    ensure_data_dirs()
    return DOCUMENTS_DIR / f"{source_id}.md"


def save_document(source_id: str, markdown: str) -> None:
    document_path(source_id).write_text(markdown, encoding="utf-8")


def load_document(source_id: str) -> str:
    path = document_path(source_id)
    return path.read_text(encoding="utf-8") if path.exists() else ""
