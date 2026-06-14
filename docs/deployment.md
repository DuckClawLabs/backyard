# Backyard — Deployment Guide

Three ways to run Backyard. Choose the one that fits your team.

---

## Deployment options at a glance

| Option | Who it's for | Setup time | Data location |
|---|---|---|---|
| [Hosted (SaaS)](#option-1--hosted-saas) | Teams that want zero ops | Minutes | Backyard cloud |
| [Railway](#option-2--railway-5-minutes) | Teams that want their own infra, no server management | 5 minutes | Your Railway account |
| [Self-hosted](#option-3--self-hosted-enterprise) | Teams with data residency, compliance, or private-network requirements | 30 minutes | Your servers |

All three options use the same Backyard server. The difference is who runs the infrastructure.

---

## Option 1 — Hosted (SaaS)

No setup. Add one line to `.claude/settings.json` and your team is connected.

1. Go to [backyard.app](https://backyard.app) *(coming soon)* → create an account → create a project
2. Invite your engineers
3. Each engineer adds this to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "backyard": {
      "url": "https://backyard.app/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    }
  }
}
```

4. Each engineer creates their profile at `.backyard-mcp/me.yaml` in their workspace (see [Engineer setup](#engineer-setup) below)

That's it. The server is already running.

---

## Option 2 — Railway (5 minutes)

Best for teams that want their data on their own infrastructure without managing servers.

### Step 1 — Fork or clone this repo

Push it to your GitHub account.

### Step 2 — Deploy on Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
2. Select your Backyard repo
3. Railway auto-detects the `Dockerfile` and deploys

### Step 3 — Add Redis and Postgres

In your Railway project, click **+ New** and add:
- **Redis** → select the Redis template
- **PostgreSQL** → select the Postgres template

Railway automatically injects `REDIS_URL` and `DATABASE_URL` into the app — no manual wiring needed.

### Step 4 — Set environment variables

In Railway → your app service → **Variables**, add:

```
ANTHROPIC_API_KEY   =  sk-ant-...
API_KEYS            =  key-alice,key-bob,key-carol
BASE_URL            =  https://your-app.up.railway.app
LOG_LEVEL           =  INFO
```

`API_KEYS` is a comma-separated list of API keys you give to each engineer. Each engineer uses their own key. No dashboard needed in Phase 1A — keys are set here and distributed to engineers.

### Step 5 — Run database migrations

```bash
railway run alembic upgrade head
```

### Step 6 — Engineers connect

Each engineer:
1. Creates `.backyard-mcp/me.yaml` in their workspace (see [Engineer setup](#engineer-setup) below)
2. Adds this to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "backyard": {
      "url": "https://your-app.up.railway.app/mcp",
      "headers": { "Authorization": "Bearer key-alice" }
    }
  }
}
```

Done. The whole team is connected. Engineers connect to `https://your-app.up.railway.app/mcp` — one URL, one time setup.

---

## Option 3 — Self-hosted (enterprise)

For teams that need data residency, private networking, or compliance controls.

**Requirements:** a Linux server with Docker and Docker Compose installed.

### Step 1 — Clone and configure

```bash
git clone https://github.com/DuckClawLabs/backyard.git
cd backyard

# Copy the example env file and fill it in
cp .env.example .env
```

Open `.env` and set:
```bash
ANTHROPIC_API_KEY=sk-ant-...
API_KEYS=key-alice,key-bob,key-carol
BASE_URL=https://your-internal-domain.com
POSTGRES_PASSWORD=choose-a-strong-password
```

See [Environment variables reference](#environment-variables-reference) for all options.

### Step 2 — Start all services

```bash
docker-compose -f infra/docker-compose.prod.yml up -d
```

This starts:
- The Backyard MCP server on port 8000
- Redis 7
- Postgres 16

### Step 3 — Run database migrations

```bash
docker-compose -f infra/docker-compose.prod.yml exec app alembic upgrade head
```

### Step 4 — (Optional) HTTPS with nginx

If you want HTTPS (recommended for production), put nginx in front:

```nginx
server {
    listen 443 ssl;
    server_name your-internal-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # Required for SSE (MCP transport)
        proxy_buffering off;
        proxy_cache off;
    }
}
```

Use Certbot to get a free Let's Encrypt certificate.

### Step 5 — Engineers connect

Same as Railway above — each engineer creates their `me.yaml` and adds the URL to `.claude/settings.json`.

```json
{
  "mcpServers": {
    "backyard": {
      "url": "https://your-internal-domain.com/mcp",
      "headers": { "Authorization": "Bearer key-alice" }
    }
  }
}
```

For SSO/SAML, SCIM provisioning, and SOC 2 audit controls — see [Phase 1B in the roadmap](roadmap.md).

---

## Local development

For contributors and engineers who want to run Backyard locally before deploying.

```bash
# Clone and install
git clone https://github.com/DuckClawLabs/backyard.git
cd backyard
pip install uv
uv pip install -e ".[dev]"

# Copy and fill env (ANTHROPIC_API_KEY is required; others have defaults)
cp .env.example .env

# Start Redis + Postgres (Docker required)
docker-compose -f infra/docker-compose.yml up

# Apply database migrations (in a second terminal)
alembic upgrade head

# The server is now running at http://localhost:8000 with live reload
# Run the test suite
pytest
```

The dev docker-compose uses volume mounts so source changes are reflected immediately (uvicorn `--reload`).

---

## Engineer setup

Every engineer on the team does this once, regardless of which deployment option you chose.

### 1. Create your identity file

In the root of **each workspace** where you use Claude Code, create `.backyard-mcp/me.yaml`:

```yaml
project:
  name: Acme Payments Service      # human-readable project name
  id: payments-service             # shared key — must be the same for all teammates

  team:
    - name: Alice Chen             # your full name (required)
      email: alice@acme.com        # your email (required)
      role: backend                # your role: frontend | backend | devops | reviewer
      owns: ["api/**", "services/**"]   # optional — overrides the role's default domains
```

**The `project.id` field is what links teammates together.** Every engineer on the same project must use the same `project.id`. The server groups you by this key — no dashboard registration needed.

`me.yaml` is gitignored by default (already in `.gitignore`). Do not commit it — it is personal to each engineer.

### 2. Add the MCP server to Claude Code settings

```json
// .claude/settings.json
{
  "mcpServers": {
    "backyard": {
      "url": "https://your-backyard-server.com/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    }
  }
}
```

This works from any Claude Code surface: CLI (`claude`), desktop app, VS Code extension, or web. No new tool to install. The engineer keeps using Claude Code exactly as before.

### 3. Start a Claude Code session

The next time you start Claude Code, the Backyard MCP server connects automatically. The agent's first turn will include a project briefing showing who else is connected and what they've published. No further setup needed.

---

## Roles

Each engineer sets their role in `me.yaml`. The role controls the agent's default domain (which files it can write without asking) and what coordination tools it has access to.

| Role | Default domain | What the agent can do without asking |
|---|---|---|
| `frontend` | `ui/**` `components/**` `styles/**` `pages/**` | Write domain files, read any file, publish FE contracts, use signals |
| `backend` | `api/**` `services/**` `db/**` `middleware/**` | Write domain files, read any file, publish API contracts, own migrations |
| `devops` | `infra/**` `*.yml` `Dockerfile` `.github/**` | Write domain files, trigger CI, publish infra contracts |
| `reviewer` | read-everywhere | Comment, approve changes, record ADRs (writes only via proposals) |

If an agent needs to write a file outside its role's domain, the MCP Hub automatically routes the request to the owning engineer for approval — the agent does not just get blocked, it asks first.

Custom roles can be defined in `backyard.toml` in the project repo. See [§10 of the technical report](technical-report.md#10-role-system) for details.

---

## Environment variables reference

All variables with defaults are optional.

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Used for file summary generation and activity compression |
| `API_KEYS` | Yes | — | Comma-separated API keys for engineers (Phase 1A auth). Example: `key-alice,key-bob` |
| `DATABASE_URL` | Yes | — | Postgres connection string. Example: `postgresql+asyncpg://user:pass@localhost/backyard` |
| `REDIS_URL` | Yes | — | Redis connection string. Example: `redis://localhost:6379` |
| `BASE_URL` | Yes | — | Public URL of your Backyard deployment. Used in dashboard links. |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `POSTGRES_PASSWORD` | No | — | Only needed by docker-compose.prod.yml (Postgres container) |

---

## Health check

Once deployed, verify the server is running:

```bash
curl https://your-backyard-server.com/health
# → {"status": "ok", "version": "0.1.0"}
```

---

## Updating

**Railway:** push a new commit to your GitHub repo. Railway auto-deploys.

**Self-hosted:**

```bash
git pull
docker-compose -f infra/docker-compose.prod.yml build
docker-compose -f infra/docker-compose.prod.yml up -d
docker-compose -f infra/docker-compose.prod.yml exec app alembic upgrade head
```

Always run migrations after updating — new versions may add database tables or columns.
