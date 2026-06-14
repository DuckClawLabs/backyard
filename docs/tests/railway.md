# Testing Backyard on Railway

Deploy the server to Railway, connect real Claude Code sessions to it, and verify the full two-engineer flow on live infrastructure.

**Why Railway for testing?**
Railway gives you a real public URL (`https://your-app.up.railway.app`) so you can test with the exact Claude Code configuration that your team will use in production — no `localhost`, no tunnels, no port forwarding. Once this works, the only difference between Railway and enterprise self-hosted is who manages the servers. The application code, MCP connection, and engineer workflow are identical.

**What you need:**
- A [Railway account](https://railway.app) (free tier works)
- A GitHub account (Railway deploys from GitHub)
- An Anthropic API key
- Claude Code installed

---

## Part 1 — Deploy to Railway

### Step 1 — Push the repo to GitHub

Fork or clone this repo and push it to your GitHub account.

```bash
git clone https://github.com/DuckClawLabs/backyard.git
cd backyard
# push to your own GitHub account
git remote set-url origin https://github.com/YOUR_USERNAME/backyard.git
git push -u origin main
```

---

### Step 2 — Create a Railway project

1. Go to [railway.app](https://railway.app) → sign in → **New Project**
2. Choose **Deploy from GitHub repo**
3. Select your `backyard` repo
4. Railway detects the `Dockerfile` automatically and starts the build

Wait for the build to complete (usually 2–3 minutes). The deploy will fail at first — the app needs Redis and Postgres, which we add next.

---

### Step 3 — Add Redis

In your Railway project:
1. Click **+ New**
2. Select **Redis** from the template list
3. Railway provisions Redis and injects `REDIS_URL` into your app service automatically

---

### Step 4 — Add Postgres

1. Click **+ New** again
2. Select **PostgreSQL** from the template list
3. Railway provisions Postgres and injects `DATABASE_URL` automatically

---

### Step 5 — Set environment variables

Click on your **app service** → **Variables** → add:

```
ANTHROPIC_API_KEY   =  sk-ant-...
LOG_LEVEL           =  INFO
```

`BASE_URL` will be set after Railway assigns a public URL (next step).

Railway auto-redeploys after you save variables.

---

### Step 6 — Get your public URL and set BASE_URL

In your Railway app service → **Settings** → scroll to **Domains** → click **Generate Domain**.

You'll get a URL like `https://backyard-production-abc123.up.railway.app`.

Go back to **Variables** and add:

```
BASE_URL  =  https://backyard-production-abc123.up.railway.app
```

Save → Railway redeploys.

---

### Step 7 — Run database migrations

Railway gives you a shell into your running container. In your app service, click **Shell**:

```bash
alembic upgrade head
```

Or use the Railway CLI:

```bash
npm install -g @railway/cli
railway login
railway link   # link to your project
railway run alembic upgrade head
```

Expected: migration steps complete with no errors.

---

### Step 8 — Verify the deployment

```bash
curl https://your-app.up.railway.app/health
# Expected: {"status": "ok", "version": "0.1.0"}
```

If this returns 200, the server is running.

---

## Part 2 — Engineer setup

Each engineer does this once. No dashboard required in Phase 1A.

### Create your identity file

In each workspace where you use Claude Code, create `.backyard-mcp/me.yaml`:

```bash
mkdir -p .backyard-mcp
```

**Engineer A (Alice — backend):**

```yaml
# .backyard-mcp/me.yaml
project:
  name: My Test Project
  id: test-project-railway-001   # must be identical for both engineers

  team:
    - name: Alice Chen
      email: alice@yourcompany.com
      role: backend
```

**Engineer B (Bob — frontend):**

```yaml
# .backyard-mcp/me.yaml  (in Bob's workspace)
project:
  name: My Test Project
  id: test-project-railway-001   # same project.id — this is what links them

  team:
    - name: Bob Smith
      email: bob@yourcompany.com
      role: frontend
```

> `me.yaml` is in `.gitignore` by default. It is personal — do not commit it.

---

### Add Backyard to Claude Code settings

**Alice's `.claude/settings.json`:**

```json
{
  "mcpServers": {
    "backyard": {
      "url": "https://your-app.up.railway.app/mcp"
    }
  }
}
```

**Bob's `.claude/settings.json`:**

```json
{
  "mcpServers": {
    "backyard": {
      "url": "https://your-app.up.railway.app/mcp",
      "headers": {
        "Authorization": "Bearer key-bob"
      }
    }
  }
}
```

Same URL for both — the server reads their identity from `me.yaml`. Only the API key differs.

---

## Part 3 — Run the test scenarios

### Verify MCP connection

Start Claude Code in the directory containing `.backyard-mcp/me.yaml`:

```bash
claude
```

Ask Claude:

```
What Backyard tools do you have access to?
```

Expected: Claude lists `publish_context`, `query_shared_context`, `signal_ready`, `wait_for_signal`, `raise_resolution`, `read_file`, `write_file`, `list_files`, `get_project_status`.

Check Railway logs (app service → **Logs**) — you should see:

```
INFO: Engineer Alice Chen (backend) connected to project test-project-railway-001
```

---

### Test 1 — Both engineers visible

With both Claude Code sessions running (Alice and Bob), ask either one:

```
Use get_project_status to show me who's connected to this project.
```

Expected: both `Alice Chen (backend)` and `Bob Smith (frontend)` appear as active sessions.

---

### Test 2 — Signal across real network

**In Bob's Claude Code session:**

```
Wait for the signal "auth-api" using wait_for_signal with a 180 second timeout.
```

Bob's agent is now waiting. The MCP SSE connection to the Railway server stays open.

**In Alice's Claude Code session:**

```
Publish a contract for auth-api-v1 with endpoint POST /api/auth/login returning {token, expires_at}.
Then call signal_ready("auth-api").
```

**Expected:** Bob's `wait_for_signal` resolves immediately. Bob's agent receives the signal and the contract payload — across the public internet, through the Railway server, with no human relay.

Railway logs should show:

```
INFO: signal published: auth-api (by: alice@yourcompany.com)
INFO: 1 waiter(s) unblocked for topic: auth-api
```

---

### Test 3 — Shared context persists across reconnects

This tests that Postgres persistence works correctly (vs. Redis-only, which would lose state on disconnect).

1. Start Alice's session → publish a contract → disconnect (Ctrl+C)
2. Reconnect Alice's session
3. Ask Alice: `Query the shared context for any published contracts`

Expected: the contract from before the disconnect is still there. This confirms Postgres is storing context durably, not just in Redis.

---

### Test 4 — Project briefing over real infra

In either session:

```
What does the project briefing say right now?
```

Expected briefing includes:
- Both engineers' names and roles
- The contract published in Test 2
- Session time (how long each engineer has been connected)
- No open decisions

This confirms the briefing is assembled from live Redis + Postgres state on the Railway server.

---

### Test 5 — Conflict resolution card

**In Alice's session:**

```
Call raise_resolution with title "API versioning strategy", conflict_a "use semantic versioning (user-api-v1, v2)", conflict_b "use date-based versioning (user-api-2026-06)", affects ["api/**"].
```

**In Bob's session:**

```
Use get_project_status to check for open decisions.
```

Expected: Bob's agent reports the open resolution card created by Alice.

Check the dashboard at `https://your-app.up.railway.app/project/test-project-railway-001` — the resolution card should be visible.

---

### Test 6 — File summary generation

This tests the Anthropic API integration (file summaries).

**In Alice's session:**

```
Write a file called api/users.py with this content:
"""User management endpoints."""
from fastapi import APIRouter
router = APIRouter()

@router.get("/users/{user_id}")
async def get_user(user_id: str):
    return {"id": user_id, "email": "alice@example.com", "name": "Alice"}
```

**In Bob's session:**

```
Get the file summary for api/users.py
```

Expected: Bob's agent returns a 2–3 sentence summary of the file and its exported symbols — generated by the Anthropic API at write time. This confirms the full `write_file` → summarize → `get_file_summary` flow works end-to-end.

---

## Part 4 — Check Railway logs and audit trail

### View server logs

In Railway → app service → **Logs**. You should see audit entries for every tool call:

```
DEBUG: audit: alice@test.com | backend | publish_context | artifact_id=user-api-v1
DEBUG: audit: alice@test.com | backend | signal_ready | topic=auth-api | notified=1
DEBUG: audit: bob@test.com | frontend | wait_for_signal | topic=auth-api | resolved=immediate
```

### Verify audit log via API

```bash
curl https://your-app.up.railway.app/project/test-project-railway-001/status
```

Expected: JSON with `active_sessions` and `open_resolutions`.

---

## Part 5 — Teardown

When you're done testing:

```bash
# Stop both Claude Code sessions (Ctrl+C or /exit)
```

On Railway: you can pause or delete the project from the Railway dashboard to stop billing. The free tier has enough hours for thorough testing.

---

## Railway vs enterprise self-hosted — the difference in practice

Once Railway testing passes, the only things that change for enterprise self-hosted are:

| | Railway | Enterprise self-hosted |
|---|---|---|
| Who runs infra | Railway (managed) | Your team (Docker on your servers) |
| Public URL | `*.up.railway.app` | Your domain (`backyard.yourcompany.com`) |
| HTTPS | Automatic (Railway) | You configure nginx + certbot |
| `DATABASE_URL` | Auto-injected by Railway | You set in `.env` |
| `REDIS_URL` | Auto-injected by Railway | You set in `.env` |
| Migrations | `railway run alembic upgrade head` | `docker-compose exec app alembic upgrade head` |
| Updates | Push to GitHub → auto-deploy | `git pull && docker-compose build && docker-compose up -d` |

The application code, `me.yaml` format, `.claude/settings.json` config, and all MCP tool behavior are identical. If the Railway tests pass, the enterprise self-hosted deployment will work the same way.

See [deployment.md](../deployment.md) for the full self-hosted setup guide.

---

## Troubleshooting

**Railway build fails:**
Check the Dockerfile builds locally first: `docker build -t backyard .`

**`alembic upgrade head` in Railway shell fails:**
`DATABASE_URL` must be injected by the Postgres service. Verify in Railway → app service → Variables that `DATABASE_URL` appears (it is auto-injected, not set manually).

**MCP tools not appearing in Claude Code:**
- Confirm `curl https://your-app.up.railway.app/health` returns 200
- Check Railway logs for `ProfileNotFoundError` — means `me.yaml` is missing in the workspace

**`wait_for_signal` never resolves:**
- SSE connections can time out through Railway's proxy. If the wait times out prematurely, set `timeout` shorter (60s) and check Railway logs for connection drops.
- Confirm both sessions use the same `project.id` in their `me.yaml`

**File summaries return null:**
`ANTHROPIC_API_KEY` is not set or invalid in Railway Variables. Add it and Railway will redeploy automatically.

---

## Checklist before calling Railway testing done

- [ ] `curl /health` returns 200 on the Railway URL
- [ ] Claude Code lists Backyard tools in both Alice and Bob sessions
- [ ] `get_project_status` shows both engineers simultaneously
- [ ] `signal_ready` / `wait_for_signal` resolves across two real Claude Code sessions
- [ ] `query_shared_context` returns contracts across sessions
- [ ] Project briefing shows correct team state
- [ ] `raise_resolution` creates a visible conflict card
- [ ] File summary is generated on `write_file` and retrievable by the other session
- [ ] Audit entries appear in Railway logs for every tool call
- [ ] Context persists across a session disconnect and reconnect (Postgres durability)
