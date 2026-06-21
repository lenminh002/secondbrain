from __future__ import annotations

import hashlib
import math
import os
from typing import Any

import httpx

OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
LOCAL_EMBEDDING_MODEL = "local-hash-64"


def current_embedding_model() -> str:
    return OPENAI_EMBEDDING_MODEL if os.getenv("OPENAI_API_KEY") else LOCAL_EMBEDDING_MODEL


def _embedding_batch_size() -> int:
    try:
        value = int(os.getenv("OPENAI_EMBEDDING_BATCH_SIZE", "96"))
    except ValueError:
        return 96
    return max(1, min(value, 2048))


def _local_embedding(text: str, dimensions: int = 64) -> list[float]:
    vector = [0.0] * dimensions
    words = text.lower().split()
    if not words:
        words = [text.lower()]
    for word in words:
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return [_local_embedding(text) for text in texts]

    embeddings: list[list[float]] = []
    headers = {"Authorization": f"Bearer {api_key}"}
    batch_size = _embedding_batch_size()
    with httpx.Client(timeout=30) as client:
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = client.post(
                OPENAI_EMBEDDINGS_URL,
                headers=headers,
                json={"model": OPENAI_EMBEDDING_MODEL, "input": batch},
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            data = payload.get("data", [])
            if not isinstance(data, list) or len(data) != len(batch):
                raise ValueError("OpenAI embeddings response did not match the requested inputs.")
            for item in data:
                if not isinstance(item, dict) or "index" not in item or "embedding" not in item:
                    raise ValueError(
                        f"Malformed item in OpenAI embeddings response: {item!r}"
                    )
            embeddings.extend(
                item["embedding"] for item in sorted(data, key=lambda item: item["index"])
            )
    return embeddings


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    limit = min(len(left), len(right))
    dot = sum(left[index] * right[index] for index in range(limit))
    left_norm = math.sqrt(sum(value * value for value in left[:limit]))
    right_norm = math.sqrt(sum(value * value for value in right[:limit]))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)
