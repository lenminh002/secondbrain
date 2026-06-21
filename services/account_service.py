from __future__ import annotations

from typing import Any

from storage import get_account as storage_get_account
from storage import load_sources, upsert_account
from storage import save_source_result


MOCK_ACCOUNT: dict[str, str] = {
    "id": "mock-user",
    "name": "SecondBrain",
    "handle": "mock-vault",
    "initials": "SB",
    "email": "mock@example.com",
    "avatar_url": "",
}


def current_account() -> dict[str, str]:
    # Read first; only write when the account doesn't exist yet.  Calling
    # upsert_account on every request caused an unnecessary write (get + set)
    # on every single endpoint hit when using the Firestore backend.
    return storage_get_account(MOCK_ACCOUNT["id"]) or upsert_account(MOCK_ACCOUNT)


def cleanup_stuck_processing_sources() -> None:
    try:
        account = storage_get_account("mock-user") or upsert_account(MOCK_ACCOUNT)
        account_id = account["id"]
        sources = load_sources(account_id)
        for source in sources:
            if source.get("status") == "processing":
                source["status"] = "failed"
                source["error"] = "Server was restarted while processing this source."
                source["progress_stage"] = "complete"
                source["progress_percent"] = 100
                save_source_result(account_id, source)
    except Exception as exc:
        print(f"Failed to cleanup stuck processing sources on startup: {exc}")
