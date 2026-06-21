from __future__ import annotations

import base64
import os
import re
import uuid
from typing import Any

import httpx

from dotenv import load_dotenv

load_dotenv()

GITHUB_API = "https://api.github.com"
PDF_MIME_TYPE = "application/pdf"


class GitHubStorageError(RuntimeError):
    pass


def _token() -> str:
    token = (os.getenv("GITHUB_TOKEN") or "").strip()
    if not token:
        raise GitHubStorageError("GitHub upload failed: GITHUB_TOKEN is required.")
    return token


def _repo() -> str:
    repo = (os.getenv("GITHUB_STORAGE_REPO") or "").strip()
    if not repo or "/" not in repo:
        raise GitHubStorageError(
            "GitHub upload failed: GITHUB_STORAGE_REPO must be set as 'owner/repo'."
        )
    return repo


def _branch() -> str:
    return (os.getenv("GITHUB_STORAGE_BRANCH") or "main").strip() or "main"


def _prefix() -> str:
    return (os.getenv("GITHUB_STORAGE_PATH_PREFIX") or "uploads").strip().strip("/") or "uploads"


def _safe_pdf_name(filename: str | None) -> str:
    name = (filename or "source.pdf").strip() or "source.pdf"
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "source.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name


def _put_contents(repo: str, path: str, payload: dict[str, Any], token: str) -> dict[str, Any]:
    """PUT a file to the GitHub Contents API. Isolated so tests can stub the network."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(timeout=30) as client:
        response = client.put(f"{GITHUB_API}/repos/{repo}/contents/{path}", headers=headers, json=payload)
    if response.status_code not in (200, 201):
        raise GitHubStorageError(
            f"GitHub upload failed: {response.status_code} {response.text[:300]}"
        )
    return response.json()


def upload_pdf_to_github(file_bytes: bytes, filename: str | None) -> dict[str, Any]:
    """Store the original PDF in a GitHub repo and return neutral file metadata.

    Files go to ``{prefix}/{uuid}/{filename}`` so paths never collide (which would
    otherwise require an existing-file sha). Returns the same neutral shape as the
    Drive uploader so the rest of the pipeline is provider-agnostic.
    """
    if not file_bytes:
        raise GitHubStorageError("GitHub upload failed: PDF bytes are empty.")

    repo, branch = _repo(), _branch()
    display_name = _safe_pdf_name(filename)
    path = f"{_prefix()}/{uuid.uuid4().hex}/{display_name}"
    result = _put_contents(
        repo,
        path,
        {
            "message": f"Add source PDF {display_name}",
            "content": base64.b64encode(file_bytes).decode("ascii"),
            "branch": branch,
        },
        _token(),
    )
    content = result.get("content") if isinstance(result.get("content"), dict) else {}
    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    return {
        "provider": "github",
        "file_id": content.get("sha") or path,
        "web_view_link": content.get("html_url") or f"https://github.com/{repo}/blob/{branch}/{path}",
        "web_content_link": raw_url,
        "filename": display_name,
        "mime_type": PDF_MIME_TYPE,
        "size_bytes": len(file_bytes),
        "github_repo": repo,
        "github_path": path,
    }
