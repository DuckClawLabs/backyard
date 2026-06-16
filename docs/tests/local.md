# Local Testing — Creator / Developer Verification

This guide is for **the person building Backyard** — verifying that the server code works correctly before deploying it anywhere.

You are one person, on one machine, running the server locally. You are checking that the code is correct: tests pass, the server starts, the MCP connection works, and the tools return the right data. This is not a multi-engineer test — that requires a shared deployed server. See [railway.md](railway.md) for the real multi-engineer test.

**What you need:**
- Docker + Docker Compose (for Redis + Postgres)
- Python 3.11+
- An Anthropic API key (for file summary generation)
- Claude Code installed

---

## Step 1 — Clone and install

```bash
git clone https://github.com/DuckClawLabs/backyard.git
cd backyard

pip install uv
uv pip install -e ".[dev]"
```

Verify:

```bash
python -c "import backyard; print('ok')"
```

---

## Step 2 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and set:

```bash
ANTHROPIC_API_KEY=sk-ant-...        # your real key — needed for file summaries
BASE_URL=http://localhost:8000
LOG_LEVEL=DEBUG                     # see everything during testing
```

Leave `DATABASE_URL` and `REDIS_URL` at their defaults — docker-compose sets those.

---

## Step 3 — Start Redis and Postgres

> **Note:** Use `docker compose` (with a space), not `docker-compose`. The hyphenated command is the old standalone binary; modern Docker ships the Compose plugin instead.

```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
```

Wait for both to be healthy:

```bash
docker compose -f infra/docker-compose.yml ps
# both should show "healthy" and list port mappings (0.0.0.0:5432->5432/tcp, 0.0.0.0:6379->6379/tcp)
```

**If Postgres shows no port mapping for 5432**, something else is occupying that port — usually a locally installed Postgres service. Stop it first:

```bash
sudo systemctl stop postgresql
docker compose -f infra/docker-compose.yml down
docker compose -f infra/docker-compose.yml up -d postgres redis
```

**If you're re-running after a previous failed setup**, the Postgres volume may be initialized with wrong credentials. Wipe it and start fresh:

```bash
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d postgres redis
```

---

## Step 4 — Run database migrations

```bash
alembic upgrade head
```

If you see `could not connect to server`, Postgres is not ready yet — wait 10 seconds and retry.

---

## Step 5 — Run the automated test suite

This is the primary local verification step.

```bash
PYTHONPATH="" uv run pytest tests/ -v
```

`PYTHONPATH=""` is required if you have ROS installed — ROS injects pytest plugins via `PYTHONPATH` that are incompatible with this project's pytest version. Clearing it prevents those plugins from loading.

Tests use `fakeredis` and an in-memory SQLite database — no external services needed. All tests should pass before you deploy anything.

Expected output:

```
tests/test_signal_engine.py::test_publish_then_wait PASSED
tests/test_signal_engine.py::test_persistent_signal PASSED
tests/test_signal_engine.py::test_wait_timeout PASSED
tests/test_signal_engine.py::test_signal_unblocks_waiter PASSED
tests/test_context_store.py::test_publish_and_get_contract PASSED
tests/test_context_store.py::test_contract_versioning PASSED
tests/test_context_store.py::test_publish_adr PASSED
tests/test_context_store.py::test_adr_auto_numbering PASSED
tests/test_context_store.py::test_upsert_file_summary PASSED
tests/test_context_store.py::test_search_by_type PASSED
tests/test_context_store.py::test_search_by_role PASSED
tests/test_briefing.py::test_briefing_renders PASSED
tests/test_briefing.py::test_briefing_token_budget PASSED
tests/test_profile_reader.py::... (8 tests) PASSED
```

If any test fails, fix it before proceeding — a broken unit test means the server is broken.

---

## Step 6 — Start the server

```bash
uv run uvicorn backyard.server.app:app --host 0.0.0.0 --port 8000
```

> **Do not use `--reload` when testing MCP.** `--reload` restarts the server process on every file change, which drops all active SSE sessions. Claude Code does not reconnect automatically — every reload breaks the MCP connection and requires starting a new Claude Code session.

Verify it's running:

```bash
curl http://localhost:8000/health
# Expected: {"status": "ok", "version": "0.1.0"}
```

---

## Step 7 — Create your identity file

In your current directory, create `.backyard-mcp/me.yaml`:

```bash
mkdir -p .backyard-mcp
```

```yaml
# .backyard-mcp/me.yaml
project:
  name: Test Project
  id: test-project-local-001

  team:
    - name: Your Name
      email: you@test.com
      role: backend
```

---

## Step 8 — Connect Claude Code to the local server

Claude Code reads MCP server configuration from a `settings.json` file. You can place this at two levels:

| Location | Scope |
|---|---|
| `~/.claude/settings.json` | Global — applies to every Claude Code session on your machine |
| `.claude/settings.json` (repo root) | Project-scoped — only active when you run `claude` from this directory |

For local testing, either works. Use the project-scoped file if you don't want Backyard active in every session.

**Create or edit the file:**

```bash
# Global (recommended for local testing)
mkdir -p ~/.claude
nano ~/.claude/settings.json

# OR project-scoped
mkdir -p .claude
nano .claude/settings.json
```

**Full settings.json for local Backyard:**

```json
{
  "mcpServers": {
    "backyard": {
      "type": "sse",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Field reference:

| Field | Value | Notes |
|---|---|---|
| `"type"` | `"sse"` | **Required.** Without this, Claude Code treats the URL as a stdio command and fails silently |
| `"url"` | `"http://localhost:8000/mcp"` | Local server address. Change port if you used a different one in Step 6 |

If you already have other MCP servers configured, add `"backyard"` alongside them — do not replace the existing `mcpServers` object:

```json
{
  "mcpServers": {
    "existing-server": {
      "type": "stdio",
      "command": "some-command"
    },
    "backyard": {
      "type": "sse",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Start Claude Code from the directory containing your `.backyard-mcp/me.yaml`:**

```bash
claude
```

Ask:

```
What Backyard tools do you have access to?
```

Expected: Claude lists the full MCP tool catalog — `publish_context`, `query_shared_context`, `signal_ready`, `wait_for_signal`, `raise_resolution`, `read_file`, `write_file`, `list_files`, `get_project_status`.

Server logs should show:

```
INFO: Engineer Your Name (backend) connected to project test-project-local-001
```

---

## Step 9 — Verify each tool category works

You are the only engineer here. You are testing that the tools function correctly, not that multi-engineer coordination works. Test each group:

**Context:**

```
Publish a contract called "user-api-v1" with endpoint GET /api/users/:id returning {id, email, name}.
Then query shared context for all contracts.
```

Expected: contract is stored and returned.

**Signals:**

```
Call signal_ready("test-signal") with message "signal works".
Then call wait_for_signal("test-signal") — it should return immediately because the signal was already published.
```

Expected: `wait_for_signal` resolves immediately (Postgres persistence working).

**Briefing:**

```
What does the project briefing say right now?
```

Expected: briefing shows you as the active engineer, lists the contract you published, no open decisions.

**File summary (Anthropic API integration):**

```
Write a file called src/test.py with a simple Python function that adds two numbers.
Then call get_file_summary for src/test.py.
```

Expected: a 2–3 sentence summary is returned. If `ANTHROPIC_API_KEY` is invalid, this will fail with an auth error — fix the key.

**Conflict surface:**

```
Call raise_resolution with title "test conflict", conflict_a "option A", conflict_b "option B", affects ["src/**"].
Then call get_project_status and check for open decisions.
```

Expected: resolution card created, visible in `get_project_status` and at `http://localhost:8000/project/test-project-local-001`.

---

## Step 10 — Simulate two identities from one machine (logic check only)

You can open a second terminal and run Claude Code from a different directory with a different `me.yaml`. Both sessions talk to the same local server and the same local database.

This is useful for checking that the logic is correct — that two sessions on the same `project.id` see each other's data. It is **not** a realistic multi-engineer test because both sessions are on the same machine, same network, with no latency.

```bash
# Terminal 2
mkdir /tmp/test-b && cd /tmp/test-b
mkdir -p .backyard-mcp .claude

cat > .backyard-mcp/me.yaml << 'EOF'
project:
  name: Test Project
  id: test-project-local-001   # same project.id

  team:
    - name: Test Engineer B
      email: b@test.com
      role: frontend
EOF

cat > .claude/settings.json << 'EOF'
{
  "mcpServers": {
    "backyard": {
      "type": "sse",
      "url": "http://localhost:8000/mcp"
    }
  }
}
EOF

claude
```

In this second session, ask:

```
Query shared context for contracts. Who is connected to this project?
```

Expected: returns the contract published by the first session, and shows both engineers as active.

This confirms the shared state works. For the real multi-engineer experience — separate machines, real network, real latency — use Railway.

---

## Troubleshooting

**`pytest` fails immediately:**
`uv pip install -e ".[dev]"` may not have installed test dependencies. Run it again.

**Server fails to start — `ModuleNotFoundError`:**
You are not in the repo root, or the install is broken. Run `uv pip install -e ".[dev]"` from the repo root.

**`alembic upgrade head` fails — `password authentication failed`:**
The Postgres volume was initialized with different credentials (e.g. from a previous run). Wipe the volume and restart:
```bash
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d postgres redis
```

**`alembic upgrade head` fails — `Connect call failed ('127.0.0.1', 5432)`:**
Postgres is not reachable on the host. Check `docker compose -f infra/docker-compose.yml ps` — if port 5432 is not listed in the PORTS column, something was holding that port when Docker started. Stop the conflicting process (`sudo systemctl stop postgresql`) and do a full `down` + `up` (not just `restart`) so Docker re-binds the port.

**Tools fail with "Could not find session" / "Error POSTing to endpoint (HTTP 404)":**
The server was restarted after Claude Code connected. `SseServerTransport` stores sessions in memory — a server restart wipes them all. Claude Code does not reconnect automatically. Start a new Claude Code session (open a new conversation) to re-establish the MCP connection. Never use `--reload` when testing MCP tools.

**Claude Code does not list Backyard tools:**
- `curl http://localhost:8000/health` — if this fails, the server is not running
- Confirm `"type": "sse"` is present in your `mcpServers` config — omitting it causes a silent connection failure
- Check `.backyard-mcp/me.yaml` exists in the directory where you run `claude` and contains real values (not the example placeholders)
- Start a **new** Claude Code session after any server restart — existing sessions do not reconnect automatically
- Look at server logs — a malformed `me.yaml` prints a clear error message inside the Claude session

**File summary returns null / Anthropic error:**
`ANTHROPIC_API_KEY` in `.env` is missing or wrong. All other tools work without it.

---

## Local testing checklist

- [ ] `PYTHONPATH="" uv run pytest tests/ -v` — all 21 tests pass
- [ ] Server starts, `curl /health` returns 200
- [ ] Claude Code lists Backyard tools
- [ ] `publish_context` + `query_shared_context` round-trip works
- [ ] `signal_ready` after publish resolves `wait_for_signal` immediately
- [ ] Project briefing shows correct state
- [ ] File summary is generated on `write_file` (requires Anthropic key)
- [ ] `raise_resolution` creates a conflict card visible in `get_project_status`
- [ ] Two-identity logic check: second session sees first session's data

When all of these pass, deploy to Railway for the real multi-engineer test.
