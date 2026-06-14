"""
Profile reader — loads .backyard-mcp/me.yaml from the engineer's workspace.

The file is personal (gitignored) and contains both project identity
(shared project.id across all teammates) and the engineer's own details.

Example .backyard-mcp/me.yaml:

  project:
    name: Acme Payments Service
    id: payments-service

    team:
      - name: Alice Chen
        email: alice@company.com
        role: frontend
        owns: ["ui/**", "components/**"]   # optional
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class EngineerProfile:
    name: str
    email: str
    role: str
    owns: list[str] = field(default_factory=list)


@dataclass
class ProjectProfile:
    id: str
    name: str
    engineer: EngineerProfile


class ProfileNotFoundError(Exception):
    pass


class ProfileInvalidError(Exception):
    pass


def load_profile(workspace_root: str | Path) -> ProjectProfile:
    """
    Load .backyard-mcp/me.yaml from the engineer's workspace root.
    Raises ProfileNotFoundError if the file doesn't exist.
    Raises ProfileInvalidError if required fields are missing.
    """
    path = Path(workspace_root) / ".backyard-mcp" / "me.yaml"

    if not path.exists():
        raise ProfileNotFoundError(
            f"No .backyard-mcp/me.yaml found in {workspace_root}.\n"
            "Create one to connect to Backyard. See .backyard-mcp/me.yaml.example for the format."
        )

    try:
        with path.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ProfileInvalidError(f"Invalid YAML in me.yaml: {e}") from e

    if not isinstance(data, dict):
        raise ProfileInvalidError("me.yaml must be a YAML mapping.")

    project = data.get("project", {})
    if not isinstance(project, dict):
        raise ProfileInvalidError("me.yaml: 'project' must be a mapping.")

    project_id = project.get("id", "").strip()
    project_name = project.get("name", "").strip()

    if not project_id:
        raise ProfileInvalidError("me.yaml: 'project.id' is required.")
    if not project_name:
        raise ProfileInvalidError("me.yaml: 'project.name' is required.")

    team = project.get("team", [])
    if not isinstance(team, list) or len(team) == 0:
        raise ProfileInvalidError("me.yaml: 'project.team' must be a list with at least one entry.")

    entry = team[0]
    if not isinstance(entry, dict):
        raise ProfileInvalidError("me.yaml: each team entry must be a mapping.")

    name = entry.get("name", "").strip()
    email = entry.get("email", "").strip()
    role = entry.get("role", "").strip().lower()

    if not name:
        raise ProfileInvalidError("me.yaml: team entry 'name' is required.")
    if not email:
        raise ProfileInvalidError("me.yaml: team entry 'email' is required.")
    if not role:
        raise ProfileInvalidError("me.yaml: team entry 'role' is required.")

    valid_roles = {"frontend", "backend", "devops", "reviewer"}
    if role not in valid_roles:
        raise ProfileInvalidError(
            f"me.yaml: role '{role}' is not valid. Choose from: {', '.join(sorted(valid_roles))}"
        )

    owns = entry.get("owns", [])
    if isinstance(owns, str):
        owns = [owns]

    return ProjectProfile(
        id=project_id,
        name=project_name,
        engineer=EngineerProfile(
            name=name,
            email=email,
            role=role,
            owns=list(owns),
        ),
    )
