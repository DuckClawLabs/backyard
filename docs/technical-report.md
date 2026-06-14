# Backyard — Technical Report

**MCP Coordination Server for Enterprise Engineering Teams**
*The Unbuilt Product* companion document · M. Reddy, June 2026
Version 1.0 · Stack: Python · Status: Design → Build

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Problem](#2-the-problem)
3. [The Solution](#3-the-solution)
   - [3.4 Feature Walkthroughs](#34-feature-walkthroughs)
4. [System Architecture](#4-system-architecture)
5. [Component Designs](#5-component-designs)
6. [MCP Tool Specifications](#6-mcp-tool-specifications)
7. [Key Data Flows](#7-key-data-flows)
8. [Data Model](#8-data-model)
9. [Authentication & Project Setup](#9-authentication--project-setup)
10. [Role System](#10-role-system)
11. [Trust & Conflict Model](#11-trust--conflict-model)
12. [Tech Stack](#12-tech-stack)
13. [Repository Layout](#13-repository-layout)
14. [Implementation Plan](#14-implementation-plan)
15. [Pilot Experiment](#15-pilot-experiment)
16. [Enterprise Fit](#16-enterprise-fit)
17. [Revenue Model](#17-revenue-model)
18. [Risk Register](#18-risk-register)

---

## 1. Executive Summary

Enterprise engineering teams using Claude Code today have a fundamental coordination gap: **every
agent session is completely isolated.** Agent A does not know what Agent B is building. The agents
cannot signal each other. Contradictory decisions go undetected until PR review. Every inter-agent
dependency requires a human to transmit context manually — via Slack, a stand-up, or a CLAUDE.md
file nobody keeps current.

**Backyard solves this with a single MCP server** that every engineer's Claude Code connects to with
one line of config. The server gives every agent on the team:

- A **shared context store** — contracts, architecture decisions, file summaries — always current
- **Real-time signals** — Agent B publishes the API; Agent A's pending wait resolves automatically
- A **project briefing** — auto-injected into every agent turn: who's active, what's published,
  what decisions are open
- A **conflict surface** — when two agents make contradictory decisions, both engineers see a
  resolution card immediately
- A **full audit log** — every agent action recorded from day one for enterprise compliance

Engineers keep using Claude Code exactly as they do today. Backyard is invisible infrastructure.

**The one question the pilot must answer:** does shared agent context meaningfully reduce coordination
overhead for an enterprise engineering team? If yes, Problem 1 is the product. If no, we stop at a
pilot and write up what we learned.

---

## 2. The Problem

### 2.1 What is broken

Every team using Claude Code at scale hits the same wall. Each agent knows only what its own engineer
has told it. Between sessions, there is no shared state, no signal channel, no awareness of what
other agents on the team are building.

**Example A — Wrong API assumptions:**
Engineer A asks their agent to build a frontend component that calls the user profile API. Engineer B's
agent is building that API at the same time. Agent A has to guess the API shape — and guesses wrong.
Agent B makes a breaking change two days later. Agent A's component breaks. Neither agent knew.

**Example B — Duplicate work:**
Two agents independently decide to add a caching layer to the same service. Both implement it, with
different strategies. The conflict is discovered at PR review. Both engineers lose a day.

**Example C — Contradictory architecture decisions:**
Engineer A tells their agent to use Postgres for the new feature. Engineer B tells their agent to use
SQLite. Both agents proceed. Two weeks later, two inconsistent database connections exist in the
codebase. Neither engineer intended this.

**Example D — Coordination via Slack:**
Engineer A needs to know if the auth middleware is ready before their agent can proceed. The only way
to find out: send a Slack message and wait. The agent cannot query another session. So Agent A either
blocks or proceeds on assumptions.

### 2.2 Why CLAUDE.md is not the answer

`CLAUDE.md` is a static file committed to the repo. It was designed to give a single agent project
context — stack decisions, conventions, instructions. It is not a coordination mechanism for teams:

| Limitation | Why it matters |
|---|---|
| **Static** | Agents update CLAUDE.md manually; it falls behind within hours of active work |
| **Asynchronous** | No agent is notified when another agent updates it |
| **Unstructured** | Free text; agents cannot query "what contracts has the backend published?" |
| **Single-file** | One file per repo; no per-project, per-team, or per-session scoping |
| **No signals** | Cannot block an agent until a dependency is ready |

### 2.3 The real cost

This is not a productivity inconvenience. For a 20-engineer team running 20 agent sessions in
parallel, the coordination overhead is:
- ~2 hours/day/engineer on synchronization that should be automatic
- PR reviews that catch problems agents could have surfaced in real time
- Architecture drift that compounds over weeks when decisions are not shared

Fixing this with better Slack discipline or more frequent stand-ups scales the human cost as the
team grows. Backyard makes the coordination automatic.

---

## 3. The Solution

### 3.1 One line of config

```json
// .claude/settings.json  (one-time addition per engineer)
{
  "mcpServers": {
    "backyard": { "url": "https://backyard.yourcompany.com/project/abc123" }
  }
}
```

This works from any Claude Code surface: CLI, desktop app, VS Code extension, web. No new tool to
install. No workflow change. The engineer keeps using Claude Code exactly as before — but their agent
now has a shared brain.

### 3.2 What engineers actually do (onboarding)

1. **Admin creates a project** on the Backyard dashboard
   → gets a project URL like `https://backyard.yourcompany.com/project/abc123`
2. **Engineers add one line** to their `.claude/settings.json`
3. **Each engineer assigns themselves a role** (Frontend, Backend, DevOps, Reviewer) on the dashboard
   → this sets their agent's default domain and what it can do without asking
4. **Done.** Their next Claude Code session connects to Backyard automatically

### 3.3 What the agents get

From the moment an engineer's Claude Code connects, their agent has access to:

- Everything in the **shared context store** — contracts already published by other roles, ADRs
  already recorded, file summaries of the files teammates have been working on
- The **project briefing** — injected automatically at the start of every agent turn, no prompt
  engineering required from the engineer
- The **signal channel** — `wait_for_signal` and `signal_ready` work across all sessions on the
  project
- The **conflict surface** — contradictory instructions are flagged immediately, not at PR review

### 3.4 Feature walkthroughs

#### The stand-up that never happens

Agent B finishes implementing the user API. Instead of someone sending a Slack message to say "the
API is ready", Agent B's agent publishes the contract and signals:

```
publish_context({ type: "contract", id: "user-api-v1",
                  endpoints: [GET /api/users/:id → UserDTO {id, email, displayName}] })

signal_ready("user-api")
```

Agent A was waiting:

```
wait_for_signal("user-api")
→ resolves immediately with the contract payload
→ Agent A calls query_shared_context({ type: "contract", id: "user-api-v1" })
→ Agent A receives the full contract
→ Agent A builds against the real API shape
```

The "is the API ready?" Slack message never gets sent. The stand-up item never gets added. Both
agents proceed without any human acting as a messenger. See §7.1 for the full step-by-step flow.

---

#### The project briefing — every agent knows the state of the team

At the start of every agent turn, before the engineer says anything, the briefing is injected
automatically:

```
=== PROJECT BRIEFING ===
Project: Acme Payments Service · Your role: Backend · Session time: 47m
Active now: Frontend (Alice), Backend (you), Reviewer (Carol)

Recent activity:
· Frontend (Alice): completed UserCard component, calls GET /api/users/:id
· Backend (you): implemented GET /api/users/:id, published contract user-api-v1

Contracts published:
· user-api-v1 — GET /api/users/:id → UserDTO {id, email, displayName}
  (published by Backend, 12m ago)

Architecture decisions:
· ADR-001: Use Postgres for all persistent storage (decided by Alice + Bob, 2h ago)

Open decisions: none
=== END BRIEFING ===
```

No prompt engineering required. No engineer has to tell their agent what teammates are doing. The
briefing is assembled fresh every turn from Redis (active sessions) and Postgres (contracts, ADRs,
recent activity), kept under 2 000 tokens, and injected as an MCP resource automatically. See §5.4
for the assembly algorithm.

---

#### The conflict surface — contradictions caught before they ship

Two engineers give their agents contradictory instructions. Both agents call `raise_resolution`.
Both engineers immediately see a resolution card on the dashboard:

```
┌─────────────────────────────────────────────────────────┐
│  CONFLICT — Database technology choice                  │
│                                                         │
│  Engineer A (Frontend) said: "use Postgres"             │
│  Engineer B (Backend) said:  "use SQLite"               │
│                                                         │
│  Affected: db/**, infra/docker-compose.yml              │
│                                                         │
│  [Choose Postgres]  [Choose SQLite]  [Discuss first]    │
│                                                         │
│  Record this decision as an ADR? [Yes] [No]             │
└─────────────────────────────────────────────────────────┘
```

Both agents are paused — they do not race ahead, they do not guess which instruction takes priority.
The engineers decide together in 60 seconds because they are working at the same time. If they
choose "Record as ADR", the decision is added to every subsequent briefing and no agent can
contradict it without triggering another resolution card. See §5.6 and §7.2 for full detail.

---

#### The role system — agents know their domain

Each engineer sets a role in `.backyard-mcp/me.yaml`. The role sets the agent's default domain
(the files it can write without asking) and which coordination tools it has access to.

If an agent needs to write a file outside its domain — say, the Frontend agent needs to update an
API response format — the MCP Hub automatically calls `propose_cross_domain_edit`. The Backend
engineer sees the request on the dashboard and approves or redirects it. The agent does not just
get blocked; it asks, visibly, and the work continues after a fast approval.

---

#### The audit log — from session one

Every agent action is logged to Postgres: tool name, arguments, result summary, latency, and a
row-level checksum. The audit log is always on, append-only, and cannot be disabled. Engineers see
their own activity in the dashboard. Engineering managers see the team's activity. Admins can
export the full log as CSV or JSON.

This is not a Phase 3 compliance feature. It is on from the first commit, because enterprise
procurement requires it before a team can put Backyard on a codebase that matters.

---

## 4. System Architecture

### 4.1 System diagram

```
                    ┌──────────────────────────────────────────────┐
                    │            BACKYARD MCP SERVER               │
                    │          (Python · FastAPI · asyncio)        │
                    │                                              │
                    │   ┌──────────────┐  ┌───────────────────┐   │
                    │   │  ① MCP Hub   │  │ ② Shared Context  │   │
                    │   │  (per session│  │    Store          │   │
                    │   │   MCP server)│  │  (Postgres + Redis│   │
                    │   └──────────────┘  └───────────────────┘   │
                    │                                              │
                    │   ┌──────────────┐  ┌───────────────────┐   │
                    │   │ ③ Signal     │  │ ④ Project         │   │
                    │   │   Engine     │  │   Briefing        │   │
                    │   │  (Redis p/s) │  │  (assembled per   │   │
                    │   └──────────────┘  │   agent turn)     │   │
                    │                     └───────────────────┘   │
                    │   ┌──────────────┐  ┌───────────────────┐   │
                    │   │ ⑤ Audit Log  │  │ ⑥ Conflict        │   │
                    │   │  (Postgres)  │  │   Surface         │   │
                    │   └──────────────┘  └───────────────────┘   │
                    │                                              │
                    │   ┌──────────────────────────────────────┐  │
                    │   │  ⑦ Web Dashboard (FastAPI + static)  │  │
                    │   └──────────────────────────────────────┘  │
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
                  │  Redis 7      Postgres 16              │
                  │  pub/sub      contracts · ADRs         │
                  │  signals      file summaries           │
                  │  hot state    audit log                │
                  │  briefing     project config           │
                  └───────────────────────────────────────┘
```

### 4.2 Connection lifecycle

When an engineer's Claude Code starts a session:

1. Claude Code reads `.claude/settings.json` → finds the `backyard` MCP server URL
2. Claude Code opens an **SSE (Server-Sent Events) connection** to
   `GET /project/{id}/mcp` with the engineer's API token in the `Authorization` header
3. The MCP Hub authenticates the token → looks up the engineer's role for this project
4. The MCP Hub registers the session → `sessions:{project_id}` set in Redis gains a new entry
5. The MCP Hub sends the tool list to Claude Code (the full MCP tool catalog for this role)
6. On the first agent turn, the briefing is injected automatically via the MCP `resources` endpoint

On disconnect: session entry removed from Redis; hot state cleaned up; audit log entry written.

### 4.3 Component summary

| # | Component | Core job |
|---|---|---|
| ① | **MCP Hub** | The MCP server. Authenticates engineers, routes tool calls, enforces role policies, injects the project briefing. One logical instance per project; one MCP connection per engineer session. |
| ② | **Shared Context Store** | Structured store of contracts, ADRs, and file summaries. Postgres for durability; Redis for hot reads. Agents query and publish through the MCP Hub. |
| ③ | **Signal Engine** | Redis pub/sub. `signal_ready(topic)` broadcasts; `wait_for_signal(topic)` blocks until the signal arrives. Works across all sessions on the project. |
| ④ | **Project Briefing** | Assembled fresh at the start of each agent turn: who is active, what was published recently, what contracts exist, what decisions are open. ≤2 000 tokens. Injected as an MCP resource. |
| ⑤ | **Audit Log** | Every tool call from every agent written to Postgres: `(project_id, engineer_id, role, session_id, turn_id, timestamp, tool_name, arguments, result_summary)`. Always on, cannot be disabled. |
| ⑥ | **Conflict Surface** | Watches for contradictory decisions across sessions. When detected, posts a resolution card to the web dashboard, pauses the relevant agents, and waits for engineers to resolve. |
| ⑦ | **Web Dashboard** | Single-page app served by FastAPI. Shows: who is active, recent agent activity, published contracts, open decisions, audit log viewer. Engineers resolve conflict cards here. |

---

## 5. Component Designs

### 5.1 MCP Hub

The MCP Hub is the entry point for all agent interactions. It is a FastAPI application that speaks
the Model Context Protocol (MCP) over HTTP/SSE.

**What it does per tool call:**
1. Verify session token (cached in Redis after initial auth)
2. Check role policy against the requested tool (`roles/definitions.py`)
3. Route to the appropriate internal service (context store, signal engine, etc.)
4. Write the call to the audit log
5. Return the result

**Briefing injection:**
MCP provides a `resources/list` endpoint that Claude Code calls at the start of each turn. The MCP
Hub returns one resource: `backyard://briefing`. Claude Code fetches it and includes it in the
agent's context. This requires zero prompt engineering from the engineer — it is automatic.

**Role enforcement:**
Every tool call is checked against the role policy before execution:
- Context tools: available to all roles
- Signal tools: available to all roles
- `propose_cross_domain_edit`: triggered automatically when a write targets a path outside the role's domain
- `create_review_comment`, `approve_change`: Reviewer role only
- All other coordination tools: all roles

### 5.2 Shared Context Store

The context store holds structured artifacts — the things agents need to know about each other, in a
form they can query precisely.

**Artifact types:**

| Type | What it is | Schema |
|---|---|---|
| `contract` | An API or module interface published by one role and consumed by others | `{id, project_id, published_by_role, version, endpoints[], types{}, description, created_at}` |
| `adr` | An architecture decision recorded after engineers resolve a conflict | `{id, project_id, title, status, affects[], decision, rationale, decided_by[], created_at}` |
| `file_summary` | 2–3 sentence auto-generated summary of a file, regenerated on every write | `{path, project_id, summary, exports[], last_modified_by, last_modified_at, clock}` |
| `activity` | Compressed bullet-point log of recent agent activity | `{project_id, period_start, period_end, bullets[], generated_at}` |

**How file summaries work:**
When an agent writes a file via the `write_file` tool, the MCP Hub:
1. Applies the write (pass-through to the local filesystem via the MCP tool)
2. Sends the new file content to the Anthropic API with a prompt: "Summarize this file in 2–3
   sentences. List its exported functions, classes, or types."
3. Stores the result as a `file_summary` artifact in Postgres, keyed by path
4. Publishes a `file_updated:{project_id}:{path}` event to Redis

Other engineers' agents can now call `get_file_summary(path)` and get an accurate, current summary
without reading the file at all.

**Compression:**
Every ~10 agent turns (tracked per project), a background task runs:
1. Fetches the last 10 audit log entries for this project
2. Sends them to the Anthropic API: "Summarize this activity in 5 bullet points."
3. Stores the result as an `activity` artifact
4. The next briefing uses the compressed bullets instead of raw log entries

This keeps the briefing token budget bounded regardless of how long a project runs.

### 5.3 Signal Engine

The signal engine is a thin Redis pub/sub layer that lets agents coordinate across sessions without
human intermediation.

**Signal lifecycle:**

```
Agent B calls signal_ready("user-api"):
  → publish to Redis channel: signals:{project_id}:user-api
  → store signal in Postgres: {project_id, topic, published_by, payload, created_at}
  → all waiting listeners on this channel receive the message

Agent A called wait_for_signal("user-api", timeout=300) earlier:
  → the MCP Hub subscribed to Redis channel: signals:{project_id}:user-api
  → on message received: resolve the pending MCP call with the signal payload
  → if timeout exceeded before signal: return {timed_out: true}
```

**Implementation detail — asyncio + Redis:**
Each `wait_for_signal` call is an async operation. The MCP Hub holds the MCP connection open (SSE
keeps it alive). The async event loop awaits the Redis subscription. When the signal arrives, the
coroutine resumes and returns the result to Claude Code.

**Persistent signals:**
If Agent B publishes `signal_ready("user-api")` and Agent A is not yet waiting, the signal is
persisted in Postgres. When Agent A later calls `wait_for_signal("user-api")`, the MCP Hub checks
Postgres first — if a signal for this topic already exists, it returns immediately without waiting.
Signals do not expire during an active project session.

### 5.4 Project Briefing

The briefing is the primary mechanism by which agents know the state of the team. It is assembled
fresh at the start of every agent turn, injected automatically, and kept within a strict token budget.

**Assembly algorithm:**

```python
def assemble_briefing(project_id: str, engineer_id: str) -> str:
    active = get_active_sessions(project_id)           # Redis: who is connected right now
    recent = get_recent_activity(project_id, limit=5)  # compressed activity bullets
    contracts = get_contracts(project_id)              # all published contracts, summaries only
    open_decisions = get_open_decisions(project_id)    # unresolved resolution cards
    my_role = get_role(project_id, engineer_id)

    briefing = format_briefing(active, recent, contracts, open_decisions, my_role)

    # enforce token budget
    while count_tokens(briefing) > 2000:
        briefing = truncate_oldest_activity(briefing)

    return briefing
```

**Briefing format:**

```
=== PROJECT BRIEFING ===
Project: [name] · Your role: Backend · Session time: 47m
Active now: Frontend (Engineer A), Backend (you), Reviewer (Engineer C)

Recent activity:
· Frontend (A): completed UserCard component, calls GET /api/users/:id
· Backend (you): implemented GET /api/users/:id, published contract user-api-v1

Contracts published:
· user-api-v1 — GET /api/users/:id → UserDTO {id, email, displayName}
  (published by Backend, 12m ago)

Architecture decisions:
· ADR-001: Use Postgres for all persistent storage (decided by A + B, 2h ago)

Open decisions: none
=== END BRIEFING ===
```

**Why this works:**
The briefing puts the team's shared state into the agent's context on every turn — without requiring
the engineer to prompt for it. The agent naturally reasons about what teammates have done, what
contracts are available, and what decisions have been made.

### 5.5 Audit Log

Every action is logged. No exceptions. The audit log is an append-only Postgres table.

**Schema:** `audit_log(id, project_id, engineer_id, role, session_id, turn_id, timestamp, tool_name, arguments_json, result_summary, latency_ms)`

**What is logged:**
- Every MCP tool call (tool name, sanitized arguments, result summary)
- Session connect/disconnect events
- Signal publications and resolutions
- Conflict card creation and resolution
- Every ADR creation and status change
- Authentication events (login, token issuance)

**What is NOT logged:**
- Raw conversation content (that stays in Claude Code, never reaches Backyard)
- Engineer private chat with their agent
- File content (only summaries and metadata)

**Audit log access:**
- Engineers see their own activity in the dashboard
- Engineering managers see their team's activity
- Admins can export full audit logs as CSV/JSON (filterable by engineer, session, time range)
- SOC 2: logs are append-only, tamper-evident (row-level checksums), retained per policy

### 5.6 Conflict Surface

The conflict surface watches for situations where two or more agents are about to make contradictory
decisions.

**Detection triggers:**
1. **Explicit contradiction:** Two agents call `raise_resolution` with opposing facts
   (e.g., "use Postgres" vs. "use SQLite")
2. **Domain claim conflict:** Two agents both write to the same file path within a short window
   (detected via Redis key: `active_write:{project_id}:{path}`)
3. **Contract version conflict:** Agent A is building against `user-api-v1`, but Agent B publishes
   `user-api-v2` with a breaking change
4. **Contradicting ADR:** An agent proposes an action that contradicts an existing ADR
   (detected when `publish_context` produces an ADR that conflicts with an existing one)

**Resolution card format:**

```
┌─────────────────────────────────────────────────────────┐
│  CONFLICT — Database technology choice                  │
│                                                         │
│  Engineer A (Frontend agent) said:  "use Postgres"      │
│  Engineer B (Backend agent) said:   "use SQLite"        │
│                                                         │
│  Affected: db/**, infra/docker-compose.yml              │
│                                                         │
│  [Choose Postgres]  [Choose SQLite]  [Discuss first]    │
│                                                         │
│  Record this decision as an ADR? [Yes] [No]             │
└─────────────────────────────────────────────────────────┘
```

**What happens when a conflict is detected:**
1. Both agents' pending writes to the affected domain are paused (Redis lock)
2. Resolution card is posted to the web dashboard
3. Both engineers are notified (dashboard notification, optional email)
4. Engineers resolve in the dashboard
5. The decision is published as an ADR to the shared context store (if they choose)
6. Both agents' pending operations resume with the decision in their next briefing

Agents do not proceed past a conflict. No silent timer picks a winner.

---

## 6. MCP Tool Specifications

Full tool specifications. All tools communicate via JSON over MCP.

### 6.1 Context tools

**`query_shared_context`**
```
Description: Search the shared context store for contracts, ADRs, and file summaries.
Input:
  query: string          — natural language or structured: "contracts for role:backend"
  type?: "contract" | "adr" | "file_summary" | "activity"
  role?: string          — filter by publishing role
  path?: string          — filter file summaries by path prefix
Output:
  results: Array<{type, id, summary, created_at, relevance_score}>
```

**`publish_context`**
```
Description: Publish a contract, architecture decision, or file summary to the shared store.
Input:
  type: "contract" | "adr"
  id: string             — e.g. "user-api-v1", "adr-database-choice"
  content: object        — typed per artifact type (see §8 data model)
  description?: string   — human-readable summary for the briefing
Output:
  artifact_id: string
  published_at: string
```

**`get_file_summary`**
```
Description: Get the auto-generated summary of any file in the project.
Input:
  path: string           — relative to project root
Output:
  summary: string        — 2–3 sentence description
  exports: string[]      — exported functions, classes, types
  last_modified_by: string
  last_modified_at: string
  (null if file has not been written through Backyard)
```

**`get_project_status`**
```
Description: Get the current state of the project — active engineers, recent activity, open decisions.
Output:
  active_sessions: Array<{engineer_id, role, connected_since}>
  recent_contracts: Array<{id, published_by, published_at}>
  open_decisions: Array<{id, description, created_at}>
  recent_activity: string[]   — last 5 activity bullets
```

### 6.2 Signal tools

**`signal_ready`**
```
Description: Broadcast that a milestone or dependency is ready.
Input:
  topic: string          — e.g. "user-api", "auth-middleware", "db-migrations"
  payload?: object       — optional structured data (e.g. the published contract)
  message?: string       — human-readable message for the briefing
Output:
  signal_id: string
  notified_waiters: number   — how many agents were unblocked
```

**`wait_for_signal`**
```
Description: Block this agent turn until the specified signal is published. If the signal was already
             published earlier in this session, returns immediately.
Input:
  topic: string          — the signal topic to wait for
  timeout?: number       — seconds before returning {timed_out: true}; default 300
Output:
  signal_id: string
  payload?: object       — whatever was included in signal_ready
  published_by: string
  published_at: string
  (or) timed_out: true
```

### 6.3 Coordination tools

**`propose_cross_domain_edit`**
```
Description: Request permission to edit a file outside your role's domain. Called automatically by
             the MCP Hub when a write_file targets an out-of-domain path.
Input:
  path: string           — the file you want to edit
  reason: string         — why you need to edit it
  intent: string         — brief description of the planned change
Output:
  approved: boolean
  approved_by?: string   — role of the engineer who approved
  decision_id?: string   — id of the pending decision card if not yet approved
```

**`raise_resolution`**
```
Description: Surface a conflict or contradictory instruction to all engineers on this project.
             Pauses the calling agent's current action until resolution.
Input:
  title: string          — short description of the conflict
  conflict_a: string     — one side of the conflict
  conflict_b: string     — the other side
  affects: string[]      — file paths or domains affected
  agent_read?: string    — the agent's read of the trade-off (optional, shown on the card)
Output:
  resolution_id: string
  (agent is now paused until engineers resolve via the dashboard)
```

**`request_clarification`**
```
Description: Post a question to a specific role's engineer, visible on the dashboard.
Input:
  to_role: string        — the role to ask (e.g. "backend", "devops")
  question: string       — the question
  context?: string       — relevant context
Output:
  clarification_id: string
  (response delivered to the agent as a signal when the engineer replies)
```

### 6.4 Standard file tools (pass-through)

These are standard MCP file tools. In Problem 1, they pass through to the engineer's local
filesystem as usual. The MCP Hub intercepts them only to generate file summaries and enforce role
domain policies.

- `read_file(path)` — read a file
- `write_file(path, content)` — write a file (triggers file summary generation + domain check)
- `list_files(path, pattern?)` — list files matching a glob pattern

### 6.5 Review tools (Reviewer role only)

- `create_review_comment(path, line, comment)` — post a review comment to the dashboard
- `approve_change(session_id, comment?)` — approve a proposed change
- `request_changes(session_id, comment)` — request changes before a proposed edit is applied

---

## 7. Key Data Flows

### 7.1 The contract flow — the stand-up that never happens

```
t=0   Agent A starts building a UserCard component.
      Calls wait_for_signal("user-api", timeout=600).
      The MCP Hub subscribes to Redis: signals:{project_id}:user-api
      Agent A's turn is paused (MCP SSE connection stays open).

t=14m Agent B finishes implementing GET /api/users/:id.
      Agent B calls publish_context({ type: "contract", id: "user-api-v1",
        endpoints: [{ method: "GET", path: "/api/users/:id",
                      response: "UserDTO {id, email, displayName}" }] })
      → Contract stored in Postgres
      → Briefing for all engineers updated
      Then calls signal_ready("user-api", payload: { contract_id: "user-api-v1" })
      → Redis publishes to signals:{project_id}:user-api
      → MCP Hub receives the message
      → Agent A's wait_for_signal resolves with the contract payload

t=14m Agent A receives:
      { signal_id: "...", payload: { contract_id: "user-api-v1" },
        published_by: "backend", published_at: "..." }
      Agent A calls query_shared_context({ type: "contract", id: "user-api-v1" })
      → receives the full contract
      Agent A builds against the real API shape.

      The "is the API ready?" Slack message never gets sent.
      The stand-up never happens.
```

### 7.2 The contradiction flow — surfaced to engineers immediately

```
t=0   Engineer A tells their agent: "use Postgres for all persistence"
      Engineer B tells their agent: "SQLite is simpler, use it"

      (These are told in separate sessions simultaneously)

t=2m  Agent A proposes a Postgres setup → calls write_file("db/schema.py", ...)
      MCP Hub checks active write lock on db/schema.py → none → proceeds
      Writes file → generates file summary → updates briefing

t=3m  Agent B proposes SQLite → calls write_file("db/schema.py", ...)
      MCP Hub checks: db/schema.py was just written by Backend role (Agent A)
      Both agents detect the contradiction on db/schema.py
      MCP Hub calls raise_resolution automatically:
        title: "Database technology conflict"
        conflict_a: "Backend (A): Postgres setup applied to db/schema.py"
        conflict_b: "Backend (B): SQLite setup proposed for db/schema.py"
        affects: ["db/schema.py", "infra/docker-compose.yml"]

      → Resolution card posted to dashboard
      → Both engineers notified
      → Agent B's write is queued, not applied

t=6m  Engineers A and B discuss in real life (they see the card immediately)
      Engineer A clicks "Choose Postgres" and checks "Record as ADR"
      Dashboard posts: PUT /projects/{id}/resolutions/{resolution_id}
        { decision: "postgres", record_adr: true }

      → ADR-001 created: { title: "Use Postgres for all persistence",
          status: "accepted", affects: ["db/**"] }
      → ADR stored in Postgres, added to shared context store
      → Agent B's queued write is cancelled; Agent B's next turn includes ADR-001 in briefing
      → Agent B's agent automatically aligns with Postgres
```

### 7.3 The briefing flow — what every agent sees

```
Agent turn starts → Claude Code calls GET /project/{id}/mcp/resources
→ MCP Hub returns: [{ uri: "backyard://briefing", name: "Project Briefing", mimeType: "text/plain" }]
→ Claude Code calls GET /project/{id}/mcp/resources/backyard://briefing
→ MCP Hub assembles briefing:
    get_active_sessions()     → Redis: SMEMBERS sessions:{project_id}
    get_recent_activity()     → Postgres: latest compressed activity bullets
    get_contracts()           → Postgres: all contracts, summaries only
    get_open_decisions()      → Postgres: unresolved resolution cards
    format + token-count → trim if > 2000 tokens
→ Returns briefing as text
→ Claude Code includes it in the agent's context
→ The agent reasons about the team's state naturally, without the engineer asking
```

---

## 8. Data Model

### 8.1 Postgres schema

```sql
-- Projects and members
CREATE TABLE projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    org_id      UUID NOT NULL REFERENCES orgs(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE project_members (
    project_id  UUID NOT NULL REFERENCES projects(id),
    engineer_id UUID NOT NULL REFERENCES engineers(id),
    role        TEXT NOT NULL,     -- 'frontend' | 'backend' | 'devops' | 'reviewer' | custom
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (project_id, engineer_id)
);

-- Shared context artifacts
CREATE TABLE contracts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id),
    contract_id     TEXT NOT NULL,        -- e.g. "user-api-v1"
    published_by    UUID NOT NULL REFERENCES engineers(id),
    role            TEXT NOT NULL,
    version         INT NOT NULL DEFAULT 1,
    content_json    JSONB NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, contract_id, version)
);

CREATE TABLE adrs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id),
    adr_ref     TEXT NOT NULL,            -- e.g. "ADR-001"
    title       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'accepted',
    affects     TEXT[] NOT NULL,          -- file paths or domain names
    decision    TEXT NOT NULL,
    rationale   TEXT,
    decided_by  UUID[] NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE file_summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id),
    path            TEXT NOT NULL,
    summary         TEXT NOT NULL,
    exports         TEXT[] NOT NULL DEFAULT '{}',
    last_modified_by UUID NOT NULL REFERENCES engineers(id),
    last_modified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, path)
);

CREATE TABLE activity_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id),
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    bullets         TEXT[] NOT NULL,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Signals
CREATE TABLE signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id),
    topic           TEXT NOT NULL,
    published_by    UUID NOT NULL REFERENCES engineers(id),
    payload_json    JSONB,
    message         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Conflicts and resolutions
CREATE TABLE resolutions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id),
    title           TEXT NOT NULL,
    conflict_a      TEXT NOT NULL,
    conflict_b      TEXT NOT NULL,
    affects         TEXT[] NOT NULL,
    agent_read      TEXT,
    status          TEXT NOT NULL DEFAULT 'open',   -- 'open' | 'resolved' | 'dismissed'
    decision        TEXT,
    decided_by      UUID[],
    adr_id          UUID REFERENCES adrs(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

-- Audit log
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    project_id      UUID NOT NULL REFERENCES projects(id),
    engineer_id     UUID NOT NULL REFERENCES engineers(id),
    role            TEXT NOT NULL,
    session_id      UUID NOT NULL,
    turn_id         TEXT,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tool_name       TEXT NOT NULL,
    arguments_json  JSONB NOT NULL,
    result_summary  TEXT,
    latency_ms      INT,
    checksum        TEXT NOT NULL    -- SHA-256 of (id || project_id || engineer_id || timestamp || tool_name)
);

-- Engineers and orgs
CREATE TABLE orgs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    plan        TEXT NOT NULL DEFAULT 'team',   -- 'team' | 'enterprise' | 'enterprise_plus'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE engineers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES orgs(id),
    email       TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE api_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    engineer_id UUID NOT NULL REFERENCES engineers(id),
    token_hash  TEXT NOT NULL UNIQUE,   -- bcrypt hash of the raw token
    name        TEXT,                   -- e.g. "laptop", "VS Code"
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    revoked_at  TIMESTAMPTZ
);
```

### 8.2 Redis key schema

```
# Active sessions
sessions:{project_id}                   SET of engineer_ids currently connected
session:{project_id}:{engineer_id}      HASH {role, connected_since, last_turn_at, session_id}

# Auth cache (to avoid hitting Postgres on every tool call)
token:{token_hash}                      HASH {engineer_id, org_id, role, project_id}  TTL: 5m

# Signals (pub/sub channels)
signals:{project_id}:{topic}            pub/sub channel

# Hot state
briefing:{project_id}                   STRING compressed briefing cache               TTL: 30s
contracts_hot:{project_id}             STRING JSON list of contract summaries          TTL: 60s
open_resolutions:{project_id}           SET of resolution_ids currently open

# Write activity (for conflict detection)
active_write:{project_id}:{path}        STRING {engineer_id, intent, acquired_at}      TTL: 30s

# Turn counting (for activity compression trigger)
turn_count:{project_id}                 INT incremented on each agent turn; resets at 10
```

---

## 9. Authentication & Project Setup

### 9.1 Engineer authentication

Backyard uses **API tokens** — the same pattern as GitHub Personal Access Tokens.

1. Engineer logs into the Backyard web dashboard (SSO/SAML in Phase 1B; email/password in 1A)
2. Engineer generates an API token in the dashboard: "New device" → copy token
3. Engineer adds the token to their environment:
   ```bash
   export BACKYARD_TOKEN=bkyd_live_xxxxxxxxxxxxxxxx
   ```
4. The `.claude/settings.json` entry passes the token:
   ```json
   {
     "mcpServers": {
       "backyard": {
         "url": "https://backyard.yourcompany.com/project/abc123",
         "headers": { "Authorization": "Bearer ${BACKYARD_TOKEN}" }
       }
     }
   }
   ```

### 9.2 Project setup (admin flow)

1. Admin creates an org at `https://backyard.yourcompany.com`
2. Admin creates a project → gets a project URL
3. Admin invites engineers by email → each engineer gets an invitation link
4. Engineers set their role (Frontend / Backend / DevOps / Reviewer) in the dashboard
5. Admin can optionally define custom roles via `backyard.toml` committed to the repo:

```toml
# backyard.toml  (committed to the project repo, read by the server on project connect)
[project]
name = "Acme Payments Service"

[roles.mobile]
domains = ["ios/**", "android/**"]
capabilities = ["read_file", "write_file", "list_files", "signal_ready",
                "wait_for_signal", "query_shared_context", "publish_context"]

[roles.data]
domains = ["pipelines/**", "dbt/**", "airflow/**"]
capabilities = ["read_file", "write_file", "list_files", "signal_ready",
                "wait_for_signal", "query_shared_context", "publish_context"]
```

### 9.3 Claude Code settings template

After setup, the dashboard shows the engineer the exact `.claude/settings.json` snippet to add:

```json
{
  "mcpServers": {
    "backyard": {
      "url": "https://backyard.yourcompany.com/project/abc123",
      "headers": { "Authorization": "Bearer ${BACKYARD_TOKEN}" }
    }
  }
}
```

One copy-paste. Done.

---

## 10. Role System

### 10.1 Built-in roles

| Role | Default domain | Can do without asking | Asks first to |
|---|---|---|---|
| **Frontend** | `ui/**` `components/**` `styles/**` `pages/**` `*.css` `*.tsx` `*.jsx` | Write domain files, read any file, publish FE contracts, signal | Touch `api/**` `db/**` `infra/**` |
| **Backend** | `api/**` `services/**` `db/**` `middleware/**` `*.py` (service) | Write domain files, read any file, publish API contracts, own migrations | Touch `ui/**` `infra/**` |
| **DevOps** | `infra/**` `*.yml` `Dockerfile` `.github/**` `scripts/**` | Write domain files, read any, trigger CI, publish infra contracts | Touch app code (`api/**` `ui/**`) |
| **Reviewer** | read-everywhere | Read any file, post review comments, approve/request changes, record ADRs | Write anything (always via proposal) |

### 10.2 Domain enforcement

Domain checks happen in `mcp_hub/server.py` before every `write_file` call:

```python
def check_domain(role: str, path: str, project_config: ProjectConfig) -> DomainResult:
    role_domains = get_role_domains(role, project_config)
    if any(pathspec.match_file(domain, path) for domain in role_domains):
        return DomainResult.ALLOWED
    return DomainResult.NEEDS_PROPOSAL
```

`NEEDS_PROPOSAL` does not block the agent — it calls `propose_cross_domain_edit` automatically
and posts a request to the owning role's engineer on the dashboard. The edit is queued until
approved, or approved instantly if the owning engineer clicks "Approve" on the dashboard.

### 10.3 Role as briefing context

The briefing is tailored to the engineer's role. A Backend engineer's briefing emphasizes
published contracts and API decisions. A Frontend engineer's briefing emphasizes what backend
APIs are available and what UI contracts have been agreed. The Reviewer sees everything.

---

## 11. Trust & Conflict Model

### 11.1 System floor (non-negotiable)

These rules are enforced at the MCP Hub regardless of role, engineer instruction, or resolution:

- No file access outside the project root (path traversal blocked: `os.path.realpath` check)
- No tool call without a valid, un-revoked API token
- No reading another engineer's private session context (sessions are isolated; the shared context
  store is the only cross-session channel)
- Audit log cannot be disabled or modified (append-only, row checksums)

### 11.2 Conflict resolution principles

When agents receive contradictory instructions:

1. **Agents stop the affected action** — they do not race ahead, they do not negotiate with each
   other, they do not guess which instruction takes priority
2. **`raise_resolution` is called** — either explicitly by the agent, or automatically by the MCP
   Hub when it detects a domain conflict
3. **Both engineers see the resolution card** — immediately, on the dashboard
4. **Engineers decide together** — the system does not auto-resolve, does not apply a rank-based
   rule, does not time out and pick a winner
5. **Decision is recorded** — as an ADR if the engineer chooses; always in the audit log

**Why no auto-resolution:**
The point of Backyard is that engineers are working together in real time — they are reachable. A
conflict card takes 60 seconds to resolve when both engineers are active. Auto-resolution would
produce wrong decisions silently. The product's advantage is that conflicts surface fast and resolve
fast because the humans are right there.

### 11.3 What each agent is told

The MCP Hub injects a system-level instruction at the start of every agent turn, before the
project briefing. This cannot be overridden by the engineer:

```
You are working in a shared Backyard project with other engineers and agents.
Ground rules:
- Before writing files outside your role's domain ({role_domains}), the system will
  automatically route the request to the appropriate engineer for approval.
- If your instructions conflict with a published ADR or another agent's actions,
  call raise_resolution and wait for engineers to decide. Do not proceed on assumptions.
- Use query_shared_context to check what contracts and decisions already exist before
  building new ones.
- Use signal_ready to notify others when a dependency is complete.
  Use wait_for_signal when you need a dependency that is not yet available.
```

---

## 12. Tech Stack

### 12.1 Core choices

| Concern | Choice | Why |
|---|---|---|
| **Server** | FastAPI + uvicorn | Async-native, first-class WebSocket/SSE, Pydantic-validated schemas, Python-native |
| **MCP interface** | `mcp` (official Python SDK) | Claude Code already speaks MCP; no custom protocol; works with every Claude Code surface |
| **Async runtime** | asyncio | Single event loop naturally serializes lock operations; fits the FastAPI model |
| **Signals / pub-sub** | `redis.asyncio` | Sub-millisecond pub/sub; SETNX atomic locks; keyspace events for TTL expiry detection |
| **Durable store** | Postgres 16 + SQLAlchemy 2 (async) + Alembic | Relational fits the structured artifact model; migrations via Alembic |
| **Briefing generation** | `anthropic` Python SDK | Activity compression every ~10 turns; `claude-haiku-4-5` for low cost/latency |
| **File summary generation** | `anthropic` Python SDK | Called on every `write_file`; `claude-haiku-4-5` |
| **Auth** | API tokens + bcrypt | Simple, secure, Claude Code `headers` field supports it |
| **Dashboard** | Vanilla HTML/JS + FastAPI static | Minimal; SSE for live updates; no JS framework overhead |
| **Tests** | pytest + pytest-asyncio + fakeredis | Signal engine and context store are the correctness surfaces; test them first |
| **Dev infra** | docker-compose | One command: `docker-compose up` gives Redis + Postgres |
| **Packaging** | uv + pyproject.toml | Fast installs |
| **Linting / typing** | ruff + mypy (strict) | Catch protocol mistakes early |

### 12.2 Model selection for internal calls

| Use | Model | Reason |
|---|---|---|
| Activity compression | `claude-haiku-4-5` | Low cost; speed matters for per-turn operations |
| File summary generation | `claude-haiku-4-5` | Called on every write; must be fast and cheap |
| Conflict description | `claude-haiku-4-5` | Short summaries only |

The engineers' own agents use whatever model they have configured in Claude Code — that is outside
Backyard's control and cost. Backyard's own API calls are small, cheap, and bounded.

### 12.3 What Backyard does NOT need

- No vector database — all context queries are structured (by type, path, role, contract ID)
- No custom Claude Code client — we use the MCP protocol instead
- No CRDT library — no real-time shared codebase
- No container orchestration — Problem 1 runs as a single FastAPI process behind a load balancer

---

## 13. Repository Layout

```
backyard/
│
├── docs/
│   ├── technical-report.md          # this document
│   ├── architecture.md              # quick component + data-flow reference
│   └── roadmap.md                   # phased plan
│
├── src/
│   └── backyard/
│       │
│       ├── protocol/                # Pydantic models for every event and message
│       │   ├── __init__.py
│       │   ├── artifacts.py         # Contract, ADR, FileSummary, ActivityLog
│       │   ├── signals.py           # Signal, WaitResult
│       │   ├── resolutions.py       # ResolutionCard, ResolutionDecision
│       │   ├── audit.py             # AuditEntry
│       │   └── briefing.py          # ProjectBriefing, BriefingSection
│       │
│       ├── server/
│       │   ├── app.py               # FastAPI entry point: MCP routes + dashboard routes
│       │   ├── auth.py              # Token validation, session auth
│       │   ├── project_registry.py  # Project config and member lookup
│       │   │
│       │   ├── mcp_hub/
│       │   │   ├── __init__.py
│       │   │   ├── server.py        # MCP server instance, tool routing, domain checks
│       │   │   ├── context_tools.py # query_shared_context, publish_context,
│       │   │   │                    # get_file_summary, get_project_status
│       │   │   ├── signal_tools.py  # signal_ready, wait_for_signal
│       │   │   ├── coord_tools.py   # raise_resolution, propose_cross_domain_edit,
│       │   │   │                    # request_clarification
│       │   │   ├── file_tools.py    # read_file, write_file, list_files (with interception)
│       │   │   └── review_tools.py  # create_review_comment, approve_change (Reviewer only)
│       │   │
│       │   ├── context/
│       │   │   ├── __init__.py
│       │   │   ├── store.py         # Postgres reads/writes for all artifact types
│       │   │   ├── briefing.py      # assemble_briefing(), compress_activity()
│       │   │   └── summarizer.py    # generate_file_summary() via Anthropic API
│       │   │
│       │   ├── signals/
│       │   │   └── engine.py        # publish_signal(), await_signal(), Redis pub/sub
│       │   │
│       │   ├── audit/
│       │   │   └── log.py           # append_audit_entry(), query_audit_log()
│       │   │
│       │   ├── conflicts/
│       │   │   ├── surface.py       # detect_conflict(), create_resolution_card()
│       │   │   └── detector.py      # domain conflict, ADR contradiction detection
│       │   │
│       │   └── roles/
│       │       └── definitions.py   # built-in role definitions, domain patterns, capabilities
│       │
│       └── dashboard/               # served as static files by FastAPI
│           ├── index.html           # main SPA: presence, activity feed, conflict cards
│           └── static/
│               ├── main.js          # SSE client, dashboard logic
│               └── style.css
│
├── tests/
│   ├── conftest.py                  # pytest fixtures: fakeredis, test Postgres, test client
│   ├── test_signal_engine.py        # signal publish, wait, timeout, persistent signal
│   ├── test_context_store.py        # contract CRUD, ADR CRUD, file summary, query
│   ├── test_briefing.py             # briefing assembly, token budget, compression trigger
│   ├── test_conflict_detector.py    # domain conflict, ADR contradiction, version conflict
│   ├── test_auth.py                 # token validation, session lifecycle
│   ├── test_role_enforcement.py     # domain checks, proposal routing
│   └── test_mcp_hub.py              # end-to-end MCP tool call tests
│
├── infra/
│   └── docker-compose.yml           # Redis 7 + Postgres 16 for local dev
│
├── backyard.toml.example            # example project config with custom roles
├── pyproject.toml
└── README.md
```

---

## 14. Implementation Plan

### Build order principle

Build the core correctness surfaces first, before the server that exposes them. The things that
are hardest to get wrong — signals, context store, conflict detection — must be unit-tested in
isolation before they handle real sessions.

### Phase 1A — Core Coordination Server

**Goal:** two engineers on the same project can share context, signal each other, and have
contradictory decisions surfaced. Engineers connect with one line of config.

**Estimated timeline: 6 weeks**

---

**Week 1 — Foundation**

| Task | Files | Definition of done |
|---|---|---|
| Project skeleton | `pyproject.toml`, `infra/docker-compose.yml`, `src/` | `docker-compose up` → Redis + Postgres running; `pytest` passes on empty test suite |
| Protocol models | `protocol/artifacts.py`, `protocol/signals.py`, `protocol/resolutions.py`, `protocol/audit.py` | All Pydantic models defined and type-checked by mypy |
| Postgres schema | `alembic/versions/0001_initial.py` | Migration applies cleanly; all tables exist |
| Auth service | `server/auth.py` | Token hash, validate, cache in Redis; tests pass |

---

**Week 2 — Signal Engine**

| Task | Files | Definition of done |
|---|---|---|
| Signal engine | `server/signals/engine.py` | `publish_signal`, `await_signal`, timeout, persistent signal — all tested with fakeredis |
| Signal persistence | `server/context/store.py` (signals table) | Signals persisted to Postgres; `await_signal` resolves immediately on already-published signals |

Tests to write: publish → wait resolves; wait before publish → resolves when published; timeout;
persistent signal from previous session.

---

**Week 3 — Context Store & File Summaries**

| Task | Files | Definition of done |
|---|---|---|
| Context store CRUD | `server/context/store.py` | contract, ADR, file_summary create/read/query — all tested against test Postgres |
| File summarizer | `server/context/summarizer.py` | `generate_file_summary(path, content)` → calls Anthropic API, returns FileSummary; tested with mock Anthropic client |
| Activity compression | `server/context/briefing.py` | `compress_activity(entries)` → calls Anthropic API, returns bullets; tested |
| Briefing assembly | `server/context/briefing.py` | `assemble_briefing()` → correct output, ≤2 000 tokens, trimming works |

---

**Week 4 — MCP Hub (core tools)**

| Task | Files | Definition of done |
|---|---|---|
| FastAPI app skeleton | `server/app.py` | `GET /health` returns 200; MCP SSE endpoint exists at `/project/{id}/mcp` |
| MCP server | `server/mcp_hub/server.py` | MCP handshake completes; tool list returned to Claude Code |
| Context tools | `server/mcp_hub/context_tools.py` | `query_shared_context`, `publish_context`, `get_file_summary`, `get_project_status` — all return correct results |
| Signal tools | `server/mcp_hub/signal_tools.py` | `signal_ready`, `wait_for_signal` — work end-to-end over MCP |
| File tools with interception | `server/mcp_hub/file_tools.py` | `write_file` triggers file summary generation; domain check runs |
| Role definitions | `server/roles/definitions.py` | All built-in roles defined; domain patterns match correctly |
| Role enforcement | `server/mcp_hub/server.py` | Out-of-domain writes trigger proposal flow (log only in Phase 1A; full UI in 1B) |

---

**Week 5 — Audit Log & Conflict Surface**

| Task | Files | Definition of done |
|---|---|---|
| Audit log | `server/audit/log.py` | Every tool call written to Postgres audit_log; checksum computed; tested |
| Conflict detector | `server/conflicts/detector.py` | Domain conflict, ADR contradiction, version conflict — all detected and unit-tested |
| Resolution cards | `server/conflicts/surface.py` | `create_resolution_card()` → Postgres + Redis open_resolutions; resolution flow works |
| Coordination tools | `server/mcp_hub/coord_tools.py` | `raise_resolution`, `propose_cross_domain_edit`, `request_clarification` — functional |

---

**Week 6 — Dashboard & Pilot Prep**

| Task | Files | Definition of done |
|---|---|---|
| Minimal web dashboard | `dashboard/index.html`, `static/main.js` | Shows: active engineers, recent activity, conflict cards with Approve/Dismiss; SSE live updates |
| Resolution card UI | `dashboard/index.html` | Engineers can resolve conflict cards from the browser |
| Project setup flow | dashboard | Admin can create project, invite engineers, assign roles |
| API token management | dashboard | Engineers can generate and revoke API tokens |
| Deployment | | Docker image builds; runs behind nginx; HTTPS with Let's Encrypt |
| End-to-end test | | Two Claude Code instances connect, exchange a signal, detect a file conflict — all works |

---

### Phase 1B — Visibility & Enterprise Controls

**Goal:** enterprise teams can evaluate and procure Backyard. Compliance and SSO are blockers for
corporate procurement.

**Estimated timeline: 8 weeks after 1A**

| What | Description | Why now |
|---|---|---|
| **SSO / SAML** | Okta, Azure AD, Google Workspace | Procurement blocker for any company >50 engineers |
| **Org-wide admin dashboard** | User management, role assignments, project list | EM/VP needs visibility |
| **Audit log viewer** | Filterable by engineer / session / time range; CSV/JSON export | Compliance and debugging |
| **Full conflict resolution UI** | Side-by-side diff view, ADR creation in the browser | Makes conflict resolution fast and clear |
| **Activity feed** | Real-time team activity stream per project | Presence awareness for EMs |
| **Email notifications** | Conflict card, clarification request, resolution decisions | Engineers need to see cards even if dashboard is not open |
| **Usage reporting** | Per-engineer and per-project activity/tool counts | Cost attribution, seat billing |
| **`propose_cross_domain_edit` full flow** | Approval UI in dashboard; queued writes applied on approval | Complete the role enforcement story |

---

### Phase 1C — Enterprise Hardening

**Goal:** financial services, healthcare, and defense can purchase Backyard.

**Estimated timeline: 12 weeks after 1B**

| What | Description | Why now |
|---|---|---|
| **Private / on-premise deployment** | Docker Compose or Helm chart for customer's cloud | Required by financial and healthcare procurement |
| **SOC 2 Type II** | Security controls, audit trail, pen test | Most enterprise procurement requires this |
| **SCIM provisioning** | Auto-sync engineers from Okta / Azure AD | Large orgs cannot manage users manually |
| **Retention policies** | Configurable audit log retention (30d / 90d / 1yr / indefinite) | Legal/compliance requirement |
| **CI/CD integration** | Webhook: failing CI build → notification in project briefing and dashboard | Closes the loop on agent-caused breakage |
| **Rate limiting & quotas** | Per-engineer and per-org limits on API calls | Protect shared infrastructure; prevent runaway agents |
| **Multi-region** | Deploy in EU and APAC | Data residency requirements for EU customers |
| **Self-healing MCP connection** | Auto-reconnect on disconnect; session state preserved | Reliability for production use |

---

## 15. Pilot Experiment

The pilot answers one question: **does shared agent context meaningfully reduce coordination
overhead for an enterprise engineering team?**

### Setup

- 1 enterprise engineering team, 4–8 engineers, existing Claude Code users
- 1 project they are actively building (not a toy project)
- 2 sprints: one sprint without Backyard (baseline), one sprint with Backyard

### What to measure

| Metric | How to measure | What it tells us |
|---|---|---|
| **Time waiting for a dependency** | Audit log: `wait_for_signal` calls + resolution time | Did signals replace the "is the API ready?" stand-up? |
| **Coordination messages (Slack/email)** | Team self-reports daily count | Did Backyard reduce out-of-band coordination? |
| **Contradictory decisions caught** | Conflict cards created and resolved | Did we catch decisions agents would have gotten wrong? |
| **Time-to-first-integration** | Time from first commit to first successful cross-role integration | Did shared context accelerate cross-team work? |
| **Engineer perception** | 5-question survey after each sprint | Would they run the next sprint this way? |

### Success threshold

If at least 3 of these are true after the pilot sprint:
- `wait_for_signal` resolved at least 5 dependencies that would otherwise have been Slack messages
- At least 2 contradictory decisions were surfaced before they were committed to code
- The Engineering Manager says "yes, we would run the next sprint this way"
- No engineer says "this made my work harder"

Then Phase 1A is validated and Phase 1B begins.

---

## 16. Enterprise Fit

### What enterprise customers need (and when Backyard provides it)

| Requirement | Phase |
|---|---|
| Audit log of all agent actions | **1A** (day one) |
| Works with existing Claude Code — no new tool | **1A** (by design) |
| Role-based access control | **1A** (domain roles) |
| SSO / SAML (Okta, Azure AD) | **1B** |
| Org-wide admin and usage reporting | **1B** |
| Compliance audit log export (CSV/JSON) | **1B** |
| Private / on-premise deployment | **1C** |
| SOC 2 Type II | **1C** |
| SCIM provisioning | **1C** |
| Data residency (EU/APAC) | **1C** |

The audit log from day one is non-negotiable. Enterprise security teams will ask for it on the
first procurement call, and it cannot be bolted on later without re-architecting the system.

### Buyer and champion

- **Buyer:** CTO, VP of Engineering, or Engineering Manager (team of 10+)
- **Champion:** a senior engineer or tech lead who tried it, liked it, and sold it internally
- **Blocker:** IT/Security who needs SSO and audit before approving any new vendor

The sales motion for Phase 1A is: find a champion engineer at a target company, run the pilot,
get the Engineering Manager's endorsement, then close procurement with SSO + audit log in 1B.

---

## 17. Revenue Model

Enterprise B2B only. No individual tier. No free tier. The buyer is an organization.

| Tier | Price | What's included |
|---|---|---|
| **Team** | $75 / seat / mo, annual | Unlimited projects, all roles, full dashboard, audit log, CI hooks, email support |
| **Enterprise** | $150 / seat / mo, annual | Team + SSO/SAML, SCIM, SOC 2 reports, private-cloud deployment, SLA (99.9%), dedicated support |
| **Enterprise+** | Custom annual contract | Enterprise + on-premise, custom retention, professional services, custom integrations |

**Entry:** a pilot engagement at no charge, for 30 days, with an agreed success criterion. The pilot
is the sales cycle. If it passes the §15 threshold, the team buys Team tier for the next quarter.

**Token cost:** Backyard's internal API calls (file summary generation, activity compression) are
billed into the platform cost, not passed through. Engineers' own Claude Code model costs are
separate and remain the company's Anthropic contract.

---

## 18. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| **R1** | Coordination overhead rises instead of falls | Medium | Critical | Pilot experiment (§15) measures this directly before any further investment. Kill if overhead doesn't fall. |
| **R2** | Context store becomes stale | Low | High | File summaries regenerated on every write. Activity compressed every 10 turns. Structured queries only — no vector drift. |
| **R3** | Agents proceed despite a conflict | Low | High | `raise_resolution` pauses the affected operation at the MCP Hub before it executes. No agent can complete a blocked write. |
| **R4** | Enterprise won't adopt without compliance | High | High | Audit log in Phase 1A. SSO + exports in Phase 1B. SOC 2 in Phase 1C. Each is gate-to-next-phase. |
| **R5** | Anthropic builds this natively into Claude Code | Medium | Critical | Speed matters. The team that has real pilot data and enterprise relationships is defensible even if Anthropic ships something similar. Differentiate on private deployment and enterprise compliance. |
| **R6** | MCP protocol changes break compatibility | Low | Medium | Pin `mcp` SDK version; test against each new release before upgrading. The MCP Hub is the only surface that depends on the protocol. |
| **R7** | Briefing token budget causes context pressure | Medium | Medium | Strict 2 000-token cap enforced in code. Compression tested. If agents still complain about context length, reduce to 1 500 and trim further. |
| **R8** | Signal engine misses a signal (Redis restart) | Low | High | Signals persisted to Postgres before Redis publish. On reconnect, MCP Hub checks Postgres for signals published during the gap. |
| **R9** | Conflict detection too noisy | Medium | Medium | Only detect domain conflicts + explicit `raise_resolution` calls in Phase 1A. Refine ADR contradiction detection in Phase 1B based on pilot feedback. |
| **R10** | Pilot customer's IT blocks new tool | Medium | High | Not a new tool — it is a new MCP server URL. The engineer's Claude Code already speaks MCP. Backyard requires only HTTPS outbound on port 443, which is universally allowed. |

---

## References

- M. Reddy, *The Unbuilt Product*, white paper, June 2026
- Model Context Protocol specification and Python SDK (`mcp`) — modelcontextprotocol.io
- Anthropic, *Claude Code* — claude.ai/code
- FastAPI documentation — fastapi.tiangolo.com
- SQLAlchemy 2.0 async documentation
- Redis pub/sub documentation
