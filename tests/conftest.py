from __future__ import annotations

import dotenv
import pytest


@pytest.fixture(autouse=True)
def _isolate_env_from_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests deterministic and offline.

    The repo's local ``.env`` carries real API keys. Modules call ``load_dotenv()``
    at import time, and tests routinely ``importlib.reload(...)`` those modules —
    which would re-read ``.env`` and re-populate keys the tests deliberately
    cleared, sending real Anthropic/OpenAI traffic. Neutralise ``load_dotenv`` and
    default the agent off so tests exercise the deterministic fallbacks unless a
    test explicitly opts in.
    """
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("AGENT_ENABLED", "false")
