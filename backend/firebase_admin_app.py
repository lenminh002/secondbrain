from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.RLock()
_ENV_LOADED = False


def _load_local_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _firebase_options() -> dict[str, str]:
    options: dict[str, str] = {}
    project_id = (
        os.getenv("FIREBASE_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
    )
    if project_id:
        options["projectId"] = project_id
    database_url = os.getenv("FIREBASE_DATABASE_URL")
    if database_url:
        options["databaseURL"] = database_url
    storage_bucket = os.getenv("FIREBASE_STORAGE_BUCKET")
    if storage_bucket:
        options["storageBucket"] = storage_bucket
    return options


def _service_account_credential(credentials: Any) -> Any | None:
    credentials_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if credentials_json:
        try:
            service_account = json.loads(credentials_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON must be valid JSON.") from exc
        if not isinstance(service_account, dict):
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON must decode to a JSON object.")
        return credentials.Certificate(service_account)

    credentials_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE") or os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )
    if not credentials_path:
        return None

    resolved_path = Path(credentials_path).expanduser()
    if not resolved_path.exists():
        raise RuntimeError(
            "Firebase service account file was not found at "
            f"{credentials_path}."
        )
    return credentials.Certificate(str(resolved_path))


def get_firebase_admin_app(*, require_credentials: bool = False) -> Any:
    _load_local_env()
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError as exc:
        raise RuntimeError("firebase-admin is required. Run `uv sync` first.") from exc

    with _LOCK:
        try:
            return firebase_admin.get_app()
        except ValueError:
            options = _firebase_options()
            emulator_host = os.getenv("FIRESTORE_EMULATOR_HOST")
            if emulator_host:
                if not options.get("projectId"):
                    raise RuntimeError(
                        "FIREBASE_PROJECT_ID is required when using FIRESTORE_EMULATOR_HOST."
                    )
                return firebase_admin.initialize_app(options=options or None)

            credential = _service_account_credential(credentials)
            if credential is not None:
                return firebase_admin.initialize_app(credential, options or None)
            if require_credentials and not emulator_host:
                raise RuntimeError(
                    "Firebase credentials are required. Set FIREBASE_SERVICE_ACCOUNT_FILE, "
                    "GOOGLE_APPLICATION_CREDENTIALS, FIREBASE_SERVICE_ACCOUNT_JSON, or "
                    "FIRESTORE_EMULATOR_HOST with FIREBASE_PROJECT_ID."
                )
            return firebase_admin.initialize_app(options=options or None)
