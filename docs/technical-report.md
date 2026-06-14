# Backyard — Multi-Human, Multi-Agent Collaborative Coding for Enterprise Engineering Teams

**Enterprise engineering teams. Each engineer with their own background AI agent. One live shared
project. All contributing at once, in real time.**
Companion to the white paper *The Unbuilt Product* (M. Reddy, June 2026).
Version 0.4 · Status: Design · Stack: Python · Target: Enterprise

---

## 0. Executive Summary

The white paper establishes the gap: every AI coding agent assumes **one human per session**, yet
enterprise software is built by teams of dozens to hundreds of engineers. AI has accelerated the
individual — it has not touched the team's coordination overhead. **Backyard** fills that gap with a
specific shape — and a deliberate design principle:

> **Backyard is a superset of Claude Code, not a replacement.** Every capability Claude Code provides
> to a single engineer — file editing, shell commands, git operations, MCP tool use, multi-step agent
> loops, streaming, slash commands, CLAUDE.md project context — is available in every session.
> Backyard adds the layer Claude Code deliberately left out: **many engineers, many agents, one shared
> live project, simultaneously.**

> Each engineer logs into the platform and gets their **own private session with their own background AI
> agent**. All of those sessions contribute to **one live shared project at the same time.** Every
> engineer's edits — and every agent's edits — appear live for the entire team. When two changes truly
> conflict, the collision is surfaced to the engineers involved and they **choose between themselves.**
> The full audit trail records who decided what and why.

The model is: **one shared project that the whole engineering team contributes to at once, with an AI
agent working alongside each engineer.** No pull requests, no merge latency, no "is the API ready?"
stand-up. The shared state is always already merged.

This report specifies the system end-to-end: the project-centric architecture, the real-time sync engine,
how separate sessions and background agents share one project, the two-layer conflict model (automatic
text convergence + human-resolved semantic conflicts), the trust model, roles, shared context, the
inter-agent protocol, a 4-week enterprise pilot, the Python stack, and a phased roadmap — with every one
of the white paper's **five fatal risks** mapped to a concrete mitigation.

---

## 1. The Core Idea (and how it differs from "shared session")

### 1.1 Project-centric, not session-centric

The unit everyone shares is the **Project** — the live codebase.

Each engineer has their **own Session**: their private chat, their own context, and their own
**background agent(s)** working on their behalf. Sessions are *isolated from each other* — you don't
read a colleague's conversation. You see other engineers' *edits and cursors* in the shared project,
not their private notes. This matches the trust model enterprise organizations need: individual
accountability with shared visibility.

```
                          ┌──────────── ONE LIVE PROJECT ────────────┐
                          │           (the shared codebase)           │
                          └───────────────────────────────────────────┘
                              ▲            ▲            ▲           ▲
          live edits          │            │            │           │   live edits
        ┌─────────────────────┘     ┌──────┘      ┌─────┘     └─────────────────┐
        │                            │             │                            │
  ┌───────────┐               ┌───────────┐  ┌───────────┐               ┌───────────┐
  │ Session A │               │ Session B │  │ Session C │               │ Session D │
  │  Human A  │               │  Human B  │  │  Human C  │               │  Human D  │
  │ + Agent A │               │ + Agent B │  │ + Agent C │               │ + Agent D │
  │ (private) │               │ (private) │  │ (private) │               │ (private) │
  └───────────┘               └───────────┘  └───────────┘               └───────────┘
```

### 1.2 Four things this gets right that pull requests don't — at enterprise scale

- **No merge step.** The shared state is *always already merged*. There is no "open a PR, wait, resolve
  conflicts, merge" — your edits and your agent's edits land in the live project as they happen.
- **Everyone sees everything, live.** A senior engineer watches a junior's agent work in real time and
  can intervene immediately — not in a diff review 24 hours later. Context is never reconstructed.
- **Cross-timezone handoffs cost nothing.** The incoming engineer's session picks up where the outgoing
  one left off; the agent briefs them on what happened. The first hour of every handoff disappears.
- **Full audit trail, always on.** Every agent action is logged with `(engineer, role, agent-turn,
  timestamp)`. Compliance and incident review don't require reconstructing history from git blame.

### 1.3 Full Claude Code feature parity — at every seat

Each engineer's session in Backyard has the complete Claude Code feature set. Nothing is cut to make
collaboration work. The multi-human layer is *additive*.

| Claude Code capability | In every Backyard session | Extended by Backyard |
|---|---|---|
| File read / edit / write | ✓ | Edits stream live to all teammates |
| Shell / bash command execution | ✓ | Output visible to all (with audit attribution) |
| Git operations | ✓ | Plus team-level attributed snapshots per session |
| MCP tool use (standard tools) | ✓ | Plus shared MCP Hub with team-coordination tools |
| Multi-step autonomous agent loops | ✓ | Agent output streams to all sessions in real time |
| Streaming responses | ✓ | Streamed to all participants, not just the operator |
| Slash commands | ✓ | — |
| CLAUDE.md project context | ✓ | A shared project-level CLAUDE.md visible to all agents |
| IDE / terminal client | ✓ (terminal, Phase 2: web IDE) | Live presence and shared view alongside |
| Permission model (approve/deny tools) | ✓ per session | Role-based capability enforcement at the org level |

The principle: **an engineer in Backyard should be at least as capable as an engineer using Claude Code
alone** — and additionally able to see, coordinate with, and build on what their teammates' agents are
doing in real time.

### 1.4 The one hard problem this creates

Real-time text collaboration is well understood for *prose*, because any interleaving of prose edits is
still valid prose. **Code is not prose:** two cleanly-merged edits can produce a file that does not
compile or that is logically contradictory. So Backyard needs **two layers** (see §5):

1. **Text convergence** — guarantees everyone's view is identical and no keystroke is ever lost.
2. **Semantic conflict detection** — notices when the converged code is broken or two sessions changed
   the same logical unit incompatibly, and **surfaces it to the engineers involved to choose between
   themselves.**

---

## 2. Design Principles

1. **The project is the shared object; sessions are private.** History and presence hang off the
   **project**; chat, context, and agent state hang off each human's **session**.
2. **Always-merged, never-blocked.** Real-time convergence means there is no merge step and no file you
   must wait for. Editing is live.
3. **Auto-merge the text, surface the meaning.** Text-level collisions converge automatically; only
   *semantic* conflicts interrupt a human — and then only the humans actually involved.
4. **Conflicts are resolved socially.** When a real conflict surfaces, it goes to a **shared resolution
   view** the involved humans both see, and they decide together. The system never silently picks a
   winner by rank.
5. **Agents coordinate through the project, not through each other's minds.** No agent reads another
   session's conversation. They share the **live code** plus **structured artifacts** (contracts, ADRs,
   file summaries). Context windows and cost stay bounded.
6. **Falsifiable before fancy.** Build the cheapest thing that proves two people + two background agents
   on one live project beat two people merging via PRs.

---

## 3. System Architecture

### 3.1 The nine components

```
┌──────────────────────────── BACKYARD PROJECT SERVER ────────────────────────────┐
│                              (Python · FastAPI · asyncio)                         │
│                                                                                  │
│   ② Live Sync Engine (CRDT)      ⑤ Semantic Conflict Watcher                     │
│   ③ Session Workspace (×N)       ⑥ Shared Context Store (per project)            │
│   ④ Agent Gateway (×N)           ⑦ MCP Hub                                       │
│   ⑧ Presence + Event Bus         ⑨ Snapshot/Git Service                         │
│                                                                                  │
│   ① Project Registry  ── owns projects, attaches sessions, keys everything ──    │
└──────────────────────────────────────────────────────────────────────────────────┘
        │                         │                          │
   Session A (Human+Agent)   Session B (Human+Agent)    Session C (Human+Agent)
        └─────────────────────────┴──── all edit ───────────┘
                                   ▼
                         ONE LIVE PROJECT (CRDT doc)  ⇄  Redis (presence, pub/sub)
                                                       ⇄  Postgres (history, context)
```

**① Project Registry** — owns projects; attaches/detaches sessions; everything keys off
`project_id` (shared) and `session_id` (per human).

**② Live Sync Engine (CRDT)** — *the real-time core.* Holds the shared codebase as a CRDT document.
Every edit — from a human's keystrokes or their background agent — is a CRDT update that converges on
every session with no lost work and no merge step. Built on **`pycrdt`** (Python bindings to Yjs/Yrs).

**③ Session Workspace (one per human)** — a human's private space: their chat history, their context,
their cursor/presence, and a live view of the shared project. Isolated from other sessions.

**④ Agent Gateway (one per session)** — wraps the Anthropic API for that human's **background agent**.
The agent's file edits are applied *as CRDT updates*, so they stream into the live project exactly like
human edits and are attributed to that session.

**⑤ Semantic Conflict Watcher** — sits above the CRDT. Detects when converged state is broken
(won't parse/compile) or when two sessions changed the same logical unit incompatibly, and raises a
**shared resolution card** to the involved humans. This is the code-specific layer plain text
collaboration doesn't need.

**⑥ Shared Context Store (per project)** — structured contracts, ADRs, and auto-generated file
summaries — how agents across different sessions understand the one shared project.

**⑦ MCP Hub** — exposes coordination tools to every agent as MCP tools (`publish_context`,
`wait_for_signal`, `raise_resolution`, …). MCP so a stock Claude Code CLI can eventually join a project.

**⑧ Presence + Event Bus** — live cursors, "who/which agent is editing what," and activity feed; Redis
pub/sub fan-out to all sessions.

**⑨ Snapshot / Git Service** — periodically and on milestones, checkpoints the live CRDT state into git
with per-change attribution `(session, human, agent)`. Git is the durable history and the export, not
the live working mechanism.

### 3.2 Why this shape

- Making the **project** the top-level object is what removes the white paper's load-bearing
  "single-principal assumption": presence, history, and context key off the project; many sessions
  attach to it.
- A **CRDT** is the right primitive because it guarantees convergence without a central lock, and —
  crucially for a Python team — **`pycrdt` speaks the Yjs wire protocol**, so the Python server
  interoperates natively with a future web editor. The backend stays Python end-to-end; an eventual
  visual editor is a thin client.

---

## 4. Data Flow

### 4.1 A human (or their background agent) edits — live, no merge

```
Human B types  (or Agent B emits a write to api/users.py)
  → applied as a CRDT update in Session B's view
  → Live Sync Engine merges it into the shared project (always-converged)
  → update broadcast to Sessions A, C, D → their views change in real time
  → Presence shows "Agent B editing api/users.py"
  → Semantic Watcher re-checks the touched region (parse/compile/logical)
  → Context Store refreshes api/users.py summary
  → Snapshot Service folds it into the next checkpoint, attributed to Session B
```

No lock was taken. No PR was opened. The change is already part of the shared project.

### 4.2 A real conflict — surfaced to the humans involved

```
Agent A and Agent B edit the SAME function in api/users.py within the same window
  → CRDT converges the TEXT (nothing is lost) ...
  → ... but the Semantic Watcher sees the two edits are logically incompatible
        (e.g. both rewrote validate() with different signatures)
  → Watcher freezes that region and opens a SHARED RESOLUTION CARD
        visible to Human A and Human B (the two involved), showing:
          • A's version + Agent A's stated intent
          • B's version + Agent B's stated intent
          • the broken/contradictory converged result
  → A and B — already online, already in their own sessions — choose between themselves:
          keep A / keep B / a merged third version either agent drafts on request
  → chosen version applied to the live project; region unfrozen; everyone re-syncs
  → decision logged with who-decided-what
```

This is the precise meaning of "conflicts posted to choose between themselves": only the people whose
changes collided are pulled in, into a shared view, and they settle it together.

### 4.3 Cross-session coordination (Frontend needs the Backend's API shape)

```
Agent A: wait_for_signal(topic="user-api", timeout=300s)          ← no human action
Agent B: implements endpoint, then publish_context(contract=user-api-v1)
                                    + signal_ready(topic="user-api")
  → MCP Hub hands Agent A the typed contract; A builds against the real shape
  → the "is the API ready yet?" message never has to be sent
```

---

## 5. The Two-Layer Conflict Model

### 5.1 Layer 1 — Text convergence (CRDT): automatic, lossless

The Live Sync Engine holds the project as a **CRDT** (Conflict-free Replicated Data Type). Properties
that matter:

- **Convergence:** every session's copy is guaranteed identical after updates exchange.
- **No lost edits:** concurrent keystrokes/agent-writes interleave deterministically; nobody's work is
  dropped.
- **No central lock:** sessions edit freely; ordering is resolved by the CRDT, not by waiting.

**Why CRDT over Operational Transform:** both can power real-time editing, but OT needs a central
transform authority and is famously tricky to get right; modern collaborative editors (Yjs/Yrs) are
CRDT-based, and `pycrdt` gives us a battle-tested Python implementation that is wire-compatible with the
JS ecosystem.

### 5.2 Layer 2 — Semantic conflict detection: surfaced to humans

The CRDT guarantees the text *converges*, not that it is *correct code*. The Semantic Conflict Watcher
catches what plain text collaboration never has to:

| Detection | How |
|---|---|
| Won't parse / compile | run the language parser (`ast` for Python; `tree-sitter` elsewhere) on the converged region after each settle |
| Same logical unit, incompatible edits | track which CRDT ranges map to which functions/classes; flag when two sessions wrote the same unit within a window |
| Contradictory intents | agents declare an `intent` with each edit; opposing intents on one unit raise a flag |

On a flag, the Watcher **freezes just that region** and opens a **shared resolution card** to the
involved sessions (§4.2). Everything else in the project keeps flowing — the freeze is surgical, not a
whole-file lock.

### 5.3 Presence as soft conflict-avoidance

Most conflicts never happen because **you can see where everyone is.** Presence shows live: "Agent C is
rewriting `login()` right now." Humans and agents naturally avoid the spot. This is advisory (shown, not
enforced), so it never blocks anyone.

### 5.4 Conflicting *instructions* (not just edits)

If two humans tell their agents contradictory things that affect the same artifact (A: "use Postgres";
B: "use SQLite"), the agents **stop and surface** via `raise_resolution` rather than racing — same
shared-card flow, same "humans choose between themselves." No rank-based auto-winner; an unresolved
decision stays *visibly* paused, never silently guessed.

---

## 6. Multi-Principal Trust Model

> **Stance:** roles and presence set defaults and routing; **humans hold the gavel.** The system
> auto-merges text and surfaces meaning; it never resolves a real conflict by rank.

**System floor (non-negotiable, no role or vote overrides):**
- no access outside the project workspace (path-traversal blocked at the Agent Gateway);
- no direct push to `main`/`master` — durable history is via attributed snapshots;
- a session cannot read another session's private chat or secrets;
- irreversible ops (delete/overwrite of whole files) require a surfaced, explicit decision.

**Above the floor:** conflicting edits or instructions → freeze the affected region / pause the action →
**shared resolution card to the involved humans** → they resolve (talk / pick / record as ADR) →
applied + audited. An agent's default under conflict is **stop and surface**, never **guess and
proceed** — the concrete answer to Fatal Risk III.

---

## 7. Role System (hints, not handcuffs)

Roles route work and set sensible defaults; they never silently wall a human off from helping.

| Role | Default domain | Asks-first to touch |
|---|---|---|
| **Frontend** | `ui/**`, `components/**`, `styles/**`, `pages/**` | backend / infra |
| **Backend** | `api/**`, `services/**`, `db/**`, `middleware/**` | ui / infra |
| **DevOps** | `infra/**`, `*.yml`, `Dockerfile`, `.github/**` | app code |
| **Reviewer** | read-everywhere; edits via proposal | — |

"Asks-first" = the agent calls `propose_cross_domain_edit`, which appears as a lightweight card to the
owning human — collaboration stays open, just visible. Custom roles via a per-project `backyard.toml`.
Enforcement is at each Agent Gateway, before any edit reaches the CRDT.

---

## 8. Shared Context Architecture

Agents in **different sessions** never share conversation history (that would explode every context
window and cost). They share the **live code** plus **structured artifacts**:

- **Interface Contracts** — `{contract_id, endpoints[], types{}}`, published by the producing session.
- **ADRs** — `{title, status, affects[], summary}`, the durable record of a §6 decision.
- **File Summaries** — 2–3 sentences auto-generated after each settle; understand a file without reading
  it.
- **Compressed Activity Log** — every ~10 edits, a cheap Claude call distills recent project activity.

Each agent turn gets a **project briefing** (≤ ~2k tokens): who's online, recent activity, live presence
(who's editing what), available contracts, and any open resolution cards. Bounded cost, constant
situational awareness — the mechanism that makes coordination overhead *fall* (Fatal Risk I). Storage:
Redis (hot: presence, briefings, pub/sub) + Postgres (durable: contracts, ADRs, summaries, audit). No
vector DB in MVP.

---

## 9. Inter-Agent Protocol (MCP)

Each agent's sanctioned channel to the shared project and other sessions is a set of **MCP tools**.

| Group | Tools |
|---|---|
| Context | `query_shared_context`, `publish_context`, `get_file_summary`, `get_project_status` |
| Coordination | `propose_cross_domain_edit`, `request_clarification`, `signal_ready`, `wait_for_signal`, **`raise_resolution`** |
| Editing (gateway-enforced, applied as CRDT updates) | `read_file`, `apply_edit`, `list_files` |
| Review (Reviewer) | `create_review_comment`, `approve_change`, `request_changes` |

`apply_edit` writes through the CRDT so agent edits are live and attributed. `raise_resolution` is the
§5.4 primitive. `wait_for_signal`/`signal_ready` delete the stand-up (§4.3).

---

## 10. Enterprise Pilot — Falsify the Thesis in 4 Weeks

**Scope:** 2 engineers from a real engineering team → **2 separate sessions**, each with **1 background
agent**, all editing **1 live shared project** (CRDT), with presence, audit logging, and semantic-conflict
surfacing. Frontend + Backend roles. Nothing else.

The pilot target is **an existing enterprise engineering team**, not two individuals. Running it inside
a company provides realistic conditions: actual codebase complexity, actual coordination overhead to
measure against, and an actual stakeholder (an Engineering Manager or VP) who can validate whether the
result matters.

| Week | Deliverable |
|---|---|
| **1 — Live core** | FastAPI server; project create; **two separate sessions** join; **`pycrdt` live-sync** of a shared file tree across both sessions; presence (who's editing what); **full audit log from day one** (`engineer, role, agent-turn, timestamp` on every action). |
| **2 — Agents in the loop** | Agent Gateway per session wrapping the Anthropic SDK; **agent edits applied as CRDT updates** (stream live to the other session); project-briefing injection; role-based capability enforcement. |
| **3 — Conflicts** | Semantic Conflict Watcher (parse-check + same-unit detection); **shared resolution card** to both engineers; choose keep-A / keep-B / merged. |
| **4 — Context + measure** | MCP tools (`publish_context`, `query_shared_context`, `signal_ready`, `wait_for_signal`); attributed snapshots to git; session export; **run the experiment** (below). |

**Client:** a Python **Textual** TUI — engineer's agent chat + a live view of the shared project +
presence + resolution cards. (The CRDT server is Yjs-wire-compatible, so a full web editor is a thin
Phase-2 client over the *same Python backend*.)

**Excluded from pilot:** DevOps/Reviewer roles, custom roles, web editor, SSO (deferred to Phase 2),
AST-level merge of incompatible units (pilot surfaces them, doesn't auto-merge).

### 10.1 The pilot experiment (the real deliverable)

Run with **two engineers from the same enterprise team** building the same well-defined feature (a
service endpoint + the UI that consumes it):

- **Arm 1:** two engineers in two Backyard sessions on one live project.
- **Arm 2:** the same two engineers on separate agent sessions, merging via PRs (their current workflow).

Measure **wall-clock to working feature**, **idle-waiting time** (blocked on the other person or a PR
review), and **defects at first integration**.

| Outcome | Reading |
|---|---|
| Backyard measurably faster, less idle | thesis supported; present to engineering leadership; proceed to Phase 2 |
| No difference | inconclusive — identify where the overhead remained; iterate or stop |
| Backyard slower / more friction | thesis disconfirmed **cheaply** — four weeks is the cost of learning this early |

The Engineering Manager's subjective assessment — "would you run the next sprint this way?" — is as
important as the time measurement. A tool that's 20% faster but creates confusion won't be adopted.

---

## 11. Tech Stack (Python)

| Concern | Choice | Why |
|---|---|---|
| Server | **FastAPI + uvicorn** | async, native WebSocket, Pydantic-validated schemas |
| **Live sync (the real-time core)** | **`pycrdt`** (Yjs/Yrs bindings) + **`pycrdt-websocket`** | CRDT convergence, no lost edits; **Yjs-wire-compatible** so a future web editor reuses this exact backend |
| Concurrency | **asyncio** | one loop; natural ordering of updates |
| Presence / pub-sub | FastAPI **WebSocket** + **`redis.asyncio`** | live cursors + fan-out to all sessions |
| Durable store | **Postgres 16** + **SQLAlchemy 2 (async)** + **Alembic** | contracts, ADRs, summaries, audit |
| AI | **`anthropic`** SDK, **`claude-sonnet-4-6`** (raise a session to `claude-opus-4-8` as needed) | streaming + native tool use for background agents |
| Inter-agent | **`mcp`** (official Python SDK) | Claude-native; future CLI can join a project |
| Semantic check | stdlib **`ast`** (Python) + **`tree-sitter`** (multi-language) | parse-validate converged regions; map ranges→units |
| Snapshots | **`GitPython`** | attributed checkpoints of live state |
| Path safety | **`pathspec`** / `os.path.realpath` | block traversal at the Gateway |
| Client (MVP) | **Textual** (+ **Rich**) | full Python TUI: chat + live project view + presence |
| Tests | **pytest** + **pytest-asyncio** + **fakeredis** | CRDT-edit and watcher correctness first |
| Dev infra | **docker-compose** (redis + postgres) | one-command local stack |

**Python vs. TypeScript:** Python is the right call. The one thing that normally argues for JS here —
real-time-collaboration CRDTs live in the JS world — is neutralized by **`pycrdt`**, which is the
Rust/Yjs CRDT with Python bindings and the *same wire protocol* as JS clients. We get the real-time core
in Python today, and any web editor we add later just talks Yjs to this same server.

---

## 12. Proposed Repository Layout

```
backyard/
├── docs/{technical-report,architecture,roadmap}.md
├── src/backyard/
│   ├── server/
│   │   ├── app.py                 # FastAPI entry, WS routes
│   │   ├── project_registry.py    # ① projects ⇄ sessions
│   │   ├── sync/                  # ② Live Sync Engine
│   │   │   ├── crdt_doc.py        #   pycrdt document per project
│   │   │   └── ws_sync.py         #   pycrdt-websocket protocol
│   │   ├── session.py             # ③ per-human session workspace
│   │   ├── gateway.py             # ④ Agent Gateway (Anthropic → CRDT edits)
│   │   ├── watcher/               # ⑤ Semantic Conflict Watcher
│   │   │   ├── parse_check.py     #   ast / tree-sitter validation
│   │   │   ├── unit_map.py        #   CRDT range → function/class map
│   │   │   └── resolution.py      #   shared resolution cards
│   │   ├── context/               # ⑥ shared context store (per project)
│   │   ├── mcp_hub/               # ⑦ MCP tools
│   │   ├── presence.py            # ⑧ cursors + event bus (Redis)
│   │   └── snapshot.py            # ⑨ attributed git checkpoints
│   ├── roles/definitions.py
│   ├── protocol/                  # Pydantic event/message models
│   └── client/                    # Textual TUI
├── tests/                         # pytest (sync + watcher first)
├── infra/docker-compose.yml
├── pyproject.toml
└── README.md
```

**Build order:** `protocol` → `sync` (CRDT live-edit, tested in isolation) → `gateway` (agent edits as
CRDT updates) → `watcher` (semantic conflicts) → `mcp_hub` → `client`. The sync engine and watcher are
the riskiest surfaces (Fatal Risks II & IV) and come first.

---

## 13. Roadmap

- **Phase 1 — Pilot (4 wks):** §10. *Does the team ship faster? Does coordination overhead fall?* Audit
  log from day one. Target: one real enterprise engineering team.
- **Phase 2 — Platform (3 mo):** all roles; web editor with live cursors; org-wide admin dashboard;
  **SSO/SAML** (enterprise requirement, moved forward); compliance audit exports; CI/CD hooks; AST-level
  merge suggestions; RBAC + org-level role schemas; load test to ~20 concurrent sessions; closed beta
  with 3–5 enterprise customers.
- **Phase 3 — Enterprise GA (6 mo):** **private-cloud and on-premise deployment** (non-negotiable for
  regulated industries); Kubernetes session isolation; SOC 2 Type II; SCIM provisioning; custom
  data-retention policy; issue-tracker (Linear/Jira) → project workflow; role-template marketplace;
  async mode (agent works while an engineer is in a different timezone, briefs them on return); GA with
  enterprise pricing (§15).

---

## 14. The Five Fatal Risks → Mitigations

| # | Risk | Mitigation |
|---|---|---|
| **I** | Coordination overhead *rises* | always-merged live project + presence + `signal_ready`/`wait_for_signal` remove the merge step and the stand-up; **§10.1 measures it** and kills the project if overhead doesn't fall. |
| **II** | Concurrent edits lose work | **CRDT guarantees convergence and lost-edit-freedom** at the text layer; the sync engine is tested exhaustively before any real project. |
| **III** | Multi-principal trust unsafe | agents **stop and surface** under conflict; hard System floor no human/vote can cross. |
| **IV** | Conflict resolution slow/confusing | most collisions auto-converge (CRDT) and never bother anyone; only *semantic* conflicts surface — to the involved humans, in a shared card, with a surgical region freeze. |
| **V** | No revenue path | §15. |

---

## 15. Revenue Model (Enterprise)

Backyard is an **enterprise product**. There is no individual or free tier. The buyer is an
organization — a CTO, VP of Engineering, or Head of Platform — purchasing on behalf of their engineering
team. The sales motion is enterprise B2B: pilot → expansion.

Charge for the **collaboration layer and the operational guarantee**; pass model tokens through at cost
(shown per session, attributable per engineer for internal chargebacks). The value sold is real-time
team coordination, semantic conflict resolution, shared context management, full audit logging, and
compliance controls — not the AI API call.

**Pricing structure:**

| Tier | Target | Price | What's included |
|---|---|---|---|
| **Team** | Startup or small org (10–50 engineers) | ~$75/seat/mo, annual | Unlimited projects, all roles, web editor, CI hooks, session history, shared-context store, audit log |
| **Enterprise** | Mid-to-large org (50–500+ engineers) | ~$150/seat/mo, annual | Everything in Team + **SSO/SAML**, **SCIM provisioning**, **SOC 2 audit reports**, **private-cloud deployment**, dedicated SLA, account manager |
| **Enterprise+** | Regulated industries / large platforms | Custom contract | Everything in Enterprise + on-premise deployment, custom data-retention policy, custom role schemas, professional services |

**On private/on-premise deployment:** for many enterprise buyers — especially in financial services,
healthcare, and defense — the requirement that code never leaves their infrastructure is non-negotiable.
Private deployment is therefore an Enterprise tier feature, not a Phase-3 add-on. The Python stack and
`pycrdt` make this straightforward: the coordination server is a standard Python application with no
proprietary cloud dependencies.

**Token cost reality:** a 1-hour session with 4 agents averaging 10 turns each ≈ 80k tokens at current
rates. This is cents, not dollars. The cost of the *coordination* — the Backyard platform — is the
product; the model API cost is a pass-through at cost, shown transparently per session, and attributable
to each engineer for internal reporting.

**Why no free tier:** enterprise buyers don't adopt collaboration infrastructure through a free tier —
they run a **pilot** (§10). The pilot *is* the top-of-funnel. A free tier would attract individual
developers, generate support load, and dilute the enterprise signal. It is a distraction from the
actual buyer.

---

## 16. Open Questions

1. **Live-edit granularity:** keystroke-level CRDT for *everyone* (humans + agents), or agents land
   edits as atomic patches while humans type live? (Recommended: CRDT for both; agents emit edits as
   CRDT updates so they stream like a fast collaborator.)
2. **Session privacy:** confirm humans see each other's *code edits + presence* but **not** each other's
   agent chat. (Recommended: yes.)
3. **Snapshot cadence:** time-based, on milestones, on every settle, or human-triggered "commit point"?
4. **Resolution scope:** does a §5 decision bind just the region now, or persist as an ADR constraining
   future edits? (Recommended: human picks "just this" vs. "record as ADR" on the card.)

---

## 17. Conclusion

The product is one shared project that the whole team contributes to at once, in real time — each person
logging into their own private session with their own background agent, with conflicts surfaced to the
people involved to settle between themselves. The architecture above makes that buildable in Python
today: a CRDT live-sync core (`pycrdt`) for the always-merged guarantee, a semantic watcher for the one
thing code needs that prose doesn't, and a per-session agent at every seat.

The next move is §10 — two humans, two sessions, two background agents, one live project, four weeks —
and the experiment in §10.1 to learn whether the empty quadrant is empty because it's hard, or because
no one with the right incentives has tried.

---

## References

- M. Reddy, *The Unbuilt Product*, white paper, June 2026.
- Yjs / Yrs — CRDT framework for real-time collaboration; `pycrdt` Python bindings.
- Model Context Protocol — specification and Python SDK (`mcp`).
- Anthropic, *Claude Code Agent Teams* — multi-agent coordination (2026).
