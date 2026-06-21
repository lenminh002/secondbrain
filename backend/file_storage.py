from __future__ import annotations

import os
from typing import Any

from github_storage import upload_pdf_to_github
from google_drive import upload_pdf_to_drive


def storage_provider() -> str:
    return (os.getenv("ORIGINAL_FILE_STORAGE") or "github").strip().lower() or "github"


def store_original_file(file_bytes: bytes, filename: str | None) -> dict[str, Any]:
    """Persist the original uploaded PDF and return neutral file metadata.

    Provider is chosen by ORIGINAL_FILE_STORAGE ("github" default, or "drive").
    Both backends return the same shape: provider, file_id, web_view_link,
    web_content_link, filename, mime_type, size_bytes.
    """
    if storage_provider() == "drive":
        return upload_pdf_to_drive(file_bytes, filename)
    return upload_pdf_to_github(file_bytes, filename)
