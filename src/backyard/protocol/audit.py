"""Audit log entry type."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    project_id: str
    engineer_id: str
    role: str
    session_id: str
    turn_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""
    latency_ms: int = 0
