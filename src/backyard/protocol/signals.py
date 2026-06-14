"""Signal protocol types — signal_ready / wait_for_signal."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Signal(BaseModel):
    id: str
    project_id: str
    topic: str
    published_by: str        # engineer_id
    published_by_role: str
    git_branch: str = ""     # branch that published; "_project_" for project-scoped
    payload: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WaitResult(BaseModel):
    timed_out: bool = False
    signal: Signal | None = None
