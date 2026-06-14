"""Project briefing model — assembled and injected into every agent turn."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ActiveSession(BaseModel):
    engineer_id: str
    engineer_name: str
    role: str
    connected_since: datetime


class BriefingContract(BaseModel):
    contract_id: str
    description: str
    published_by_role: str
    published_at: datetime


class OpenDecision(BaseModel):
    resolution_id: str
    title: str
    created_at: datetime


class ProjectBriefing(BaseModel):
    project_id: str
    project_name: str
    my_role: str
    active_sessions: list[ActiveSession] = Field(default_factory=list)
    recent_activity: list[str] = Field(default_factory=list)
    contracts: list[BriefingContract] = Field(default_factory=list)
    open_decisions: list[OpenDecision] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    def render(self) -> str:
        active = ", ".join(f"{s.role} ({s.engineer_name})" for s in self.active_sessions)
        lines = [
            "=== PROJECT BRIEFING ===",
            f"Project: {self.project_name}  |  Your role: {self.my_role}",
            f"Active: {active or 'only you'}",
            "",
        ]

        if self.recent_activity:
            lines.append("Recent activity:")
            for bullet in self.recent_activity:
                lines.append(f"  · {bullet}")
            lines.append("")

        if self.contracts:
            lines.append("Contracts published:")
            for c in self.contracts:
                lines.append(f"  · {c.contract_id} — {c.description} (by {c.published_by_role})")
            lines.append("")

        if self.open_decisions:
            lines.append("Open decisions requiring engineer input:")
            for d in self.open_decisions:
                lines.append(f"  ⚠ {d.title} [{d.resolution_id}]")
            lines.append("")
        else:
            lines.append("Open decisions: none")

        lines.append("=== END BRIEFING ===")
        return "\n".join(lines)
