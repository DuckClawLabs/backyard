# Backyard — Roadmap

Full detail in [`technical-report.md`](./technical-report.md) (§10, §13, §14).

---

## Phase 1 — MVP (4 weeks): *Does collaboration beat PRs?*

**Scope:** 2 humans, 2 agents, 1 repo, Frontend + Backend roles, file-level locking, shared terminal
transcript, conflicts surfaced to the session. Nothing else.

| Week | Deliverable |
|---|---|
| 1 — Spine | FastAPI server; session create/join over WebSocket; Agent Gateway (Anthropic SDK + briefing + `write_file` interception); Redis lock service (SETNX + TTL). |
| 2 — CRE | per-file vector clocks; 3-way merge via `git merge-file`; auto-merge disjoint; **conflict card to both terminals** + one-key choose. |
| 3 — Context | file-summary generation; briefing injection; MCP tools `publish_context`, `query_shared_context`, `signal_ready`, `wait_for_signal`. |
| 4 — Git + measure | per-role branches; auto-commit with session metadata; session export; **run the experiment**. |

**The experiment:** build the same CRUD-plus-UI feature (a) in one Backyard session vs. (b) two
separate sessions merging via PRs. Measure wall-clock, idle time, defects at first integration.

| Outcome | Reading |
|---|---|
| Backyard faster, less idle | thesis supported → Phase 2 |
| No difference | inconclusive → find where the overhead landed |
| Backyard slower | thesis disconfirmed cheaply → stop, document honestly |

A negative result is a **successful** MVP — it cost four weeks, not a company.

---

## Phase 2 — Platform (3 months): *Is it reliable?*

- DevOps + Reviewer roles; cross-domain proposal flow; ADR system.
- AST-aware conflict detection (`ast` + `tree-sitter`).
- Session reconnect without losing agent context.
- RBAC + invite-per-role; thin web dashboard.
- CI webhook → session notification on failing tests.
- Load test to ~10 concurrent sessions; closed beta with ~20 teams.

---

## Phase 3 — Product (6 months): *Is it a business?*

- Session isolation on Kubernetes; SSO/SAML; audit + retention (SOC 2 prep).
- Private-cloud deployment option.
- Role-template marketplace; custom MCP tool plugins.
- Async mode: agent works while a human is away, briefs them on return.
- Issue-tracker (Linear/Jira) → session workflow.
- GA launch with public pricing.

---

## Fatal-risk gates (must stay green to advance)

| # | Risk | Gate |
|---|---|---|
| I | Coordination overhead rises | Phase-1 experiment must show it *falls*. |
| II | Concurrent-edit merge loses work | CRE exhaustively tested before any real session. |
| III | Multi-principal trust unsafe | Agents *stop and surface*; hard System floor holds. |
| IV | Conflict resolution slow/confusing | One card, side-by-side, decided by humans already present. |
| V | No revenue path | Paid boundary (hosted coordination) defined before code — it is. |
