# Backyard — Multi-Human, Multi-Agent Collaborative Coding

**A technical design for the "unbuilt product."**
Companion to the white paper *The Unbuilt Product* (M. Reddy, June 2026).
Version 0.1 · Status: Design · Stack: Python

---

## 0. Executive Summary

The white paper establishes the gap: every AI coding agent assumes **one human per session**, yet
software is built by teams. **Backyard** is the design for the missing quadrant — *many humans, many
agents, one shared project, in real time*.

A backyard is a shared space a household works in together. The product is exactly that: a shared
workspace where each engineer keeps their own AI agent, but all of them see one another's work as it
happens, coordinate through the agents instead of through pull requests, and resolve disagreements
**together, out loud, in one session** rather than days later in code review.

This report specifies the system end-to-end: components, data flow, the conflict-resolution engine,
the multi-principal trust model, the role system, shared-context management, the inter-agent protocol,
a 4-week MVP that falsifies the core hypothesis as cheaply as possible, the Python tech stack, and a
phased roadmap. Every one of the white paper's **five fatal risks** is mapped to a concrete mitigation.

**The one question the MVP must answer:** *Do two humans driving agents in one shared session ship
faster than two humans on separate sessions merging through pull requests?* Everything else follows
from that result.

---

## 1. Problem & Thesis

### 1.1 What's broken

The pull-request model predates AI agents by two decades. It was designed so that *humans* working in
*isolation* could reconcile their work *asynchronously*. AI agents inherited this model unquestioned.
The result, for a team using agents today:

- **Context is lost at every boundary.** Human A's agent reasons through a decision; Human B sees only
  the diff, hours later, with none of the reasoning.
- **Coordination is out-of-band.** "Is the API ready?" is a Slack message or a stand-up, not something
  the agents can answer for each other.
- **Mentorship is scheduled, not ambient.** A senior reviews *after* the work, never *during*.
- **Handoffs re-pay context cost.** Across time zones, the first hour of every handoff is
  re-explanation.

### 1.2 Thesis

If multiple humans share **one live session** in which each has their **own agent**, and the agents
coordinate through a shared substrate, then the coordination that today costs meetings and PR latency
collapses to near-zero human time — *provided* concurrent edits and conflicting instructions are
resolved fast and obviously. Backyard is the architecture that makes that provision true.

### 1.3 Non-goals

- Not a multi-agent orchestrator for *one* human (that is Anthropic's Agent Teams — the inverse problem).
- Not a Google-Docs-style character-by-character co-editor of source (that ignores code semantics).
- Not a replacement for git history — it *produces* clean git history as a byproduct.

---

## 2. Design Principles

1. **One session, many principals.** The session — not the user — is the top-level object. Everything
   (locks, context, audit, billing) hangs off the session, not off a single account.
2. **Conflicts are social, resolved socially.** A collision is surfaced into the shared session and the
   humans decide together. The system's job is to *detect fast, present clearly, apply faithfully* — not
   to pick a winner behind their backs.
3. **Agents coordinate through a substrate, never by reading each other's minds.** No agent ingests
   another agent's raw conversation. They exchange **structured artifacts** (contracts, decisions, file
   summaries, signals) through a shared store. This keeps context windows small and costs bounded.
4. **Roles are hints, not handcuffs.** Domain ownership routes work and sets defaults; it never silently
   blocks a human from helping elsewhere — it just asks first, in the open.
5. **Local-first, server-coordinated.** The repo and edits live on participants' machines / a shared
   workspace; the server coordinates state. This keeps trust and latency low and gives a clean paid-tier
   boundary (hosted coordination).
6. **Falsifiable before fancy.** Build the cheapest thing that can disprove the thesis. Resist every
   feature that doesn't help answer the core question.

---

## 3. System Architecture

### 3.1 The seven components

```
                         ┌───────────────────────────────────────────────┐
                         │            BACKYARD SESSION SERVER             │
                         │           (Python · FastAPI · asyncio)         │
                         │                                               │
   Human A ─ CLI/TUI ◄──►│  ① Session Orchestrator   ② Agent Gateway(×N) │
   Human B ─ CLI/TUI ◄──►│  ③ Conflict Resolver      ④ Shared Context    │
   Human C ─ CLI/TUI ◄──►│  ⑤ MCP Hub                ⑥ Workspace/Git Svc │◄──► Shared
                         │  ⑦ Event Bus + Audit Log                      │     Git Repo
                         └───────────────────────────────────────────────┘
                                          │
                                   Redis (locks, pub/sub, hot state)
                                   Postgres (history, contracts, audit)
```

**① Session Orchestrator** — the single source of truth for *who is in the session, what role they
hold, what each agent is doing, and what is locked*. A state machine; one logical instance per session.

**② Agent Gateway (one per human-agent pair)** — wraps the Anthropic API for that human's agent.
Injects the shared **session briefing** into each turn, streams the agent's output to *all*
participants, and **intercepts every tool call** (file writes, shell) before it runs to enforce roles
and route through the Conflict Resolver. This is the trust boundary; its correctness is load-bearing.

**③ Conflict Resolver (CRE)** — receives every proposed file mutation, detects collisions via
per-file vector clocks + 3-way diff, **auto-merges only line-disjoint changes**, and **escalates
everything else into the shared session** for the humans to settle.

**④ Shared Context Store** — a *structured* store (not a vector DB) of contracts, architecture
decisions (ADRs), and auto-generated file summaries. The thing agents read to understand each other.

**⑤ MCP Hub** — exposes the coordination API to every agent as Model Context Protocol tools
(`publish_context`, `wait_for_signal`, `propose_cross_domain_edit`, …). MCP is chosen so that, in
time, a stock Claude Code CLI can join a Backyard session by pointing at this server.

**⑥ Workspace & Git Service** — owns the filesystem and all git operations. No agent touches git
directly; every commit flows through here, tagged with `(session, role, agent-turn)` metadata, on
per-role branches that periodically integrate.

**⑦ Event Bus + Audit Log** — every state change is an event, fanned out to all clients (live UI) via
Redis pub/sub and persisted to Postgres (replay, audit, billing attribution).

### 3.2 Why this shape

- The **session as top-level object** is the single architectural decision that removes the
  "single-principal assumption" the white paper identifies as load-bearing. Locks, context, audit, and
  billing all key off `session_id + participant_id`, never a lone account.
- **One Gateway per agent** keeps each agent's context isolated and its costs attributable, while the
  shared Orchestrator + Context Store give them common ground without a shared context window.

---

## 4. Data Flow

### 4.1 Clean edit (no collision)

```
Human A: "add email validation to the signup form"
  → Agent Gateway A injects session briefing, calls Claude (streaming)
  → Claude emits tool_use: write_file("ui/signup.py", <content>)
  → Gateway A intercepts → role check (A owns ui/**) → OK
  → CRE: lock signup.py (Redis SETNX), vector clock fresh → grant
  → write applied in shared workspace; Git Svc commits to session/<id>/frontend
  → FILE_CHANGED event → Event Bus → B's and C's terminals update live
  → Context Store regenerates signup.py summary; briefing for others refreshed
  → lock released
```

### 4.2 Collision (two agents target one file) — **surfaced to the session**

```
Agent A and Agent B both propose writes to api/users.py within ~200ms
  → CRE grants A's lock, records B's proposal against A's vector clock
  → CRE computes 3-way diff [base, A, B]:
       • disjoint lines  → auto-merge, apply both, done (no human bother)
       • overlapping     → CONFLICT raised INTO THE SHARED SESSION
  → Both humans see one conflict card in their terminals:
       "api/users.py — A wants X, B wants Y (same lines). Decide together."
       side-by-side diff, with each agent's stated intent
  → A and B talk it out in the session (they're both right here, right now)
       and pick: keep A / keep B / a merged third option either agent drafts
  → CRE applies the chosen result, releases lock, emits FILE_RESOLVED
```

No timer silently picks a winner. The humans are *already in the room* — that is the whole point of the
product, and the resolution flow leans on it.

### 4.3 Cross-agent information (Frontend needs the API shape)

```
Agent A: wait_for_signal(role="backend", milestone="user-api", timeout=300s)   ← no human action
Agent B: implements endpoint, then publish_context(contract=user-api-v1)
                                     + signal_ready(milestone="user-api")
  → MCP Hub resolves A's pending wait, hands A the typed contract
  → A builds against the real shape; the "is the API ready?" stand-up never happens
```

Agents never exchange raw reasoning — only the structured contract crosses the boundary.

---

## 5. Conflict Resolution Engine (CRE)

### 5.1 Algorithm choice

| Option | Verdict |
|---|---|
| **CRDTs** | Eventually consistent, no central authority — but *lose code semantics*; auto-merging two conflicting function bodies is meaningless. ✗ as the primary mechanism |
| **Operational Transform** | Needs a central serializer — which we *have* (Orchestrator) — but is painful for tree-structured code and overkill for MVP. Defer. |
| **3-way merge + human escalation** | Exactly what git does: auto-merge the easy case, **escalate the hard case to humans**. Matches Principle 2. ✓ **chosen** |

### 5.2 Per-file vector clocks

Each file carries `{role: seq}`. An agent reads at a clock, proposes a write tagged with it; the CRE
compares against the file's current clock to know **what the agent saw**, **whether someone wrote since**,
and **the correct 3-way base**. This is what makes "disjoint vs. overlapping" decidable.

### 5.3 Lock schema (Redis)

```
key:   lock:{session}:{path}
value: {role, participant, acquired_at, intent}   # intent = "adding email validation"
ttl:   30s, renewed every 10s while the agent is actively writing
```

SETNX for atomicity; TTL means a crashed agent frees its lock in ≤30s (vs. minutes for a DB-connection
lock). The human-readable `intent` is shown to others so a lock explains *why*, not just *that*.

### 5.4 Conflict classes & policy

| Class | Example | Policy |
|---|---|---|
| **A — Structural** | imports, type/signature defs | auto-merge if disjoint; else → session |
| **B — Logic** | function bodies, conditionals | **always → session** (never auto-pick) |
| **C — Formatting** | whitespace, trailing commas | accept later write silently |
| **D — Generated** | lockfiles, `dist/`, migrations | exclusive to owning role; others can't write |

### 5.5 Python implementation notes

- 3-way merge: **`merge3`** (pure-Python diff3) or shell out to **`git merge-file`** (battle-tested,
  already a dependency via the Git Service). MVP uses `git merge-file`; swap to `merge3` if finer
  control is needed.
- AST-aware detection (Phase 2): Python's stdlib **`ast`** for `.py`, **`tree-sitter`** for everything
  else — catches "both added a `def login()`" even on different lines.
- The CRE is a **pure, isolated module** with no I/O beyond Redis — it is the hardest correctness
  problem and must be unit-tested to death *before* it ever touches a real session (Fatal Risk II).

---

## 6. Multi-Principal Trust Model

> **Core stance:** when humans give the agent(s) conflicting instructions, the system does **not**
> auto-resolve by rank. It **posts the conflict into the one shared session and the humans choose
> between themselves.** Roles set defaults and routing; humans hold the gavel.

### 6.1 Three things that are *not* negotiable (System level)

A thin floor of hard rules no role or vote can override — these are safety, not policy:
- no file access outside the session workspace (path-traversal blocked at the Gateway);
- no direct push to `main`/`master` — integration happens on session branches;
- no reading another participant's secrets/environment;
- destructive ops (delete/overwrite of shared files) always pass through the CRE.

### 6.2 Everything above the floor is human-decided

```
Conflicting human instructions detected
   (e.g. A: "use Postgres"   B: "use SQLite";
         A: "remove the auth middleware"   B: "never remove auth")
        │
        ▼
   Agents PAUSE the affected action  (they do not race ahead, they do not negotiate with each other)
        │
        ▼
   DECISION CARD posted into the shared session, visible to all:
     • what each human asked for, verbatim
     • which artifact/domain it touches (and who nominally owns it — a hint, not a verdict)
     • the agent's read of the trade-off
        │
        ▼
   Humans resolve, in the open, by any of:
     • talk + one person sets the decision      (default, fastest — they're already here)
     • quick vote among present participants     (when it's genuinely a judgment call)
     • record it as an ADR                       (when it should bind future turns)
        │
        ▼
   Decision applied; logged to audit with who-decided-what; agents resume
```

There is **no silent timer-winner**. If nobody decides, the action simply stays paused — a stuck
decision is a *visible* stuck decision, not a wrong action taken quietly. (A team may *opt in* to a
"domain-owner breaks ties after N minutes" convenience later, but it is off by default and always
logged.)

### 6.3 What each agent is told (system prompt skeleton)

```
You are the {ROLE} agent for {human} in a shared multi-human session {id}.
Other participants: {role:human, domain} …
Ground rules:
  • Before editing outside your domain, call propose_cross_domain_edit — do not just do it.
  • Use query_shared_context / publish_context to stay in sync; never assume another role's shape.
  • If your human's instruction conflicts with what another human told their agent,
    STOP the affected step and call raise_session_decision — the humans will settle it together.
  • Never take a destructive or irreversible action without an explicit, surfaced decision.
```

This is the concrete answer to the white paper's Fatal Risk III (multi-principal trust): the agent's
default under conflicting principals is **stop and surface**, never **guess and proceed**.

---

## 7. Role System

### 7.1 Built-in roles (domains are *defaults/hints*, not hard walls)

| Role | Default domain | Can | Asks-first to |
|---|---|---|---|
| **Frontend** | `ui/**`, `components/**`, `styles/**`, `pages/**` | edit domain, run FE tests, propose API contracts | touch backend/infra |
| **Backend** | `api/**`, `services/**`, `db/**`, `middleware/**` | edit domain, run BE tests, publish API contracts, own migrations | touch UI/infra |
| **DevOps** | `infra/**`, `*.yml`, `Dockerfile`, `.github/**` | edit domain, run all CI, trigger deploys | touch app code |
| **Reviewer** | read-everywhere | comment, request changes, record ADRs, raise decisions | (writes via proposals only) |

"Asks-first" = the agent calls `propose_cross_domain_edit`, which **posts into the session** for the
owning human to wave through — consistent with §6: collaboration is open, not blocked.

### 7.2 Custom roles

A session config (`backyard.toml`) can declare arbitrary roles: a name, glob domains, and a capability
subset. Stored with the session; no code change needed.

### 7.3 Enforcement point

The Agent Gateway checks every tool call against the role policy *before* execution
(`fnmatch`/`pathspec` on the path for writes; capability set for everything else). Out-of-domain writes
aren't rejected — they're **redirected** to the proposal flow.

---

## 8. Shared Context Architecture

### 8.1 The trap to avoid

Naively sharing every agent's conversation history would exhaust each context window in minutes and
cost a fortune. So agents **do not** share histories. They share **structured artifacts**.

### 8.2 The four artifact types

- **Interface Contracts** — published by the producing role, consumed by others
  (`{contract_id, endpoints[], types{}}`).
- **Architecture Decisions (ADRs)** — `{title, status, affects[], summary}`; the durable record of a
  §6 decision.
- **File Summaries** — 2–3 sentences auto-generated after each write (`{path, summary, exports[],
  last_by, clock}`); lets an agent understand a file without reading it.
- **Compressed Session Log** — every ~10 turns a cheap Claude call distills recent activity to bullets.

### 8.3 The session briefing (≤ ~2k tokens, injected each turn)

```
=== SESSION BRIEFING (auto) ===
Elapsed: 47m · Present: Frontend(A), Backend(B), Reviewer(C)
Recent:  B added GET /api/users, published user-api-v1
         A built UserCard.py
Contracts: user-api-v1 → GET /api/users/:id → UserDTO
Locks:   db/schema.py (B, editing migration)
Open decisions: none
=== END ===
```

Constant situational awareness, bounded cost. This is the mechanism that makes coordination overhead
*fall* instead of rise (Fatal Risk I).

### 8.4 Storage

Redis (hot: locks, briefings, clocks, pub/sub) + Postgres (durable: contracts, ADRs, summaries, audit).
**No vector DB in MVP** — queries are structured (by role/path/contract-id), which is faster, cheaper,
and never stale within a fast session. Semantic search is a Phase-2 cross-session concern.

---

## 9. Inter-Agent Protocol (MCP)

Every agent's only sanctioned channel to the rest of the session is a set of **MCP tools** served by
the Hub. Chosen over a bespoke protocol because Claude Code already speaks MCP — the long-term payoff is
that a user's existing CLI can join a Backyard session natively.

| Group | Tools |
|---|---|
| Context | `query_shared_context`, `publish_context`, `get_file_summary`, `get_session_status` |
| Coordination | `propose_cross_domain_edit`, `request_clarification`, `signal_ready`, `wait_for_signal`, **`raise_session_decision`** |
| Files (gateway-enforced) | `read_file`, `write_file`, `list_files` |
| Review (Reviewer only) | `create_review_comment`, `approve_merge`, `request_changes` |

`raise_session_decision` is the §6 primitive: it pauses the agent and posts a decision card to the
humans. `wait_for_signal`/`signal_ready` are the §4.3 primitive that deletes the stand-up.

---

## 10. MVP — Falsify the Thesis in 4 Weeks

**Scope:** 2 humans, 2 agents, 1 repo, **Frontend + Backend** roles only. File-level locking. Shared
live transcript in a terminal client. Conflicts surfaced to the session. Nothing else.

| Week | Deliverable |
|---|---|
| **1 — Spine** | FastAPI server; session create/join over WebSocket; Agent Gateway wrapping the Anthropic Python SDK with briefing injection + `write_file` interception; Redis lock service (SETNX + TTL). |
| **2 — CRE** | per-file vector clocks; 3-way merge via `git merge-file`; auto-merge disjoint; **conflict card surfaced to both terminals** with side-by-side diff + one-key choose. |
| **3 — Context** | file-summary generation after writes; briefing injection; MCP tools `publish_context`, `query_shared_context`, `signal_ready`, `wait_for_signal`. |
| **4 — Git + measure** | per-role branches, auto-commit with session metadata; session export (what was built, by whom, elapsed); **the experiment** (below). |

**Excluded from MVP:** DevOps/Reviewer roles, custom roles, ADR system, CI integration, web dashboard
(terminal only), billing, AST diffing.

**Client:** a Python **TUI** built with **Textual** (or Rich) — keeps the entire stack in Python, fits
the white paper's "shared transcript + file-level locking and nothing else," and avoids a JS frontend.

### 10.1 The experiment (this is the actual deliverable of the MVP)

Run the *same* small feature (a CRUD resource with a UI) two ways:
- **Arm 1:** two engineers in one Backyard session.
- **Arm 2:** the same two engineers on separate agent sessions, merging via PRs.

Measure **wall-clock to working feature**, **idle-waiting time**, and **defects at first integration**.

| Outcome | Reading |
|---|---|
| Backyard meaningfully faster, less idle | thesis supported — proceed to Phase 2 |
| No difference | inconclusive — investigate where overhead landed |
| Backyard slower / more friction | **thesis disconfirmed cheaply** — stop, write it up honestly |

A negative result is a *successful* MVP: it cost four weeks instead of a company.

---

## 11. Tech Stack (Python)

| Concern | Choice | Why |
|---|---|---|
| Server | **FastAPI + uvicorn** | first-class async, native WebSocket, Pydantic-validated event schemas |
| Concurrency | **asyncio** | one event loop naturally serializes lock ops |
| Real-time | FastAPI **WebSocket** + **`redis.asyncio`** pub/sub | fan-out to all participants |
| Hot state / locks | **Redis 7** (SETNX, TTL, keyspace events) | sub-ms locks; crash-safe via TTL |
| Durable store | **Postgres 16** + **SQLAlchemy 2 (async)** + **Alembic** | contracts, ADRs, audit; relational fits |
| AI | **`anthropic`** Python SDK, **`claude-sonnet-4-6`** (option to raise a role to `claude-opus-4-8`) | streaming + native tool use |
| Inter-agent | **`mcp`** (official Python MCP SDK) | Claude-native; future CLI can join |
| 3-way merge | **`git merge-file`** (MVP) → **`merge3`** | proven; matches git semantics |
| AST diff (Ph2) | stdlib **`ast`** + **`tree-sitter`** | semantic conflict detection |
| Git ops | **`GitPython`** (or `subprocess` git) | per-role branches, tagged commits |
| Path safety | **`pathspec`** / `os.path.realpath` checks | block traversal at the Gateway |
| Client TUI | **Textual** (+ **Rich**) | full app in Python, live shared transcript |
| Tests | **pytest** + **pytest-asyncio** + **fakeredis** | CRE and lock correctness first |
| Dev infra | **docker-compose** (redis + postgres) | one-command local stack |
| Packaging | **uv** / **pyproject.toml**, **ruff** + **mypy** | fast installs, typed, linted |

**On Python vs. TypeScript:** for *this* product, the honest answer is **either works, and Python is
the right call here** — every piece we need exists first-class in Python (FastAPI WebSockets,
`redis.asyncio`, the `anthropic` and `mcp` SDKs, Textual for the client). TypeScript's only real edge is
that Claude Code's own client internals are JS, which would matter if we wanted the stock CLI to join on
day one — but that's a Phase-2 nicety, not an MVP need.

---

## 12. Proposed Repository Layout (for the eventual build)

```
backyard/
├── docs/
│   ├── technical-report.md          # this document
│   ├── architecture.md              # §3–§9 reference
│   └── roadmap.md                   # §13
├── src/backyard/
│   ├── server/
│   │   ├── app.py                   # FastAPI entry, WS routes
│   │   ├── orchestrator.py          # ① session state machine
│   │   ├── gateway.py               # ② Agent Gateway (Anthropic + interception)
│   │   ├── cre/                     # ③ conflict resolver
│   │   │   ├── engine.py
│   │   │   ├── vector_clock.py
│   │   │   ├── merge.py             # git merge-file / merge3
│   │   │   └── locks.py             # Redis SETNX + TTL
│   │   ├── context/                 # ④ shared context store
│   │   ├── mcp_hub/                 # ⑤ MCP tools
│   │   ├── workspace.py             # ⑥ git + fs isolation
│   │   └── bus.py                   # ⑦ event bus + audit
│   ├── roles/definitions.py
│   ├── protocol/                    # Pydantic event/message models
│   └── client/                      # Textual TUI
├── tests/                           # pytest (cre first)
├── infra/docker-compose.yml
├── pyproject.toml
└── README.md
```

**Build order (when implementing):** `protocol` models → `cre` (in isolation, fully tested) →
`gateway` → `orchestrator` → `mcp_hub` → `client`. The CRE is first because it is the riskiest
correctness surface (Fatal Risk II).

---

## 13. Roadmap

- **Phase 1 — MVP (4 wks):** §10. *Does collaboration beat PRs?*
- **Phase 2 — Platform (3 mo):** DevOps + Reviewer roles, cross-domain proposal flow, ADRs, AST-aware
  conflict detection, session reconnect, RBAC + invite-per-role, a thin web dashboard, CI webhook into
  the session, load test to ~10 concurrent sessions, closed beta with ~20 teams.
- **Phase 3 — Product (6 mo):** session isolation on Kubernetes, SSO/SAML, audit/retention for SOC 2,
  private-cloud deploy, role-template marketplace, async mode (agent works while a human is away, briefs
  them on return), issue-tracker → session workflow, GA + pricing.

---

## 14. The Five Fatal Risks → Mitigations

| # | Risk (white paper) | Mitigation in this design |
|---|---|---|
| **I** | Coordination overhead *rises* | §8 briefing + §9 `signal_ready`/`wait_for_signal` delete the stand-up; **§10.1 measures it directly** and kills the project if it doesn't drop. |
| **II** | Concurrent-edit merge loses work | §5 CRE: vector clocks + 3-way merge, **auto-merge only the disjoint case**, everything else escalates; CRE is a pure module **tested exhaustively before any real session**. |
| **III** | Multi-principal trust unsafe | §6: agents **stop and surface** under conflicting principals — never guess; a hard System floor (§6.1) that no human or vote can cross. |
| **IV** | Conflict resolution slow/confusing | §4.2 + §6.2: one card, side-by-side, decided by humans **who are already in the room** — the product's core advantage *is* the resolution UX. |
| **V** | No revenue path | §15. |

---

## 15. Revenue Model

Charge for the **coordination layer**, pass model tokens through at cost (shown transparently
per-session). A 1-hour, 4-agent session ≈ 80k tokens ≈ cents — the value sold is orchestration,
conflict resolution, shared context, audit, not the API call.

- **Free:** 1 active session, 2 humans, built-in roles, terminal client.
- **Team — ~$49/seat/mo:** unlimited sessions, all roles, history, CI hooks, web dashboard.
- **Enterprise — ~$149/seat/mo:** custom roles, SSO, audit/retention, private-cloud, SLA.

The local-first/self-host build is the free on-ramp; **hosted coordination + collaboration features are
the paid boundary** — which is exactly why the boundary must be drawn before the first line of code
(Fatal Risk V), and it is.

---

## 16. Open Questions (to settle before/early in the build)

1. **Workspace topology:** one shared workspace on the server, or each human's local checkout kept in
   sync? (MVP leans shared-server for simplicity; local-first is the Phase-3 trust story.)
2. **Decision bindingness:** does a §6 decision bind only the current action, or persist as an ADR that
   constrains future turns? (Proposed: human chooses "just this" vs. "record as ADR" on the card.)
3. **Reviewer-as-driver:** can the Reviewer ever write directly in an emergency, or always via proposal?
4. **Token attribution granularity:** per-human is clear; do we also attribute *shared* calls
   (briefing compression, file summaries) — split evenly, or to the session?

---

## 17. Conclusion

The white paper named an empty quadrant and argued, convincingly, that incumbents are structurally
unlikely to fill it. This report turns that argument into a buildable system: a Python, session-first
architecture where many humans keep their own agents, coordinate through a structured substrate instead
of pull requests, and **settle their disagreements together, in the open, in one shared session** — the
exact behavior the product exists to enable.

The next move is not to build all of it. It is to build §10 — two humans, two agents, one repo, four
weeks — and let the experiment in §10.1 tell us whether the quadrant is empty because it's hard, or
empty because no one with the right incentives has tried.

---

## References

- M. Reddy, *The Unbuilt Product*, white paper, June 2026.
- VILA-Lab, *Dive-into-Claude-Code* — architecture analysis.
- Anthropic, *Claude Code Agent Teams* — multi-agent coordination capability (2026).
- Model Context Protocol — specification and Python SDK (`mcp`).
