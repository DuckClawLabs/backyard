"""Tests for MCP file tools: read_file, write_file, list_files."""

from __future__ import annotations

import pytest

from backyard.server.mcp_hub import file_tools


PROJECT = "proj-files"


@pytest.fixture
def auth(alice):
    alice.project_id = PROJECT
    return alice


# ── read_file ─────────────────────────────────────────────────────────────────

async def test_read_file_existing(tmp_path, monkeypatch, db, auth):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("hello world")

    result = await file_tools.dispatch("read_file", {"path": "README.md"}, db, auth)
    assert result == "hello world"


async def test_read_file_missing(tmp_path, monkeypatch, db, auth):
    monkeypatch.chdir(tmp_path)

    result = await file_tools.dispatch("read_file", {"path": "missing.py"}, db, auth)
    assert "not found" in result.lower()


async def test_read_file_path_traversal_blocked(tmp_path, monkeypatch, db, auth):
    monkeypatch.chdir(tmp_path)

    result = await file_tools.dispatch("read_file", {"path": "../../etc/passwd"}, db, auth)
    assert "Error" in result


async def test_read_file_nested(tmp_path, monkeypatch, db, auth):
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "api" / "v1"
    sub.mkdir(parents=True)
    (sub / "users.py").write_text("class UserAPI: pass")

    result = await file_tools.dispatch("read_file", {"path": "api/v1/users.py"}, db, auth)
    assert "UserAPI" in result


# ── write_file ────────────────────────────────────────────────────────────────

async def test_write_file_in_domain(tmp_path, monkeypatch, fake_redis, db, auth):
    # alice is 'backend' — api/** is in-domain
    monkeypatch.chdir(tmp_path)

    result = await file_tools.dispatch(
        "write_file",
        {"path": "api/orders.py", "content": "# order service\n"},
        db,
        auth,
    )
    assert "Wrote" in result
    assert (tmp_path / "api" / "orders.py").read_text() == "# order service\n"


async def test_write_file_creates_parent_dirs(tmp_path, monkeypatch, fake_redis, db, auth):
    monkeypatch.chdir(tmp_path)

    await file_tools.dispatch(
        "write_file",
        {"path": "services/payments/gateway.py", "content": "# gateway"},
        db,
        auth,
    )
    assert (tmp_path / "services" / "payments" / "gateway.py").exists()


async def test_write_file_records_summary_in_db(tmp_path, monkeypatch, fake_redis, db, auth):
    monkeypatch.chdir(tmp_path)

    await file_tools.dispatch(
        "write_file",
        {"path": "api/health.py", "content": "def health(): return 'ok'"},
        db,
        auth,
    )

    from backyard.server.context import store
    summary = await store.get_file_summary(db, project_id=PROJECT, path="api/health.py")
    assert summary is not None
    assert summary.path == "api/health.py"


async def test_write_file_out_of_domain_triggers_proposal(tmp_path, monkeypatch, fake_redis, db, auth):
    # backend writing to ui/** requires propose_cross_domain_edit
    monkeypatch.chdir(tmp_path)

    result = await file_tools.dispatch(
        "write_file",
        {"path": "ui/App.tsx", "content": "// frontend component"},
        db,
        auth,
    )
    assert "proposed" in result.lower() or "cross-domain" in result.lower()
    assert not (tmp_path / "ui" / "App.tsx").exists()


async def test_write_file_out_of_domain_no_file_written(tmp_path, monkeypatch, fake_redis, db, auth):
    monkeypatch.chdir(tmp_path)

    await file_tools.dispatch(
        "write_file",
        {"path": "infra/docker-compose.yml", "content": "version: '3'"},
        db,
        auth,
    )
    assert not (tmp_path / "infra" / "docker-compose.yml").exists()


async def test_write_file_path_traversal_blocked(tmp_path, monkeypatch, fake_redis, db, auth):
    monkeypatch.chdir(tmp_path)

    result = await file_tools.dispatch(
        "write_file",
        {"path": "../../evil.sh", "content": "rm -rf /"},
        db,
        auth,
    )
    assert "Error" in result


# ── list_files ────────────────────────────────────────────────────────────────

async def test_list_files_empty_dir(tmp_path, monkeypatch, db, auth):
    monkeypatch.chdir(tmp_path)

    result = await file_tools.dispatch("list_files", {}, db, auth)
    assert result == "No files found."


async def test_list_files_finds_files(tmp_path, monkeypatch, db, auth):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "b.py").write_text("b")

    result = await file_tools.dispatch("list_files", {"path": "."}, db, auth)
    assert "a.py" in result
    assert "b.py" in result


async def test_list_files_nested(tmp_path, monkeypatch, db, auth):
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "main.py").write_text("# main")

    result = await file_tools.dispatch("list_files", {"path": "."}, db, auth)
    assert "main.py" in result


async def test_list_files_missing_dir(tmp_path, monkeypatch, db, auth):
    monkeypatch.chdir(tmp_path)
    # Non-existent path rglobs to nothing — returns "No files found." rather than an error
    result = await file_tools.dispatch("list_files", {"path": "nonexistent"}, db, auth)
    assert result == "No files found."


async def test_list_files_respects_gitignore(tmp_path, monkeypatch, db, auth):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/\n")
    (tmp_path / "main.py").write_text("# main")
    (tmp_path / "main.pyc").write_bytes(b"\x00\x01")

    result = await file_tools.dispatch("list_files", {"path": "."}, db, auth)
    assert "main.py" in result
    assert "main.pyc" not in result


async def test_unknown_tool(db, auth):
    result = await file_tools.dispatch("nonexistent_tool", {}, db, auth)
    assert "Unknown tool" in result
