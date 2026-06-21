from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    agent_enabled: bool = True
    agent_max_steps: int = 12
    agent_processing_mode: str = "agent"
    agent_save_trace: bool = True


def get_settings() -> Settings:
    """Read agent settings from the environment at call time.

    Reading lazily (rather than at import) keeps the values correct when tests
    monkeypatch the environment and reload modules.
    """
    return Settings(
        agent_enabled=_env_bool("AGENT_ENABLED", True),
        agent_max_steps=_env_int("AGENT_MAX_STEPS", 12),
        agent_processing_mode=(os.getenv("AGENT_PROCESSING_MODE", "agent").strip() or "agent"),
        agent_save_trace=_env_bool("AGENT_SAVE_TRACE", True),
    )
