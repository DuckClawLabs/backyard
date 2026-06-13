# Backyard — Google Docs for AI-Assisted Coding

**Multiple humans, each with their own background AI agent, editing one live shared project in real time.**
Companion to the white paper *The Unbuilt Product* (M. Reddy, June 2026).
Version 0.2 · Status: Design · Stack: Python

---

## 0. Executive Summary

The white paper establishes the gap: every AI coding agent assumes **one human per session**, yet
software is built by teams. **Backyard** fills the missing quadrant with a specific shape:

> Many humans log in. **Each gets their own private session with their own background agent.** All of
> those sessions edit **one live shared project at the same time — like Google Docs.** Every human's
> edits, and every agent's edits, appear live for everyone. When two changes truly conflict, the
> collision is surfaced to the humans involved and they **choose between themselves.**

The mental model is exact: **Google Docs, but the document is a codebase and every editor has an AI
agent working alongside them in the background.** Google Docs solved real-time collaboration for prose
with no pull requests, no merge step, no "who has the file open." Backyard does the same for code — and
adds a per-person agent to each seat.

This report specifies the system end-to-end: the project-centric architecture, the live-sync engine
(CRDT), how separate sessions and background agents share one project, the two-layer conflict model
(automatic text convergence + human-resolved semantic conflicts), the trust model, roles, shared
context, the inter-agent protocol, a 4-week MVP, the Python stack, and a phased roadmap — with every one
of the white paper's **five fatal risks** mapped to a concrete mitigation.

---

## 1. The Core Idea (and how it differs from "shared session")

### 1.1 Project-centric, not session-centric

The unit everyone shares is the **Project** — the live codebase. It is the Google Doc.

Each human has their **own Session**: their private chat, their own context, and their own **background
agent(s)** working on their behalf. Sessions are *isolated from each other* — you don't read someone
else's conversation — exactly as in Google Docs you see others' edits and cursors but not their private
notes.

```
                          ┌──────────── ONE LIVE PROJECT ────────────┐
                          │      (the shared codebase = the Doc)      │
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

### 1.2 Three things this gets right that pull requests don't

- **No merge step.** Like Google Docs, the shared state is *always already merged*. There is no "open a
  PR, wait, resolve conflicts, merge" — your edits and your agent's edits land in the live project as
  they happen.
- **Everyone sees everything, live.** Human C watches Human A's agent refactor a module in real time,
  not in a diff three hours later. Context is never reconstructed.
- **Agents work in the background, per person.** Each human's agent is doing real work autonomously
  inside that human's session; its output flows into the shared project the same way the human's own
  keystrokes do.

### 1.3 The one hard problem this creates

Google Docs works because *any* interleaving of prose edits is still valid prose. **Code is not prose:**
two cleanly-merged edits can produce a file that does not compile or that is logically contradictory.
So Backyard needs **two layers** (see §5):

1. **Text convergence** — guarantees everyone's view is identical and no keystroke is ever lost
   (this is the CRDT, the Google Docs guarantee).
2. **Semantic conflict detection** — notices when the converged code is broken or two sessions changed
   the same logical unit incompatibly, and **surfaces it to the humans involved to choose between
   themselves.**

---

## 2. Design Principles

1. **The project is the shared object; sessions are private.** Locks, presence, and history hang off
   the **project**; chat, context, and agent state hang off each human's **session**.
2. **Always-merged, never-blocked.** Real-time convergence (CRDT) means there is no merge step and no
   file you must wait for. Editing is live, like Google Docs.
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

**② Live Sync Engine (CRDT)** — *the Google Docs core.* Holds the shared codebase as a CRDT document.
Every edit — from a human's keystrokes or their background agent — is a CRDT update that converges on
every session with no lost work and no merge step. Built on **`pycrdt`** (Python bindings to Yjs/Yrs).

**③ Session Workspace (one per human)** — a human's private space: their chat history, their context,
their cursor/presence, and a live view of the shared project. Isolated from other sessions.

**④ Agent Gateway (one per session)** — wraps the Anthropic API for that human's **background agent**.
The agent's file edits are applied *as CRDT updates*, so they stream into the live project exactly like
human edits and are attributed to that session.

**⑤ Semantic Conflict Watcher** — sits above the CRDT. Detects when converged state is broken
(won't parse/compile) or when two sessions changed the same logical unit incompatibly, and raises a
**shared resolution card** to the involved humans. This is the code-specific layer Google Docs doesn't
need.

**⑥ Shared Context Store (per project)** — structured contracts, ADRs, and auto-generated file
summaries — how agents across different sessions understand the one shared project.

**⑦ MCP Hub** — exposes coordination tools to every agent as MCP tools (`publish_context`,
`wait_for_signal`, `raise_resolution`, …). MCP so a stock Claude Code CLI can eventually join a project.

**⑧ Presence + Event Bus** — live cursors, "who/which agent is editing what," and activity feed; Redis
pub/sub fan-out to all sessions. The Google-Docs "see everyone's cursor" layer.

**⑨ Snapshot / Git Service** — periodically and on milestones, checkpoints the live CRDT state into git
with per-change attribution `(session, human, agent)`. Git is the durable history and the export, not
the live working mechanism.

### 3.2 Why this shape

- Making the **project** the top-level object is what removes the white paper's load-bearing
  "single-principal assumption": presence, history, and context key off the project; many sessions
  attach to it.
- A **CRDT** is the right primitive because it is *exactly* what Google-Docs-class editors use, it
  guarantees convergence without a central lock, and — crucially for a Python team — **`pycrdt` speaks
  the Yjs wire protocol**, so the Python server interoperates natively with a future Monaco/Yjs web
  editor. The backend stays Python end-to-end; the eventual "real Google Docs feel" web UI is a thin
  client.

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

- **Convergence:** every session's copy is guaranteed identical after updates exchange — like Google
  Docs.
- **No lost edits:** concurrent keystrokes/agent-writes interleave deterministically; nobody's work is
  dropped.
- **No central lock:** sessions edit freely; ordering is resolved by the CRDT, not by waiting.

**Why CRDT over Operational Transform:** both can power Google-Docs-style editing, but OT needs a
central transform authority and is famously tricky to get right; modern collaborative editors
(Yjs/Yrs) are CRDT-based, and `pycrdt` gives us a battle-tested Python implementation that is
wire-compatible with the JS ecosystem.

### 5.2 Layer 2 — Semantic conflict detection: surfaced to humans

The CRDT guarantees the text *converges*, not that it is *correct code*. The Semantic Conflict Watcher
catches what Google Docs never has to:

| Detection | How |
|---|---|
| Won't parse / compile | run the language parser (`ast` for Python; `tree-sitter` elsewhere) on the converged region after each settle |
| Same logical unit, incompatible edits | track which CRDT ranges map to which functions/classes; flag when two sessions wrote the same unit within a window |
| Contradictory intents | agents declare an `intent` with each edit; opposing intents on one unit raise a flag |

On a flag, the Watcher **freezes just that region** and opens a **shared resolution card** to the
involved sessions (§4.2). Everything else in the project keeps flowing — the freeze is surgical, not a
whole-file lock.

### 5.3 Presence as soft conflict-avoidance (the Google Docs trick)

Most conflicts never happen because **you can see where everyone is.** Presence shows live: "Agent C is
rewriting `login()` right now." Humans and agents naturally avoid the spot — the same way Google Docs
collaborators don't fight over the same sentence. This is advisory (shown, not enforced), so it never
blocks anyone.

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

## 10. MVP — Falsify the Thesis in 4 Weeks

**Scope:** 2 humans → **2 separate sessions**, each with **1 background agent**, all editing **1 live
shared project** (CRDT), with presence and semantic-conflict surfacing. Frontend + Backend roles.
Nothing else.

| Week | Deliverable |
|---|---|
| **1 — Live core** | FastAPI server; project create; **two separate sessions** join; **`pycrdt` live-sync** of a shared file tree across both sessions; presence (who's editing what). |
| **2 — Agents in the loop** | Agent Gateway per session wrapping the Anthropic SDK; **agent edits applied as CRDT updates** (stream live to the other session); project-briefing injection. |
| **3 — Conflicts** | Semantic Conflict Watcher (parse-check + same-unit detection); **shared resolution card** to both humans; choose keep-A / keep-B / merged. |
| **4 — Context + measure** | MCP tools (`publish_context`, `query_shared_context`, `signal_ready`, `wait_for_signal`); attributed snapshots to git; session export; **run the experiment** (below). |

**Client:** a Python **Textual** TUI showing your agent chat + a live view of the shared project +
presence + resolution cards. (The CRDT server is Yjs-wire-compatible, so a "real Google Docs feel"
Monaco/Yjs **web** editor is a thin Phase-2 client over the *same Python backend* — the team stays in
Python for everything that matters.)

**Excluded from MVP:** DevOps/Reviewer roles, custom roles, web editor, billing, AST-level merge of
incompatible units (MVP surfaces them, doesn't auto-merge).

### 10.1 The experiment (the real deliverable)

Build the same small feature (a CRUD resource + UI) two ways: **Arm 1** — two people in two sessions on
one live Backyard project; **Arm 2** — the same two on separate agent sessions merging via PRs. Measure
**wall-clock to working feature**, **idle-waiting time**, **defects at first integration**.

| Outcome | Reading |
|---|---|
| Backyard faster, less idle | thesis supported → Phase 2 |
| No difference | inconclusive → find where overhead landed |
| Backyard slower / more friction | thesis disconfirmed **cheaply** → stop, document honestly |

---

## 11. Tech Stack (Python)

| Concern | Choice | Why |
|---|---|---|
| Server | **FastAPI + uvicorn** | async, native WebSocket, Pydantic-validated schemas |
| **Live sync (the Google Docs core)** | **`pycrdt`** (Yjs/Yrs bindings) + **`pycrdt-websocket`** | CRDT convergence, no lost edits; **Yjs-wire-compatible** so a future web editor reuses this exact backend |
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

**Python vs. TypeScript:** Python is the right call — and the one thing that used to argue for JS
(Google-Docs-style CRDT lives in the JS world) is neutralized by **`pycrdt`**, which is the Rust/Yjs
CRDT with Python bindings and the *same wire protocol* as JS clients. We get the Google Docs core in
Python today, and any web editor we add later just talks Yjs to this same server.

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

- **Phase 1 — MVP (4 wks):** §10. *Do two people + two background agents on one live project beat PRs?*
- **Phase 2 — Platform (3 mo):** DevOps + Reviewer roles; cross-domain proposals; ADRs; **Monaco/Yjs web
  editor** (the true Google-Docs feel, thin client over the same Python backend); AST-level merge
  suggestions for incompatible units; session reconnect; RBAC + invite links; CI webhook into the live
  project; load test to ~10 concurrent sessions; closed beta (~20 teams).
- **Phase 3 — Product (6 mo):** Kubernetes session isolation; SSO/SAML; audit/retention (SOC 2 prep);
  private-cloud deploy; role-template marketplace; async mode (your agent works while you're away,
  briefs you on return); issue-tracker → project workflow; GA + pricing.

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

## 15. Revenue Model

Charge for the **collaboration layer**; pass model tokens through at cost (shown per session). The value
sold is the live shared project, the CRDT sync, conflict resolution, shared context, presence, and
audit — not the API call.

- **Free:** 1 live project, 2 sessions, built-in roles, terminal client.
- **Team — ~$49/seat/mo:** unlimited projects + sessions, all roles, history, CI hooks, **web editor**.
- **Enterprise — ~$149/seat/mo:** custom roles, SSO, audit/retention, private-cloud, SLA.

Local-first/self-host is the free on-ramp; **hosted collaboration is the paid boundary** — drawn before
the first line of code (Fatal Risk V).

---

## 16. Open Questions

1. **Live-edit granularity:** keystroke-level CRDT for *everyone* (humans + agents), or agents land
   edits as atomic patches while humans type live? (Recommended: CRDT for both; agents emit edits as
   CRDT updates so they stream like a fast collaborator.)
2. **Session privacy:** confirm humans see each other's *code edits + presence* but **not** each other's
   agent chat. (Recommended: yes — that's the Google Docs analog.)
3. **Snapshot cadence:** time-based, on milestones, on every settle, or human-triggered "commit point"?
4. **Resolution scope:** does a §5 decision bind just the region now, or persist as an ADR constraining
   future edits? (Recommended: human picks "just this" vs. "record as ADR" on the card.)

---

## 17. Conclusion

The product is stated in one line: **Google Docs for AI-assisted coding** — many humans, each logging
into their own session with their own background agent, all editing one live shared project, with
conflicts surfaced to the people involved to settle between themselves. The architecture above makes
that buildable in Python today: a CRDT live-sync core (`pycrdt`) for the always-merged Google Docs
guarantee, a semantic watcher for the one thing code needs that prose doesn't, and a per-session agent
at every seat.

The next move is §10 — two humans, two sessions, two background agents, one live project, four weeks —
and the experiment in §10.1 to learn whether the empty quadrant is empty because it's hard, or because
no one with the right incentives has tried.

---

## References

- M. Reddy, *The Unbuilt Product*, white paper, June 2026.
- Yjs / Yrs — CRDT framework for real-time collaboration; `pycrdt` Python bindings.
- Model Context Protocol — specification and Python SDK (`mcp`).
- Anthropic, *Claude Code Agent Teams* — multi-agent coordination (2026).
