"""Shared context artifact types — what agents publish and consume."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Endpoint(BaseModel):
    method: str
    path: str
    response: str
    description: str = ""


class Contract(BaseModel):
    id: str
    project_id: str
    published_by_role: str
    published_by_engineer: str
    version: int = 1
    endpoints: list[Endpoint] = Field(default_factory=list)
    types: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ADR(BaseModel):
    id: str
    project_id: str
    adr_ref: str           # e.g. "ADR-001"
    title: str
    status: str = "accepted"
    affects: list[str] = Field(default_factory=list)
    decision: str
    rationale: str = ""
    decided_by: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FileSummary(BaseModel):
    id: str
    project_id: str
    path: str
    summary: str
    exports: list[str] = Field(default_factory=list)
    last_modified_by: str
    last_modified_at: datetime = Field(default_factory=datetime.utcnow)


class ActivityEntry(BaseModel):
    project_id: str
    period_start: datetime
    period_end: datetime
    bullets: list[str]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
