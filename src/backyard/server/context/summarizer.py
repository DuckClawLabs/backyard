"""Generate file summaries via the Anthropic API."""

from __future__ import annotations

import anthropic

from backyard.server.config import settings

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def summarize_file(path: str, content: str) -> tuple[str, list[str]]:
    """Return (summary, exports) for the given file content."""
    if not settings.anthropic_api_key:
        return f"File at {path}.", []

    client = _get_client()
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": (
                f"File: {path}\n\n"
                f"```\n{content[:4000]}\n```\n\n"
                "Respond with JSON only:\n"
                '{"summary": "2-3 sentence description", "exports": ["list", "of", "exported", "names"]}'
            ),
        }],
    )

    import json
    try:
        data = json.loads(response.content[0].text)
        return data.get("summary", ""), data.get("exports", [])
    except (json.JSONDecodeError, IndexError, KeyError):
        return f"File at {path}.", []


async def compress_activity(bullets: list[str]) -> list[str]:
    """Compress a list of activity log entries into ≤5 concise bullets."""
    if not settings.anthropic_api_key or not bullets:
        return bullets[:5]

    client = _get_client()
    joined = "\n".join(f"- {b}" for b in bullets)
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": (
                "Summarize this team activity into 5 or fewer concise bullet points.\n"
                "Focus on what was built/published/decided. Be specific.\n\n"
                f"{joined}\n\n"
                "Respond with JSON only: {\"bullets\": [\"...\", ...]}"
            ),
        }],
    )

    import json
    try:
        data = json.loads(response.content[0].text)
        return data.get("bullets", bullets[:5])
    except (json.JSONDecodeError, IndexError, KeyError):
        return bullets[:5]
