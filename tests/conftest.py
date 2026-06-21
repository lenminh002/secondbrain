from __future__ import annotations

import dotenv
import pytest


@pytest.fixture(autouse=True)
def _isolate_env_from_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests deterministic and offline.

    The repo's local ``.env`` carries real API keys, and modules call
    ``load_dotenv()`` at import time. Tests routinely ``importlib.reload(...)``
    those modules, which can re-read ``.env`` and re-populate values the tests
    rely on being controlled. Neutralise ``load_dotenv`` and pin the agent-related
    settings to known values so tests exercise the deterministic fallbacks unless
    a test explicitly opts in. Setting them here also means that even if ``.env``
    does load, ``load_dotenv``'s default ``override=False`` leaves these intact.
    """
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CLAUDE_OAUTH_TOKEN", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AGENT_ENABLED", "false")
    monkeypatch.setenv("AGENT_PROCESSING_MODE", "agent")
    monkeypatch.setenv("AGENT_SAVE_TRACE", "true")
