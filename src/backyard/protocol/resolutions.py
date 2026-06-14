"""Conflict resolution card types."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ResolutionCard(BaseModel):
    id: str
    project_id: str
    title: str
    conflict_a: str
    conflict_b: str
    affects: list[str] = Field(default_factory=list)
    agent_read: str = ""
    raised_by: str                     # engineer_id
    raised_by_role: str
    status: Literal["open", "resolved", "dismissed"] = "open"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ResolutionDecision(BaseModel):
    resolution_id: str
    decision: str
    decided_by: list[str]              # engineer_ids
    record_as_adr: bool = False
    resolved_at: datetime = Field(default_factory=datetime.utcnow)
