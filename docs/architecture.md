# Backyard — Architecture Reference

Condensed component and data-flow reference. Full rationale lives in
[`technical-report.md`](./technical-report.md) (§3–§9).

---

## Components

| # | Component | Responsibility |
|---|---|---|
| ① | **Session Orchestrator** | Source of truth: participants, roles, agent activity, locks. One per session. |
| ② | **Agent Gateway** (×N) | Wraps Anthropic API per human-agent pair; injects briefing; streams output to all; **intercepts every tool call** (trust boundary). |
| ③ | **Conflict Resolver (CRE)** | Detects collisions (vector clocks + 3-way diff); auto-merges disjoint edits; **escalates the rest to the session**. |
| ④ | **Shared Context Store** | Structured contracts, ADRs, file summaries. How agents understand each other. |
| ⑤ | **MCP Hub** | Coordination API exposed to agents as MCP tools. |
| ⑥ | **Workspace & Git Service** | Owns fs + git; per-role branches; metadata-tagged commits. |
| ⑦ | **Event Bus + Audit Log** | Redis pub/sub fan-out to clients; Postgres persistence for replay/audit/billing. |

```
   Human A ─ TUI ◄──►┐
   Human B ─ TUI ◄──►├──►  Session Server (FastAPI · asyncio)  ◄──► Shared Git Repo
   Human C ─ TUI ◄──►┘            │
                          Redis (locks, pub/sub) · Postgres (history)
```

---

## Key data flows

**Clean edit:** human → gateway (briefing injected) → Claude → `write_file` intercepted → role check →
CRE lock → apply → commit on `session/<id>/<role>` → `FILE_CHANGED` broadcast → context summary refresh
→ unlock.

**Collision:** two writes to one file → CRE 3-way diff → *disjoint* auto-merges; *overlapping* raises a
**conflict card into the shared session**; humans pick keep-A / keep-B / merged → CRE applies →
`FILE_RESOLVED`. No silent winner.

**Cross-agent:** consumer calls `wait_for_signal`; producer calls `publish_context` + `signal_ready`;
Hub hands the typed contract over. No raw reasoning crosses; the stand-up disappears.

---

## Conflict Resolution Engine

- **Algorithm:** 3-way merge + human escalation (what git does). CRDTs lose code semantics; OT is
  deferred.
- **Vector clock** per file `{role: seq}` decides "what the agent saw" and the correct merge base.
- **Locks (Redis):** `lock:{session}:{path}` → `{role, participant, acquired_at, intent}`, TTL 30s
  renewed every 10s. SETNX for atomicity; TTL frees a crashed agent's lock fast.
- **Classes:** Structural (auto if disjoint), Logic (always → session), Formatting (accept later),
  Generated (owner-exclusive).
- **Python:** `git merge-file` for MVP → `merge3`; `ast` + `tree-sitter` for Phase-2 semantic detection.
  CRE is a pure, exhaustively-tested module.

---

## Multi-Principal Trust

- **System floor (non-negotiable):** no access outside workspace; no direct push to `main`; no reading
  others' secrets; destructive ops always via CRE.
- **Above the floor: humans decide.** Conflicting instructions → agents **pause** → a **decision card**
  is posted into the shared session → humans resolve (talk / vote / record as ADR) → applied + audited.
- **No silent timer-winner.** A stuck decision stays *visibly* paused.
- **Agent default under conflict:** *stop and surface* (`raise_session_decision`), never *guess and
  proceed*. This is the answer to Fatal Risk III.

---

## Roles (hints, not handcuffs)

| Role | Default domain |
|---|---|
| Frontend | `ui/**`, `components/**`, `styles/**`, `pages/**` |
| Backend | `api/**`, `services/**`, `db/**`, `middleware/**` |
| DevOps | `infra/**`, `*.yml`, `Dockerfile`, `.github/**` |
| Reviewer | read-everywhere; writes via proposals |

Out-of-domain writes are **redirected** to `propose_cross_domain_edit` (posted to the session), not
rejected. Custom roles via `backyard.toml`. Enforcement at the Agent Gateway, pre-execution.

---

## Shared Context (no shared history)

Agents exchange **structured artifacts**, never raw conversations:
**Interface Contracts**, **ADRs**, **File Summaries**, **Compressed Session Log**.
Each turn gets a ≤2k-token **session briefing** (elapsed, present roles, recent activity, contracts,
locks, open decisions). Storage: Redis (hot) + Postgres (durable). No vector DB in MVP.

---

## Inter-Agent Protocol (MCP)

| Group | Tools |
|---|---|
| Context | `query_shared_context`, `publish_context`, `get_file_summary`, `get_session_status` |
| Coordination | `propose_cross_domain_edit`, `request_clarification`, `signal_ready`, `wait_for_signal`, `raise_session_decision` |
| Files (enforced) | `read_file`, `write_file`, `list_files` |
| Review (Reviewer) | `create_review_comment`, `approve_merge`, `request_changes` |
