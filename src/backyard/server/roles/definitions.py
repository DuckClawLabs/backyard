"""Role definitions — domain patterns and capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field

import pathspec


@dataclass
class RoleDefinition:
    name: str
    domains: list[str]           # glob patterns for files this role owns
    capabilities: set[str]       # allowed MCP tools
    ask_first: list[str]         # glob patterns requiring propose_cross_domain_edit


BUILT_IN_ROLES: dict[str, RoleDefinition] = {
    "frontend": RoleDefinition(
        name="frontend",
        domains=["ui/**", "components/**", "styles/**", "pages/**", "*.css", "*.tsx", "*.jsx"],
        capabilities={
            "read_file", "write_file", "list_files",
            "query_shared_context", "publish_context", "get_file_summary", "get_project_status",
            "signal_ready", "wait_for_signal",
            "propose_cross_domain_edit", "raise_resolution", "request_clarification",
        },
        ask_first=["api/**", "db/**", "services/**", "middleware/**", "infra/**", "*.yml", "Dockerfile"],
    ),
    "backend": RoleDefinition(
        name="backend",
        domains=["api/**", "services/**", "db/**", "middleware/**"],
        capabilities={
            "read_file", "write_file", "list_files",
            "query_shared_context", "publish_context", "get_file_summary", "get_project_status",
            "signal_ready", "wait_for_signal",
            "propose_cross_domain_edit", "raise_resolution", "request_clarification",
        },
        ask_first=["ui/**", "components/**", "styles/**", "pages/**", "infra/**", "*.yml", "Dockerfile"],
    ),
    "devops": RoleDefinition(
        name="devops",
        domains=["infra/**", "*.yml", "*.yaml", "Dockerfile", ".github/**", "scripts/**"],
        capabilities={
            "read_file", "write_file", "list_files",
            "query_shared_context", "publish_context", "get_file_summary", "get_project_status",
            "signal_ready", "wait_for_signal",
            "propose_cross_domain_edit", "raise_resolution", "request_clarification",
        },
        ask_first=["api/**", "ui/**", "services/**", "db/**", "components/**"],
    ),
    "reviewer": RoleDefinition(
        name="reviewer",
        domains=[],                 # reviewer reads everywhere; writes only via proposal
        capabilities={
            "read_file", "list_files",
            "query_shared_context", "get_file_summary", "get_project_status",
            "signal_ready", "wait_for_signal",
            "propose_cross_domain_edit", "raise_resolution", "request_clarification",
            "create_review_comment", "approve_change", "request_changes",
        },
        ask_first=["**"],           # reviewer always proposes before writing
    ),
}


def get_role(role_name: str) -> RoleDefinition:
    role = BUILT_IN_ROLES.get(role_name.lower())
    if role is None:
        raise ValueError(f"Unknown role: {role_name!r}. Valid roles: {list(BUILT_IN_ROLES)}")
    return role


def is_in_domain(role_name: str, path: str) -> bool:
    """Return True if path is within the role's default domain."""
    role = get_role(role_name)
    if not role.domains:
        return False
    spec = pathspec.PathSpec.from_lines("gitwildmatch", role.domains)
    return spec.match_file(path)


def needs_proposal(role_name: str, path: str) -> bool:
    """Return True if writing to path requires propose_cross_domain_edit."""
    role = get_role(role_name)
    spec = pathspec.PathSpec.from_lines("gitwildmatch", role.ask_first)
    return spec.match_file(path)


def has_capability(role_name: str, tool_name: str) -> bool:
    role = get_role(role_name)
    return tool_name in role.capabilities
