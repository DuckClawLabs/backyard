# Backyard — Architecture Reference

**Multi-human, multi-agent collaborative coding:** many humans, each with their own private session +
background agent, all contributing to one live shared project in real time. Full rationale in
[`technical-report.md`](./technical-report.md).

---

## The shape

```
                          ┌──────────── ONE LIVE PROJECT ────────────┐
                          │        (the shared codebase, CRDT)        │
                          └───────────────────────────────────────────┘
                              ▲            ▲            ▲           ▲
  ┌───────────┐        ┌───────────┐ ┌───────────┐         ┌───────────┐
  │ Session A │        │ Session B │ │ Session C │   ...   │ Session D │
  │ Human+Agent (private chat/context) — each edits the live project   │
  └───────────┘        └───────────┘ └───────────┘         └───────────┘
```

- **Project** = the shared, live codebase. The unit everyone collaborates on. Keyed by `project_id`.
- **Session** = one human's private workspace: their chat, context, presence, and **background agent**.
  Keyed by `session_id`. Sessions are isolated from each other (you see others' *edits*, not their chat).

---

## Components

| # | Component | Responsibility |
|---|---|---|
| ① | **Project Registry** | Owns projects; attaches/detaches sessions; everything keys off project + session. |
| ② | **Live Sync Engine (CRDT)** | The real-time core. Shared codebase as a `pycrdt` doc; every human/agent edit converges on all sessions, lossless, no merge step, no lock. |
| ③ | **Session Workspace** (×N) | Per-human private space: chat, context, cursor/presence, live project view. |
| ④ | **Agent Gateway** (×N) | Wraps Anthropic API for that session's background agent; applies its edits **as CRDT updates** (live + attributed). |
| ⑤ | **Semantic Conflict Watcher** | Above the CRDT: detects broken/contradictory converged code; freezes the region; raises a shared resolution card to involved humans. |
| ⑥ | **Shared Context Store** (per project) | Contracts, ADRs, file summaries — how agents across sessions understand the shared project. |
| ⑦ | **MCP Hub** | Coordination tools exposed to agents (incl. `apply_edit`, `raise_resolution`, `wait_for_signal`). |
| ⑧ | **Presence + Event Bus** | Live cursors / "who's editing what" + Redis pub/sub fan-out. |
| ⑨ | **Snapshot / Git Service** | Attributed checkpoints of live state to git (durable history + export). |

---

## Two-layer conflict model

**Layer 1 — Text convergence (CRDT).** Automatic and lossless. Every session converges to identical
text; concurrent edits interleave deterministically; no central lock. (`pycrdt` = Yjs/Yrs; wire-
compatible with JS clients.)

**Layer 2 — Semantic conflict detection.** The text converges but may be broken *code*. The Watcher:
- parse-checks converged regions (`ast` / `tree-sitter`),
- maps CRDT ranges → functions/classes to spot "same unit, incompatible edits,"
- on a flag, **freezes only that region** and opens a **shared resolution card** to the involved
  humans, who **choose between themselves** (keep-A / keep-B / merged). No rank-based auto-winner.

**Presence as soft avoidance:** seeing "Agent C is rewriting `login()` now" prevents most collisions —
advisory, never blocking.

**Conflicting instructions** (A: "Postgres" / B: "SQLite") follow the same path: agents **stop and
surface** via `raise_resolution`; humans settle it.

---

## Key data flows

**Live edit:** human keystroke *or* agent `apply_edit` → CRDT update → merged into shared project →
broadcast to all sessions (views update live) → presence + Watcher re-check + context summary → folded
into next attributed snapshot. No lock, no PR.

**Conflict:** same logical unit edited incompatibly → CRDT converges text, Watcher flags semantics →
region frozen → shared card to the two involved humans → they pick → applied + audited.

**Cross-session:** consumer `wait_for_signal(topic)`; producer `publish_context` + `signal_ready`; Hub
hands over the typed contract. The stand-up disappears.

---

## Trust model

- **System floor (non-negotiable):** no access outside the project workspace; no direct push to `main`;
  no reading another session's chat/secrets; irreversible ops need a surfaced decision.
- **Above the floor:** humans decide, in a shared resolution view, for the regions/instructions that
  truly conflict. Agent default under conflict: **stop and surface**, never **guess and proceed**.

---

## Roles (hints, not handcuffs)

| Role | Default domain |
|---|---|
| Frontend | `ui/**`, `components/**`, `styles/**`, `pages/**` |
| Backend | `api/**`, `services/**`, `db/**`, `middleware/**` |
| DevOps | `infra/**`, `*.yml`, `Dockerfile`, `.github/**` |
| Reviewer | read-everywhere; edits via proposal |

Out-of-domain edits are **redirected** to `propose_cross_domain_edit` (a card to the owner), not
blocked. Custom roles via per-project `backyard.toml`. Enforced at the Gateway before edits reach the
CRDT.

---

## Inter-agent protocol (MCP)

| Group | Tools |
|---|---|
| Context | `query_shared_context`, `publish_context`, `get_file_summary`, `get_project_status` |
| Coordination | `propose_cross_domain_edit`, `request_clarification`, `signal_ready`, `wait_for_signal`, `raise_resolution` |
| Editing (CRDT-applied) | `read_file`, `apply_edit`, `list_files` |
| Review (Reviewer) | `create_review_comment`, `approve_change`, `request_changes` |
