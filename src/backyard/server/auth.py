"""API token authentication."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from backyard.server.config import settings


class AuthContext:
    def __init__(
        self,
        engineer_id: str,
        engineer_name: str,
        org_id: str,
        role: str,
        session_id: str,
        project_id: str = "unset",
    ):
        self.engineer_id = engineer_id
        self.engineer_name = engineer_name
        self.org_id = org_id
        self.role = role
        self.session_id = session_id
        self.project_id = project_id


def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    # Also allow ?token= query param for SSE connections
    token = request.query_params.get("token", "")
    if token:
        return token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing Authorization header or token query parameter",
    )


async def authenticate(request: Request) -> AuthContext:
    """
    Validate the API key from the request.

    In Phase 1A, API keys are configured via the API_KEYS env var:
      API_KEYS=key-alice,key-bob,key-carol

    The key name (the part after "key-") becomes the engineer name.
    A real session ID is generated per connection.
    """
    token = _extract_token(request)

    if token not in settings.valid_api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Derive a stable engineer_id from the token (sha256 of the key)
    import hashlib, uuid
    engineer_id = str(uuid.UUID(hashlib.md5(token.encode()).hexdigest()))

    # Parse engineer name from key format "key-<name>"
    engineer_name = token.removeprefix("key-") if token.startswith("key-") else token

    return AuthContext(
        engineer_id=engineer_id,
        engineer_name=engineer_name,
        org_id="default-org",
        role="backend",   # overridden by project membership; placeholder for Phase 1A
        session_id=str(uuid.uuid4()),
    )
