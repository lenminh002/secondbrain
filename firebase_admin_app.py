from __future__ import annotations

import os
import threading
from typing import Any

_LOCK = threading.RLock()


def get_firebase_admin_app(*, require_credentials: bool = False) -> Any:
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError as exc:
        raise RuntimeError("firebase-admin is required. Run `uv sync` first.") from exc

    with _LOCK:
        try:
            return firebase_admin.get_app()
        except ValueError:
            credentials_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE") or os.getenv(
                "GOOGLE_APPLICATION_CREDENTIALS"
            )
            if credentials_path:
                return firebase_admin.initialize_app(credentials.Certificate(credentials_path))
            if require_credentials:
                raise RuntimeError(
                    "Firebase credentials are required. Set FIREBASE_SERVICE_ACCOUNT_FILE "
                    "or GOOGLE_APPLICATION_CREDENTIALS to a Firebase service account JSON file."
                )
            return firebase_admin.initialize_app()
