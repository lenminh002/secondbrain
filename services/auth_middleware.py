from __future__ import annotations

import json
import os
from typing import Any
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from firebase_admin import auth

from firebase_admin_app import get_firebase_admin_app
from storage import get_account, upsert_account
from services.account_service import _CURRENT_ACCOUNT_VAR

_FIREBASE_APP: Any = None


def _get_app() -> Any:
    global _FIREBASE_APP
    if _FIREBASE_APP is None:
        _FIREBASE_APP = get_firebase_admin_app()
    return _FIREBASE_APP


class FirebaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Allow preflight and docs/openapi paths to bypass authentication
        if request.method == "OPTIONS" or request.url.path in (
            "/docs",
            "/redoc",
            "/openapi.json",
        ):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                # Ensure Firebase Admin App is initialized
                app = _get_app()
                
                # Verify the ID token
                decoded_token = auth.verify_id_token(token, app=app)
                uid = decoded_token["uid"]
                email = decoded_token.get("email") or ""
                name = decoded_token.get("name") or email.split("@")[0] or "User"
                avatar_url = decoded_token.get("picture") or ""
                initials = "".join([p[0] for p in name.split() if p])[:2].upper()
                if not initials:
                    initials = "US"

                account = get_account(uid)
                if not account:
                    account = {
                        "id": uid,
                        "name": name,
                        "handle": email.split("@")[0] if email else uid,
                        "initials": initials,
                        "email": email,
                        "avatar_url": avatar_url,
                    }
                    upsert_account(account)

                # Set request-scoped user
                token_ref = _CURRENT_ACCOUNT_VAR.set(account)
                try:
                    return await call_next(request)
                finally:
                    _CURRENT_ACCOUNT_VAR.reset(token_ref)

            except Exception as exc:
                return Response(
                    content=json.dumps({"detail": f"Invalid token: {exc}"}),
                    status_code=401,
                    media_type="application/json",
                )

        # If no token is provided:
        # If firestore backend is enabled, authentication is mandatory.
        if os.getenv("SECONDBRAIN_STORAGE_BACKEND") == "firestore":
            return Response(
                content=json.dumps({"detail": "Authorization header missing"}),
                status_code=401,
                media_type="application/json",
            )

        # Otherwise (e.g. testing or mock/memory mode), fallback to mock user
        return await call_next(request)
