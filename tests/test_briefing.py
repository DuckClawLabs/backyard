"""Briefing assembly tests."""

from __future__ import annotations

import pytest

from backyard.server.context.briefing import assemble_briefing


@pytest.mark.asyncio
async def test_briefing_renders(db, fake_redis):
    briefing = await assemble_briefing(
        db=db,
        project_id="proj-test",
        project_name="Test Project",
        engineer_id="alice-id",
        role="backend",
    )
    rendered = briefing.render()
    assert "PROJECT BRIEFING" in rendered
    assert "backend" in rendered
    assert "Test Project" in rendered
    assert "END BRIEFING" in rendered


@pytest.mark.asyncio
async def test_briefing_token_budget(db, fake_redis):
    from backyard.server.context.briefing import record_activity

    # Flood activity with long bullets
    for i in range(50):
        await record_activity("proj-test", "x" * 200)

    briefing = await assemble_briefing(
        db=db,
        project_id="proj-test",
        project_name="Test Project",
        engineer_id="alice-id",
        role="backend",
    )
    rendered = briefing.render()
    # Rough token estimate: 1 token ≈ 4 chars; budget is 2000 tokens = 8000 chars
    assert len(rendered) <= 8000 + 500   # small headroom for format overhead
