"""Authentication — optional API key enforcement.

If API_KEYS is set in the environment, every request must present a matching
Bearer token. If API_KEYS is not set, auth is skipped — identity comes from
the engineer's .backyard-mcp/me.yaml file read by the MCP endpoint.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status

from backyard.server.config import settings


class AuthContext:
    def __init__(
        self,
        session_id: str,
        engineer_id: str = "",
        engineer_name: str = "",
        org_id: str = "default",
        role: str = "",
        project_id: str = "",
        git_branch: str = "",
    ):
        self.engineer_id = engineer_id
        self.engineer_name = engineer_name
        self.org_id = org_id
        self.role = role
        self.session_id = session_id
        self.project_id = project_id
        self.git_branch = git_branch


async def authenticate(request: Request) -> AuthContext:
    """Return an AuthContext for this request.

    When API_KEYS is not configured: always succeeds. Identity (name, email,
    role, project) is filled in later from me.yaml by the MCP endpoint.

    When API_KEYS is configured: the Bearer token must match a known key.
    """
    session_id = str(uuid.uuid4())

    if not settings.auth_enabled:
        return AuthContext(session_id=session_id)

    # Auth is enabled — extract and validate the token
    auth_header = request.headers.get("Authorization", "")
    token = request.query_params.get("token", "")

    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Set API_KEYS on the server or remove auth.",
        )

    if token not in settings.valid_api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return AuthContext(session_id=session_id)
