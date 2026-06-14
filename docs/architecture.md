# Backyard — Architecture Reference

Quick reference for components, data flows, and storage. Full design in [`technical-report.md`](./technical-report.md). Deployment instructions in [`deployment.md`](./deployment.md).

---

## Overview

Backyard is a single MCP server that every engineer's Claude Code connects to with one line of config. From that connection onward, every agent on the team shares the same brain — the same contracts, the same decisions, the same real-time signals.

```
                 ┌──────────── BACKYARD MCP SERVER ────────────┐
                 │          (Python · FastAPI · asyncio)        │
                 │                                              │
                 │  ① MCP Hub          ② Shared Context Store  │
                 │  ③ Signal Engine    ④ Project Briefing       │
                 │  ⑤ Audit Log        ⑥ Conflict Surface       │
                 │  ⑦ Web Dashboard                             │
                 └──────────────────────────────────────────────┘
                       ▲               ▲               ▲
                 MCP   │         MCP   │         MCP   │
          ┌────────────┴──┐  ┌─────────┴──┐  ┌────────┴──────┐
          │  Engineer A   │  │ Engineer B  │  │  Engineer C   │
          │  Claude Code  │  │ Claude Code │  │  Claude Code  │
          │  Role:Frontend│  │ Role:Backend│  │ Role:Reviewer │
          │  (any surface)│  │(any surface)│  │  (any surface)│
          └───────────────┘  └─────────────┘  └───────────────┘

               ┌───────────────────────────────────────┐
               │  Redis 7        Postgres 16            │
               │  pub/sub        contracts · ADRs       │
               │  signals        file summaries         │
               │  hot state      audit log              │
               │  briefing cache project config         │
               └───────────────────────────────────────┘
```

---

## Components

| # | Component | Core job |
|---|---|---|
| ① | **MCP Hub** | The entry point. Authenticates engineers (API token), reads their role from `.backyard-mcp/me.yaml`, routes tool calls to the right internal service, enforces role domain policies, writes every call to the audit log. One MCP connection per engineer session. |
| ② | **Shared Context Store** | Structured artifacts — contracts, ADRs, file summaries — in Postgres (durable) with Redis hot-read cache. Agents publish and query through the MCP Hub. No raw conversation history. |
| ③ | **Signal Engine** | Redis pub/sub. `signal_ready(topic)` broadcasts to all subscribers. `wait_for_signal(topic)` blocks until the signal arrives. If the signal was already published, returns immediately (Postgres persistence). |
| ④ | **Project Briefing** | Assembled fresh at the start of every agent turn: who is active (Redis), what was published recently (compressed activity), what contracts exist (Postgres), what decisions are open. ≤2 000 tokens. Injected as an MCP resource — zero prompt engineering required. |
| ⑤ | **Audit Log** | Append-only Postgres table. Every tool call from every agent: `(project_id, engineer_id, role, session_id, turn_id, timestamp, tool_name, arguments_json, result_summary, latency_ms, checksum)`. Always on. Cannot be disabled. Row-level SHA-256 checksums for tamper evidence. |
| ⑥ | **Conflict Surface** | Detects contradictory decisions (explicit `raise_resolution` calls, domain write collisions, ADR contradictions, breaking contract version changes). Posts resolution cards to the dashboard, pauses the relevant agents, and waits for engineers to decide. No auto-resolution. |
| ⑦ | **Web Dashboard** | FastAPI-served static HTML. Shows: who is active, recent agent activity, published contracts, open decisions, audit log viewer. Engineers resolve conflict cards here. Live updates via SSE. |

---

## How engineers connect

### The MCP endpoint

One URL per Backyard deployment. Never changes, regardless of which project an engineer is working on.

```json
// .claude/settings.json  (one-time addition per engineer)
{
  "mcpServers": {
    "backyard": {
      "url": "https://backyard.yourcompany.com/mcp",
      "headers": { "Authorization": "Bearer YOUR_API_KEY" }
    }
  }
}
```

Works from any Claude Code surface: CLI (`claude`), desktop app, VS Code extension, web. No new tool to install.

### The identity file

Project identity is not set in the MCP URL. Each engineer creates a personal file in their workspace:

```yaml
# .backyard-mcp/me.yaml  (gitignored — do not commit)
project:
  name: Acme Payments Service
  id: payments-service             # this is what links teammates together

  team:
    - name: Alice Chen             # required
      email: alice@acme.com        # required
      role: backend                # frontend | backend | devops | reviewer
      owns: ["api/**", "services/**"]   # optional — overrides role defaults
```

When Claude Code connects to `/mcp`, the server reads `me.yaml` from the `X-Workspace-Root` header path. Engineers from different workspaces with the same `project.id` are grouped into one shared project. No dashboard registration needed in Phase 1A.

### Connection lifecycle

1. Claude Code opens an SSE connection to `GET /mcp` with the API token in `Authorization`
2. Server reads `.backyard-mcp/me.yaml` from the workspace root
3. Server authenticates the token, registers the session in Redis (`sessions:{project_id}`)
4. Server sends the full MCP tool catalog to Claude Code
5. On every agent turn, Claude Code calls `GET /mcp/resources` → server returns the project briefing
6. On disconnect: session entry removed from Redis; audit log entry written

---

## MCP tool catalog

| Group | Tools | Available to |
|---|---|---|
| **Context** | `query_shared_context`, `publish_context`, `get_file_summary`, `get_project_status` | All roles |
| **Signals** | `signal_ready`, `wait_for_signal` | All roles |
| **Coordination** | `propose_cross_domain_edit`, `raise_resolution`, `request_clarification` | All roles |
| **File tools** (pass-through + interception) | `read_file`, `write_file`, `list_files` | All roles |
| **Review** | `create_review_comment`, `approve_change`, `request_changes` | Reviewer only |

`write_file` is intercepted — on every write, the MCP Hub: (1) checks role domain, (2) generates a file summary via `claude-haiku-4-5`, (3) publishes a `file_updated` event to Redis, (4) writes to the audit log.

---

## Data flows

### Contract + signal (the stand-up that never happens)

```
Agent A calls wait_for_signal("user-api", timeout=600)
→ MCP Hub subscribes to Redis: signals:{project_id}:user-api
→ Agent A's turn is held open (SSE connection stays alive)

Agent B finishes the user API:
→ calls publish_context({ type: "contract", id: "user-api-v1", ... })
  → stored in Postgres contracts table
  → briefing cache invalidated in Redis
→ calls signal_ready("user-api")
  → Redis publishes to signals:{project_id}:user-api
  → signal persisted to Postgres signals table
  → Agent A's wait_for_signal resolves with the contract payload

Agent A receives the contract and builds against the real API shape.
The "is the API ready?" message never gets sent.
```

### Conflict detection and resolution

```
Two agents write to the same file within a short window:
→ MCP Hub detects via Redis key: active_write:{project_id}:{path}
→ raise_resolution called automatically:
    { title, conflict_a, conflict_b, affects }
→ Both agents' pending writes paused (Redis lock held)
→ Resolution card posted to Postgres resolutions table + Redis open_resolutions set
→ Dashboard shows card to both engineers via SSE

Engineers decide (in 60 seconds — they're both working right now):
→ PUT /project/{id}/resolutions/{resolution_id}
    { decision: "postgres", record_adr: true }
→ ADR created in Postgres, added to shared context
→ Paused agents' next turns include the ADR in their briefing
→ They align automatically, no further human action
```

### Briefing assembly (every agent turn)

```
Claude Code: GET /mcp/resources
→ Server: [{ uri: "backyard://briefing", ... }]
Claude Code: GET /mcp/resources/backyard://briefing
→ Server assembles:
    get_active_sessions()     → Redis HGETALL sessions:{project_id}
    get_recent_activity()     → Postgres latest compressed activity bullets
    get_contracts()           → Postgres all contracts, summaries only
    get_open_decisions()      → Postgres unresolved resolution cards
    format + count tokens → trim if > 2000 tokens
→ Returns briefing text
→ Claude Code includes it in the agent context on every turn
```

---

## Storage

| Store | What lives there | Why |
|---|---|---|
| **Redis** | Active sessions, signals (pub/sub channels), hot briefing cache (TTL: 30s), contract summaries cache (TTL: 60s), open resolution IDs, write-lock keys (TTL: 30s) | Sub-millisecond reads; pub/sub for real-time fan-out; TTLs for automatic cleanup |
| **Postgres** | Contracts, ADRs, file summaries, signals (persistence), resolutions, activity log, audit log, engineers, projects, API tokens | Durable; relational model fits the structured artifact store; append-only audit log |

No vector database. All context queries are structured (by type, role, file path, contract ID) — faster, cheaper, and never stale within an active session. Semantic search across sessions is a Phase 2 concern.

---

## Role domain enforcement

Domain checks run in the MCP Hub before every `write_file` call:

```python
def check_domain(role: str, path: str) -> DomainResult:
    role_domains = get_role_domains(role)
    if any(pathspec.match_file(domain, path) for domain in role_domains):
        return DomainResult.ALLOWED
    return DomainResult.NEEDS_PROPOSAL
```

`NEEDS_PROPOSAL` does not block the agent. The MCP Hub automatically calls `propose_cross_domain_edit`, which posts a request to the owning engineer on the dashboard. The write is queued until they approve. This keeps collaboration open without letting agents step on each other silently.

| Role | Default domain (pathspec patterns) |
|---|---|
| `frontend` | `ui/**` `components/**` `styles/**` `pages/**` `*.css` `*.tsx` `*.jsx` |
| `backend` | `api/**` `services/**` `db/**` `middleware/**` |
| `devops` | `infra/**` `*.yml` `Dockerfile` `.github/**` `scripts/**` |
| `reviewer` | read-everywhere (writes only via proposals) |

Custom roles can be defined in `backyard.toml` at the project root.

---

## Tech stack

| Layer | Technology |
|---|---|
| Server | FastAPI + uvicorn |
| Protocol | `mcp` (official Python MCP SDK) |
| Async | asyncio |
| Hot state / signals | `redis.asyncio` |
| Durable store | Postgres 16 + SQLAlchemy 2 (async) + Alembic |
| Internal AI calls | `anthropic` Python SDK (`claude-haiku-4-5`) |
| Auth | API tokens + bcrypt |
| Dashboard | Vanilla HTML/JS + FastAPI static files, SSE for live updates |
| Tests | pytest + pytest-asyncio + fakeredis |
| Dev infra | docker-compose (Redis + Postgres) |
| Packaging | uv + pyproject.toml |
| Linting / types | ruff + mypy (strict) |

See [§12 of the technical report](technical-report.md#12-tech-stack) for the full rationale behind each choice.
