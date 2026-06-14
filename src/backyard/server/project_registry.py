"""Project registry — maps git remote URLs to project IDs."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backyard.db.models import Project, ProjectMember
from backyard.server.redis_client import get_redis


def normalize_git_remote(remote_url: str) -> str:
    """
    Normalize a git remote URL to a canonical form for matching.
    Handles https://, git@, and ssh:// formats.

    Examples:
      https://github.com/acme/payments.git  -> github.com/acme/payments
      git@github.com:acme/payments.git      -> github.com/acme/payments
    """
    url = remote_url.strip()
    # Strip trailing .git
    if url.endswith(".git"):
        url = url[:-4]
    # git@host:org/repo -> host/org/repo
    ssh_match = re.match(r"git@([^:]+):(.+)", url)
    if ssh_match:
        return f"{ssh_match.group(1)}/{ssh_match.group(2)}"
    # https://host/org/repo -> host/org/repo
    https_match = re.match(r"https?://([^/]+)/(.+)", url)
    if https_match:
        return f"{https_match.group(1)}/{https_match.group(2)}"
    return url


async def resolve_project_from_remote(
    db: AsyncSession, git_remote: str
) -> Project | None:
    """Find the project matching a git remote URL."""
    normalized = normalize_git_remote(git_remote)
    result = await db.execute(
        select(Project).where(Project.git_remote == normalized)
    )
    return result.scalar_one_or_none()


async def get_engineer_role_for_project(
    project_id: str, engineer_id: str
) -> str:
    """
    Look up an engineer's role for a project.
    Checks Redis cache first, falls back to 'backend'.
    """
    redis = get_redis()
    role = await redis.hget(f"member_roles:{project_id}", engineer_id)
    return role or "backend"


async def set_active_project(session_id: str, project_id: str) -> None:
    """Explicitly set the active project for this session (fallback when git detection fails)."""
    redis = get_redis()
    await redis.set(f"active_project:{session_id}", project_id, ex=86400)


async def get_active_project(session_id: str) -> str | None:
    """Get the project this session last explicitly activated."""
    redis = get_redis()
    return await redis.get(f"active_project:{session_id}")
