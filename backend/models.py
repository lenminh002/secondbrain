from __future__ import annotations

from pydantic import BaseModel, Field


class AgentToolCallLog(BaseModel):
    """A single safe tool-call record. Never contains chain-of-thought."""

    tool_name: str
    input_summary: dict = Field(default_factory=dict)
    output_summary: dict = Field(default_factory=dict)
    status: str
    created_at: str | None = None


class AgentRunStatus(BaseModel):
    run_id: str
    user_id: str
    source_id: str
    status: str
    current_step: str | None = None
    tool_calls: list[dict] = Field(default_factory=list)
    summary: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class AgentRunResponse(BaseModel):
    run_id: str
    source_id: str
    status: str
    summary: str | None = None
