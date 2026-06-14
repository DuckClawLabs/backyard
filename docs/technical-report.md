# Backyard — Technical Report

**Multi-Agent Coordination for Enterprise Engineering Teams**
Companion to the white paper *The Unbuilt Product* (M. Reddy, June 2026).
Version 0.5 · Stack: Python · Target: Enterprise

---

## Overview

Backyard is a team coordination layer that wraps Claude Code for enterprise engineering teams.
Each engineer connects their existing Claude Code to one shared project — their agent has full shared
context of what every other agent on the team is doing, in real time.

This report covers two distinct problems:

- **[Part A — Problem 1: MCP Coordination](#part-a--problem-1-mcp-coordination)** ← *building now*
- **[Part B — Problem 2: Live Collaboration](#part-b--problem-2-live-collaboration)** ← *future vision*

We build Problem 1 first. It is real, achievable, and has no direct competitors today.
Problem 1 earns us the right — and the revenue — to build Problem 2.

---

# Part A — Problem 1: MCP Coordination

## A1. The Problem

Every team using Claude Code today has this problem. Each agent knows only what its own engineer has
told it. There is no shared state between agent sessions.

- Agent A writes an integration for an API that Agent B hasn't shipped yet — wrong assumptions, baked in silently
- Agent B makes a breaking change — Agent A's agent doesn't know for hours
- Two agents make contradictory architecture decisions independently — discovered at PR review, not before
- Agent A needs to know if the auth middleware is ready — only a Slack message can answer it, not an agent

You can put shared context in a `CLAUDE.md` file. But it is manual, asynchronous, and agents don't get
notified when it changes. No tool solves this today.

## A2. The Solution

An **MCP coordination server** every engineer's Claude Code connects to with one line of config —
giving every agent on the team a **shared brain**.

```json
// .claude/settings.json  (one-time setup per engineer)
{
  "mcpServers": {
    "backyard": { "url": "https://backyard.yourcompany.com/project/abc" }
  }
}
```

Engineers keep using whichever Claude Code surface they already use — CLI, desktop app, VS Code
extension, or web. Nothing changes in their workflow. Backyard is invisible infrastructure that makes
their agents smarter about the team they're part of.

## A3. System Architecture

```
                    ┌──────────── BACKYARD MCP SERVER ────────────┐
                    │          (Python · FastAPI · asyncio)        │
                    │                                              │
                    │  ① MCP Hub          ② Shared Context Store  │
                    │  ③ Signal Engine    ④ Project Briefing       │
                    │  ⑤ Audit Log        ⑥ Conflict Surface       │
                    └──────────────────────────────────────────────┘
                         ▲              ▲               ▲
                         │   MCP        │               │  MCP
                 ┌───────┴──────┐  ┌────┴───────┐  ┌───┴────────┐
                 │  Engineer A  │  │ Engineer B │  │ Engineer C │
                 │  Claude Code │  │ Claude Code│  │ Claude Code│
                 │  (any surface│  │(any surface│  │(any surface│
                 └──────────────┘  └────────────┘  └────────────┘

                    Redis (pub/sub, signals, hot state)
                    Postgres (context, audit log)
```

### Components

| # | Component | Responsibility |
|---|---|---|
| ① | **MCP Hub** | The MCP server interface. Exposes standard file tools and all team-coordination tools to every connected agent. |
| ② | **Shared Context Store** | Contracts, ADRs, file summaries. Structured artifacts agents publish and query. Never raw conversation history. |
| ③ | **Signal Engine** | Redis pub/sub. `signal_ready` / `wait_for_signal` let agents coordinate without human intermediation. |
| ④ | **Project Briefing** | Auto-injected into every agent turn (≤2k tokens): who's active, recent activity, published contracts, open decisions. |
| ⑤ | **Audit Log** | Every agent action logged: `(engineer, role, agent-turn, timestamp, tool, result)`. Always on. Postgres. |
| ⑥ | **Conflict Surface** | Detects contradictory agent decisions; posts a resolution card to the involved engineers via the web dashboard. |

## A4. MCP Tool Catalog

| Group | Tools | Purpose |
|---|---|---|
| **Context** | `query_shared_context` | Search contracts, ADRs, file summaries |
| | `publish_context` | Publish a contract, ADR, or decision |
| | `get_file_summary` | Get the auto-generated summary of any file |
| | `get_project_status` | Active engineers, recent activity, open decisions |
| **Signals** | `signal_ready(topic)` | Broadcast that a milestone is complete |
| | `wait_for_signal(topic, timeout)` | Block until another agent signals; resolves with the published contract |
| **Coordination** | `propose_cross_domain_edit` | Request permission to touch another role's domain |
| | `raise_resolution` | Surface a conflict or contradictory instruction to the engineers |
| | `request_clarification` | Ask another role's engineer a question via the dashboard |
| **File tools** | `read_file`, `write_file`, `list_files` | Standard file access (pass-through; agents still write to their local filesystem in Problem 1) |
| **Review** | `create_review_comment`, `approve_change` | Reviewer role only |

## A5. Key Data Flows

### A5.1 Shared contract — the stand-up that never happens

```
Agent A: wait_for_signal("user-api", timeout=300s)     ← no human action required

Agent B implements the endpoint, then:
  publish_context({ type: "contract", id: "user-api-v1",
                    endpoints: [GET /api/users/:id → UserDTO] })
  signal_ready("user-api")

→ Signal Engine resolves Agent A's wait
→ Agent A receives the typed contract
→ Agent A builds against the real shape immediately
→ The "is the API ready?" Slack message never gets sent
```

### A5.2 Contradictory decisions — surfaced, not silently picked

```
Engineer A tells their agent: "use Postgres"
Engineer B tells their agent: "use SQLite"

→ Both agents detect the contradiction and call raise_resolution()
→ Conflict Surface posts a resolution card to the web dashboard:
      "Database choice — A: Postgres, B: SQLite. Engineers: decide together."
→ Engineers resolve in the open; decision recorded as an ADR
→ ADR is published to the Shared Context Store
→ Both agents' subsequent turns include the decision in their briefing
→ No agent proceeds until the decision is made
```

### A5.3 Project briefing — injected every turn

```
=== PROJECT BRIEFING (auto-generated) ===
Session: 47m active · Engineers: Frontend(A), Backend(B), Reviewer(C)
Recent:  B published user-api-v1 (GET /api/users/:id)
         A completed UserCard component
Contracts available: user-api-v1
Open decisions: none
=== END ===
```

Constant situational awareness. Bounded cost (≤2k tokens). Every agent knows the state of the team
without sharing raw conversation histories.

## A6. Shared Context Architecture

Agents in different sessions never share conversation history — that would explode context windows and
cost. They share **structured artifacts** only:

| Artifact | Schema | Published by | Consumed by |
|---|---|---|---|
| **Interface Contract** | `{id, endpoints[], types{}}` | Producing role | All other roles |
| **Architecture Decision (ADR)** | `{title, status, affects[], summary}` | Any (after engineer approval) | All agents |
| **File Summary** | `{path, summary, exports[], last_by}` | Auto-generated on write | Any agent querying a file |
| **Compressed Activity** | Bullet-point summary of recent turns | Auto-generated every ~10 turns | Project briefing |

Storage: **Redis** (hot: signals, briefings, pub/sub) + **Postgres** (durable: contracts, ADRs,
summaries, audit). No vector database — all queries are structured (by role/path/contract ID), which is
faster, cheaper, and never stale.

## A7. Role System

Roles set default domains and route work. They are hints, not hard walls — helping outside your domain
just asks first, visibly.

| Role | Default domain | Asks-first to touch |
|---|---|---|
| **Frontend** | `ui/**`, `components/**`, `styles/**`, `pages/**` | backend / infra |
| **Backend** | `api/**`, `services/**`, `db/**`, `middleware/**` | ui / infra |
| **DevOps** | `infra/**`, `*.yml`, `Dockerfile`, `.github/**` | app code |
| **Reviewer** | read-everywhere; edits via proposal | — |

Custom roles defined in `backyard.toml` per project. Enforcement at the MCP Hub before any tool
executes.

## A8. Trust and Conflict Model

**System floor (non-negotiable):** no file access outside the project workspace; no direct push to
`main`/`master`; a session cannot read another session's private context; irreversible operations
require a surfaced decision.

**Above the floor:** contradictory decisions → agents stop and surface via `raise_resolution` → both
engineers see a resolution card → they decide together → decision logged and published as an ADR.
Agent default under conflict: **stop and surface, never guess and proceed.**

## A9. Tech Stack

| Concern | Choice | Rationale |
|---|---|---|
| Server | **FastAPI + uvicorn** | Async, native WebSocket, Pydantic-validated schemas |
| MCP interface | **`mcp`** (official Python SDK) | Claude-native; works with any Claude Code surface |
| Concurrency | **asyncio** | Single event loop; natural signal serialization |
| Signals / pub-sub | **`redis.asyncio`** | Sub-ms pub/sub; signal delivery; hot state |
| Durable store | **Postgres 16 + SQLAlchemy 2 (async) + Alembic** | Contracts, ADRs, audit log |
| Briefing generation | **`anthropic`** Python SDK | Compress activity log every ~10 turns |
| Path safety | **`pathspec`** / `os.path.realpath` | Block traversal at the MCP Hub |
| Dashboard | **Vanilla HTML/JS** served by FastAPI | Presence, conflict cards, audit log — no framework needed |
| Tests | **pytest + pytest-asyncio + fakeredis** | Signal engine and context store correctness first |
| Dev infra | **docker-compose** (redis + postgres) | One-command local stack |

**No custom client.** Engineers use their existing Claude Code setup.

## A10. Repository Layout (Problem 1)

```
backyard/
├── docs/
│   ├── technical-report.md     # this document
│   ├── architecture.md         # component + data-flow reference
│   └── roadmap.md              # phased plan
├── src/backyard/
│   ├── server/
│   │   ├── app.py              # FastAPI entry: MCP endpoint + dashboard routes
│   │   ├── project_registry.py # project ⇄ session mapping
│   │   ├── mcp_hub/
│   │   │   ├── server.py       # MCP server instance per session
│   │   │   ├── context_tools.py   # query/publish context, file summaries
│   │   │   ├── signal_tools.py    # signal_ready, wait_for_signal
│   │   │   └── coord_tools.py     # raise_resolution, propose_cross_domain_edit
│   │   ├── context/
│   │   │   ├── store.py        # Postgres-backed context store
│   │   │   ├── briefing.py     # project briefing assembly + compression
│   │   │   └── models.py       # Contract, ADR, FileSummary Pydantic models
│   │   ├── signals/
│   │   │   └── engine.py       # Redis pub/sub signal engine
│   │   ├── audit/
│   │   │   └── log.py          # audit log writer + query
│   │   ├── conflicts/
│   │   │   └── surface.py      # contradiction detection + resolution card
│   │   └── roles/
│   │       └── definitions.py  # role configs, domain patterns, capabilities
│   ├── protocol/               # Pydantic event/message models
│   └── dashboard/              # static single-page web app
│       ├── index.html          # presence, conflict cards, audit log
│       └── static/
├── tests/
│   ├── test_signals.py         # signal engine correctness
│   ├── test_context_store.py   # context store queries
│   └── test_briefing.py        # briefing assembly + token budget
├── infra/docker-compose.yml
├── pyproject.toml
└── README.md
```

**Build order:** `protocol` → `signals/engine` (tested in isolation) → `context/store` →
`mcp_hub/context_tools` → `mcp_hub/signal_tools` → `briefing` → `mcp_hub/coord_tools` →
`conflicts/surface` → `dashboard`. Signals and context store are the core correctness surfaces and
come first.

## A11. Enterprise Roadmap (Problem 1)

### Phase 1A — Core coordination server
MCP server, shared context store, signal engine, project briefing, audit log. Engineers connect with
one line of config. Target: an internal pilot with a real enterprise engineering team.

**Pilot experiment:** two engineers use Backyard for one sprint. Does coordination overhead fall vs.
their current workflow? Does the "is the API ready?" message disappear? The Engineering Manager's
subjective answer — "would you run the next sprint this way?" — matters as much as the time measurement.

### Phase 1B — Visibility and enterprise controls
Web dashboard (presence, activity feed, conflict cards), SSO/SAML, org-wide admin, compliance audit
exports. Required for enterprise procurement.

### Phase 1C — Enterprise hardening
Private/on-premise deployment, SOC 2 Type II, SCIM provisioning, CI/CD integration. Required for
financial services, healthcare, and defense customers.

## A12. Revenue Model (Problem 1)

Enterprise B2B only. No individual or free tier. The buyer is an organization.

| Tier | Price | Includes |
|---|---|---|
| **Team** | ~$75/seat/mo, annual | Unlimited projects, all roles, dashboard, audit log, CI hooks |
| **Enterprise** | ~$150/seat/mo, annual | Team + SSO/SAML, SCIM, SOC 2 reports, private-cloud deployment, SLA |
| **Enterprise+** | Custom contract | Enterprise + on-premise, custom retention policy, professional services |

Charge for the coordination layer. Pass model tokens through at cost, shown per engineer.

## A13. Five Fatal Risks → Mitigations (Problem 1)

| # | Risk | Mitigation |
|---|---|---|
| **I** | Coordination overhead rises instead of falling | Pilot experiment measures it directly; project briefing + signals delete the stand-up. Kill if overhead doesn't fall. |
| **II** | Context store becomes stale or noisy | Structured queries only (no vector search); auto-generated file summaries on every write; compressed activity log every ~10 turns. |
| **III** | Agents make wrong decisions from bad shared context | ADR system records decisions durably; agents cannot proceed past a `raise_resolution` until engineers decide. |
| **IV** | Enterprise won't adopt without compliance features | Audit log from day one; SSO + compliance exports in Phase 1B; private deployment in Phase 1C. |
| **V** | No revenue without individual tier | By design: enterprise-only from the start. Pilot is the top-of-funnel, not a free tier. |

---

# Part B — Problem 2: Live Collaboration

## B1. The Problem

The pull-request model was designed for humans working in isolation, asynchronously. AI agents
inherited it unquestioned. Even with Problem 1 solved — even with perfect shared context and real-time
signals — engineers still work on separate local codebases and merge through PRs.

The gap that remains: **there is no way for multiple engineers to contribute to one live codebase
simultaneously.** Every edit still goes through a branch, a PR, a review cycle, a merge. The agent
accelerates the individual edit; it does not eliminate the merge step.

## B2. The Vision

Each engineer logs into a shared project and gets their own **background AI agent**. All engineers edit
**one live shared codebase at the same time**. Every agent's edits appear live for the whole team.
Conflicts surface to the engineers involved. No pull requests. No merge step. No waiting.

```
                    ┌──────── ONE LIVE PROJECT ────────┐
                    │       (shared codebase, CRDT)    │
                    └──────────────────────────────────┘
                       ▲           ▲           ▲
                 Session A    Session B    Session C
             (engineer + background agent, private chat)
```

## B3. What Makes This Hard (Honest Assessment)

**1. Workspace ownership.** Claude Code writes to the local filesystem. To share edits in real time,
the code cannot live on each engineer's laptop — it must live on shared infrastructure. This requires
Backyard to provision **cloud workspaces** (containers) per engineer. That is a platform company, not
just a tool.

**2. Real-time file sync.** A CRDT (`pycrdt`, Yrs/Yjs-compatible) can sync a shared document across
sessions without a merge step. But applying this to a directory tree of source files — handling
renames, deletions, binary files — is more engineering than it appears.

**3. Background autonomous agents.** Claude Code is interactive: an engineer types, the agent responds,
the engineer approves. A "background agent" that works autonomously requires a separate server-side
agent loop — not a Claude Code wrapper, but an independent process running against the Anthropic API
per engineer per project.

**4. Semantic conflict detection.** A CRDT guarantees text convergence but not code correctness. Two
cleanly-merged edits can produce a file that won't compile or is logically contradictory. Detecting
this requires real-time AST parsing and cross-session intent comparison. This is a research-level
problem for the general case. The MVP can detect parse failures; true semantic detection is a
12–18 month engineering investment.

## B4. Architecture (when built)

| Component | What it does |
|---|---|
| **Cloud Workspace Service** | Provisions a container per engineer; all containers share the project codebase |
| **Live Sync Engine (CRDT)** | `pycrdt` document per project; every edit converges on all sessions, lossless, no merge step |
| **Background Agent Loop** | Server-side agent process per session; runs autonomously; edits applied as CRDT updates |
| **Semantic Conflict Watcher** | AST-aware: detects broken or contradictory converged code; freezes the region; surfaces to engineers |
| **Full Web IDE** | Monaco editor + Yjs WebSocket client; live cursors; the Yjs protocol is wire-compatible with `pycrdt` |

## B5. Why Problem 1 Comes First

- Problem 1 is real, achievable now, and has zero direct competitors today
- Problem 1 can ship to enterprise teams already using Claude Code — this month
- Problem 1 validates the market before any cloud infrastructure is committed to
- The team that wins Problem 1 has the relationships, trust, and revenue to fund Problem 2
- Problem 2 without Problem 1 is building a platform before proving the pain

**Build the shared brain first. Then build the shared workspace.**

---

## References

- M. Reddy, *The Unbuilt Product*, white paper, June 2026.
- Model Context Protocol — specification and Python SDK (`mcp`).
- Yjs / Yrs — CRDT framework; `pycrdt` Python bindings.
- Anthropic, *Claude Code Agent Teams* — multi-agent coordination (2026).
