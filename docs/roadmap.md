# Backyard — Roadmap

**Google Docs for AI-assisted coding.** Many humans, each with their own session + background agent, all
editing one live shared project. Full detail in [`technical-report.md`](./technical-report.md).

---

## Phase 1 — MVP (4 weeks): *Does it beat PRs?*

**Scope:** 2 humans → **2 separate sessions**, each with **1 background agent**, all editing **1 live
shared project** (CRDT) with presence and semantic-conflict surfacing. Frontend + Backend. Nothing else.

| Week | Deliverable |
|---|---|
| 1 — Live core | FastAPI server; project create; two separate sessions join; **`pycrdt` live-sync** of a shared file tree across both; presence (who's editing what). |
| 2 — Agents in the loop | Agent Gateway per session (Anthropic SDK); **agent edits applied as CRDT updates**, streaming live to the other session; project-briefing injection. |
| 3 — Conflicts | Semantic Conflict Watcher (parse-check + same-unit detection); **shared resolution card** to both humans; keep-A / keep-B / merged. |
| 4 — Context + measure | MCP tools (`publish_context`, `query_shared_context`, `signal_ready`, `wait_for_signal`); attributed git snapshots; session export; **run the experiment**. |

**Client:** Python **Textual** TUI — your agent chat + a live view of the shared project + presence +
resolution cards. (The `pycrdt` backend is Yjs-wire-compatible, so the Phase-2 web editor is a thin
client over this same Python server.)

**The experiment:** build the same CRUD-plus-UI feature (a) two people in two sessions on one live
Backyard project vs. (b) two people on separate sessions merging via PRs. Measure wall-clock, idle time,
defects at first integration.

| Outcome | Reading |
|---|---|
| Backyard faster, less idle | thesis supported → Phase 2 |
| No difference | inconclusive → find where the overhead landed |
| Backyard slower | thesis disconfirmed cheaply → stop, document honestly |

A negative result is a **successful** MVP — four weeks, not a company.

---

## Phase 2 — Platform (3 months): *Is it reliable — and does it feel like Google Docs?*

- **Monaco/Yjs web editor** — the true Google-Docs feel (live cursors, inline edits), a thin client over
  the same Python backend.
- DevOps + Reviewer roles; cross-domain proposal flow; ADR system.
- AST-level **merge suggestions** for incompatible units (not just surface-and-pick).
- Session reconnect without losing agent context; RBAC + invite links.
- CI webhook → notification into the live project on failing tests.
- Load test to ~10 concurrent sessions; closed beta with ~20 teams.

---

## Phase 3 — Product (6 months): *Is it a business?*

- Kubernetes session isolation; SSO/SAML; audit + retention (SOC 2 prep).
- Private-cloud deployment option.
- Role-template marketplace; custom MCP tool plugins.
- Async mode: your agent works while you're away, briefs you on return.
- Issue-tracker (Linear/Jira) → live-project workflow.
- GA launch with public pricing.

---

## Fatal-risk gates (must stay green to advance)

| # | Risk | Gate |
|---|---|---|
| I | Coordination overhead rises | Phase-1 experiment must show it *falls* (no merge step, live presence). |
| II | Concurrent edits lose work | **CRDT guarantees convergence + no lost edits**; sync engine tested exhaustively first. |
| III | Multi-principal trust unsafe | Agents *stop and surface*; hard System floor holds. |
| IV | Conflict resolution slow/confusing | Text auto-converges; only *semantic* conflicts surface — to involved humans, surgical region freeze. |
| V | No revenue path | Paid boundary (hosted collaboration + web editor) defined before code. |
