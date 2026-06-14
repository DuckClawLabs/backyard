# Testing Backyard Locally

Run the full server on your machine, connect Claude Code to it, and verify that two engineer identities can share context through real MCP tool calls.

**What you need:**
- Docker + Docker Compose (for Redis + Postgres)
- Python 3.11+
- An Anthropic API key (for file summary generation)
- Claude Code installed (`claude` CLI, desktop app, or VS Code extension)

---

## Step 1 — Clone and install

```bash
git clone https://github.com/DuckClawLabs/backyard.git
cd backyard

pip install uv
uv pip install -e ".[dev]"
```

Verify the install:

```bash
python -c "import backyard; print('ok')"
```

---

## Step 2 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and set these (the rest can stay as defaults):

```bash
ANTHROPIC_API_KEY=sk-ant-...        # your real key — needed for file summaries
API_KEYS=key-alice,key-bob          # two keys for testing two engineers
BASE_URL=http://localhost:8000      # local URL
LOG_LEVEL=DEBUG                     # see everything during testing
```

Leave `DATABASE_URL` and `REDIS_URL` at their defaults — docker-compose sets those automatically.

---

## Step 3 — Start Redis and Postgres

```bash
docker-compose -f infra/docker-compose.yml up -d postgres redis
```

Wait for both to be healthy:

```bash
docker-compose -f infra/docker-compose.yml ps
# both should show "healthy"
```

---

## Step 4 — Run database migrations

```bash
alembic upgrade head
```

Expected output: a list of migration steps ending in `INFO  [alembic.runtime.migration] Running upgrade ...`

If you see `could not connect to server`, Postgres is not ready yet — wait 10 seconds and retry.

---

## Step 5 — Run the automated test suite

Before testing manually, verify the core services pass their unit tests:

```bash
pytest -v
```

Expected: all tests in `tests/` pass. The tests use `fakeredis` and an in-memory SQLite database — no external services needed.

You should see:
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

If tests fail here, fix them before proceeding — the server will behave incorrectly if the core services are broken.

---

## Step 6 — Start the server

```bash
uvicorn backyard.server.app:app --host 0.0.0.0 --port 8000 --reload
```

Or use docker-compose to start everything together (app + Redis + Postgres):

```bash
docker-compose -f infra/docker-compose.yml up
```

Verify the server is running:

```bash
curl http://localhost:8000/health
# Expected: {"status": "ok", "version": "0.1.0"}
```

---

## Step 7 — Create your identity file

In the directory where you run Claude Code, create `.backyard-mcp/me.yaml`:

```bash
mkdir -p .backyard-mcp
```

```yaml
# .backyard-mcp/me.yaml
project:
  name: Test Project
  id: test-project-001         # must be identical for both test engineers

  team:
    - name: Alice Chen
      email: alice@test.com
      role: backend
```

> For the two-engineer test in Step 9, you will create a second workspace with a different `me.yaml` (Bob's).

---

## Step 8 — Add Backyard to Claude Code settings

Edit (or create) `.claude/settings.json` in your home directory or project directory:

```json
{
  "mcpServers": {
    "backyard": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer key-alice"
      }
    }
  }
}
```

The `X-Workspace-Root` header is sent automatically by Claude Code with the path to the workspace. Backyard reads `me.yaml` from that path.

**Where `.claude/settings.json` lives:**
- CLI: `~/.claude/settings.json` (global) or `<project>/.claude/settings.json` (project-scoped)
- VS Code extension: same paths, picked up automatically
- Desktop app: same paths

---

## Step 9 — Verify the MCP connection

Start Claude Code in the directory that contains `.backyard-mcp/me.yaml`:

```bash
claude
```

In the Claude Code session, ask:

```
What Backyard tools do you have access to?
```

Expected response: Claude should list the MCP tools — `publish_context`, `query_shared_context`, `signal_ready`, `wait_for_signal`, `raise_resolution`, `read_file`, `write_file`, `list_files`, `get_project_status`.

If the tools are not listed, check:
- Is the server running? `curl http://localhost:8000/health`
- Is the API key in `.env` matching what's in `settings.json`?
- Does `.backyard-mcp/me.yaml` exist in the current directory?

Server logs (from the terminal where uvicorn is running) will show the connection:
```
INFO: Engineer Alice Chen (backend) connected to project test-project-001
```

---

## Step 10 — Two-engineer test

This is the real test. You need two Claude Code sessions running simultaneously, representing two engineers on the same project.

### Setup Engineer B (Bob)

Open a second terminal. Create a second workspace directory:

```bash
mkdir /tmp/bob-workspace
cd /tmp/bob-workspace
mkdir -p .backyard-mcp
```

Create Bob's identity file:

```yaml
# /tmp/bob-workspace/.backyard-mcp/me.yaml
project:
  name: Test Project
  id: test-project-001       # same project.id as Alice — this is what links them

  team:
    - name: Bob Smith
      email: bob@test.com
      role: frontend
```

Create Bob's Claude Code settings:

```bash
mkdir -p .claude
cat > .claude/settings.json << 'EOF'
{
  "mcpServers": {
    "backyard": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer key-bob"
      }
    }
  }
}
EOF
```

Start Claude Code as Bob:

```bash
claude
```

---

### Test 1: Project status shows both engineers

In either session, ask Claude:

```
Use get_project_status to show me who's connected to this project.
```

Expected: both Alice (backend) and Bob (frontend) appear in active sessions.

---

### Test 2: Signal — the stand-up that never happens

**In Bob's session**, tell Claude:

```
Wait for the signal "user-api" using wait_for_signal. Timeout 120 seconds.
```

Bob's agent is now waiting. The Claude Code session will be held open (the MCP SSE connection stays alive).

**In Alice's session**, tell Claude:

```
Publish a contract for user-api-v1 with endpoint GET /api/users/:id returning {id, email, name}.
Then signal_ready("user-api").
```

**Expected result:** Bob's `wait_for_signal` resolves immediately with the signal payload. Bob's agent receives the contract information without any human sending a message.

Check Alice's session logs on the server:
```
INFO: signal published: user-api (project: test-project-001, by: alice@test.com)
INFO: 1 waiter(s) unblocked for topic: user-api
```

---

### Test 3: Shared context — query what teammates published

**In Bob's session**, ask Claude:

```
Query the shared context for contracts published by the backend role.
```

Expected: Bob's agent returns the `user-api-v1` contract that Alice published in Test 2.

---

### Test 4: Project briefing

In either session, ask Claude:

```
What does the project briefing say right now?
```

Expected: the briefing includes both engineers (Alice + Bob), the contract published in Test 2, and no open decisions.

---

### Test 5: Conflict surface

**In Alice's session**, tell Claude:

```
Call raise_resolution with title "Database choice conflict", conflict_a "use Postgres", conflict_b "use SQLite", affects ["db/**"].
```

**In Bob's session**, ask Claude:

```
Use get_project_status to check for open decisions.
```

Expected: Bob's agent reports the open resolution card.

Check the dashboard at `http://localhost:8000/project/test-project-001` — the resolution card should be visible there.

---

## Troubleshooting

**Server fails to start:**
```
uvicorn backyard.server.app:app ...
ModuleNotFoundError: No module named 'backyard'
```
Run `uv pip install -e ".[dev]"` again and make sure you're in the repo root.

**`alembic upgrade head` fails:**
```
FATAL: password authentication failed for user "backyard"
```
Postgres is not using the docker-compose credentials. Make sure you're running Postgres via docker-compose, not a local installation.

**MCP tools not appearing in Claude Code:**
- Check the server is running: `curl http://localhost:8000/health`
- Check the API key matches: `API_KEYS` in `.env` must include the key in `settings.json`
- Check `me.yaml` exists in the workspace root (the directory where you run `claude`)
- Look at server logs — a bad `me.yaml` will print an error like `ProfileInvalidError: missing field: email`

**`wait_for_signal` times out:**
- Both sessions must be connected to the same `project.id` in their `me.yaml`
- The signal must be published after the wait is registered (or persisted in Postgres for a previous session)
- Check Redis is running: `docker-compose -f infra/docker-compose.yml ps`

**File summaries fail:**
```
anthropic.AuthenticationError
```
The `ANTHROPIC_API_KEY` in `.env` is invalid or missing. File summaries call the Anthropic API. To test without a key, skip `write_file` calls — all other tools work without it.

---

## What to verify before calling local testing done

- [ ] `pytest` passes — all unit tests green
- [ ] Server starts and `/health` returns 200
- [ ] Claude Code lists Backyard tools in a session
- [ ] `get_project_status` shows both engineers when both are connected
- [ ] `signal_ready` / `wait_for_signal` works across two sessions
- [ ] `query_shared_context` returns contracts published by the other session
- [ ] Project briefing includes teammates and published contracts
- [ ] `raise_resolution` creates a visible conflict card on the dashboard
- [ ] Server logs show audit entries for every tool call
