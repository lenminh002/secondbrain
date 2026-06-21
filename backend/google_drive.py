from __future__ import annotations

import io
import json
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
PDF_MIME_TYPE = "application/pdf"


class GoogleDriveUploadError(RuntimeError):
    pass


def _service_account_info() -> dict[str, Any] | None:
    raw_json = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
    if raw_json:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise GoogleDriveUploadError(
                "Google Drive upload failed: GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is not valid JSON."
            ) from exc
        if not isinstance(data, dict):
            raise GoogleDriveUploadError(
                "Google Drive upload failed: GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON must be a JSON object."
            )
        return data
    return None


def _service_account_file() -> str | None:
    path = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE")
    return path.strip() if path else None


def _drive_folder_id() -> str:
    folder_id = (os.getenv("GOOGLE_DRIVE_FOLDER_ID") or "").strip()
    if not folder_id:
        raise GoogleDriveUploadError(
            "Google Drive upload failed: GOOGLE_DRIVE_FOLDER_ID is required."
        )
    return folder_id


def _build_drive_service() -> Any:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise GoogleDriveUploadError(
            "Google Drive upload failed: install google-api-python-client and google-auth."
        ) from exc

    info = _service_account_info()
    credentials_file = _service_account_file()
    if info:
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=DRIVE_SCOPES,
        )
    elif credentials_file:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=DRIVE_SCOPES,
        )
    else:
        raise GoogleDriveUploadError(
            "Google Drive upload failed: set GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE "
            "or GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON."
        )

    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def upload_pdf_to_drive(file_bytes: bytes, filename: str | None) -> dict[str, Any]:
    if not file_bytes:
        raise GoogleDriveUploadError("Google Drive upload failed: PDF bytes are empty.")

    display_name = (filename or "source.pdf").strip() or "source.pdf"
    if not display_name.lower().endswith(".pdf"):
        display_name = f"{display_name}.pdf"

    try:
        from googleapiclient.http import MediaIoBaseUpload

        service = _build_drive_service()
        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes),
            mimetype=PDF_MIME_TYPE,
            resumable=True,
        )
        created_file = (
            service.files()
            .create(
                body={
                    "name": display_name,
                    "mimeType": PDF_MIME_TYPE,
                    "parents": [_drive_folder_id()],
                },
                media_body=media,
                fields="id,name,mimeType,webViewLink,webContentLink",
                supportsAllDrives=True,
            )
            .execute()
        )
    except GoogleDriveUploadError:
        raise
    except Exception as exc:
        raise GoogleDriveUploadError(f"Google Drive upload failed: {exc}") from exc

    return {
        "provider": "google_drive",
        "file_id": created_file.get("id"),
        "web_view_link": created_file.get("webViewLink"),
        "web_content_link": created_file.get("webContentLink"),
        "filename": created_file.get("name") or display_name,
        "mime_type": created_file.get("mimeType") or PDF_MIME_TYPE,
        "size_bytes": len(file_bytes),
    }


def upload_markdown_to_drive(file_bytes: bytes, filename: str | None) -> dict[str, Any]:
    if not file_bytes:
        raise GoogleDriveUploadError("Google Drive upload failed: Markdown bytes are empty.")

    display_name = (filename or "source.md").strip() or "source.md"
    if not display_name.lower().endswith(".md"):
        display_name = f"{display_name}.md"

    try:
        from googleapiclient.http import MediaIoBaseUpload

        service = _build_drive_service()
        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes),
            mimetype="text/markdown",
            resumable=True,
        )
        created_file = (
            service.files()
            .create(
                body={
                    "name": display_name,
                    "mimeType": "text/markdown",
                    "parents": [_drive_folder_id()],
                },
                media_body=media,
                fields="id,name,mimeType,webViewLink,webContentLink",
                supportsAllDrives=True,
            )
            .execute()
        )
    except GoogleDriveUploadError:
        raise
    except Exception as exc:
        raise GoogleDriveUploadError(f"Google Drive upload failed: {exc}") from exc

    return {
        "provider": "google_drive",
        "file_id": created_file.get("id"),
        "web_view_link": created_file.get("webViewLink"),
        "web_content_link": created_file.get("webContentLink"),
        "filename": created_file.get("name") or display_name,
        "mime_type": created_file.get("mimeType") or "text/markdown",
        "size_bytes": len(file_bytes),
    }

