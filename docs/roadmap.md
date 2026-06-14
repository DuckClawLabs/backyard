# Backyard — Roadmap

**Enterprise engineering teams.** Each engineer with their own background AI agent. One live shared
project. Full detail in [`technical-report.md`](./technical-report.md).

---

## Phase 1 — Pilot (4 weeks): *Does it reduce team coordination overhead?*

**Scope:** 2 engineers from a real enterprise team → **2 separate sessions**, each with **1 background
agent**, editing **1 live shared project** (CRDT) with presence, audit logging, and semantic-conflict
surfacing. Frontend + Backend roles. Nothing else.

The pilot must involve a **real enterprise engineering team** — not two individuals. Realistic
conditions are the point: actual codebase, actual coordination overhead, a stakeholder who can validate
whether the result matters to the business.

Engineers connect their **existing Claude Code setup** (CLI, desktop, VS Code, or web) to the Backyard
MCP server via a one-line config — no new client to install.

```json
{ "mcpServers": { "backyard": { "url": "https://backyard.co/project/abc" } } }
```

| Week | Deliverable |
|---|---|
| 1 — MCP server + live core | FastAPI server; MCP endpoint serving standard file tools (read, edit, list, shell, git) + project registry; **`pycrdt` live-sync** so two sessions share one project; presence; **full audit log from day one**. |
| 2 — Team tools + agents | MCP team-coordination tools (`publish_context`, `signal_ready`, `wait_for_signal`, `raise_resolution`); Agent Gateway routing MCP calls through the CRDT; project-briefing injection; role capability enforcement. |
| 3 — Conflicts + dashboard | Semantic Conflict Watcher (parse-check + same-unit detection); **shared resolution card** to both engineers; lightweight web dashboard (presence, conflict cards, audit log). |
| 4 — Context + measure | Shared context store; attributed git snapshots; session export; **run the pilot experiment**. |

**The experiment:** two engineers build the same well-defined feature in Backyard vs. their current
PR-based workflow. Measure wall-clock, idle time, defects at first integration, and — critically — the
Engineering Manager's answer to "would you run the next sprint this way?"

| Outcome | Reading |
|---|---|
| Measurably faster, less idle | thesis supported; present to engineering leadership; proceed to Phase 2 |
| No difference | inconclusive — find where overhead stayed; iterate or stop |
| Slower / more friction | disconfirmed cheaply — four weeks, not a company |

---

## Phase 2 — Platform (3 months): *Is it ready for the enterprise?*

- All roles: DevOps, Reviewer; org-configurable domain schemas.
- **Web editor** with live cursors (thin Yjs client over the same Python backend).
- **Org-wide admin dashboard**: user management, role assignments, usage and cost reporting.
- **SSO/SAML** — moved to Phase 2, not Phase 3. This is a non-negotiable enterprise requirement for any
  security-conscious organization.
- Compliance audit log exports (CSV/JSON, filterable by engineer, session, time range).
- CI/CD hooks — failing test notification surfaced live into the project.
- AST-level merge suggestions for incompatible units (not just surface-and-pick).
- Session reconnect without losing agent context.
- RBAC: invite links per role, org-level permissions.
- Load test to ~20 concurrent sessions.
- **Closed enterprise beta:** 3–5 enterprise customers running full sprints.

---

## Phase 3 — Enterprise GA (6 months): *Is it deployable everywhere?*

- **Private-cloud and on-premise deployment** — non-negotiable for financial services, healthcare, and
  defense customers; moved forward, not a Phase-3 afterthought.
- Kubernetes session isolation per org.
- **SOC 2 Type II** certification.
- **SCIM provisioning** (auto-sync engineers from Okta/Azure AD).
- Custom data-retention and deletion policy per org.
- Role-template marketplace: community-defined role schemas for common team structures.
- **Async mode:** agent works while an engineer is in a different time zone; full session briefing on
  return.
- Issue-tracker integration (Linear, Jira) → live project workflow.
- GA with enterprise pricing (§15 of the technical report).

---

## Enterprise feature priority rationale

Features that were Phase 3 in a consumer product are Phase 1/2 here because enterprise buyers evaluate
on compliance, security, and control — not feature count. A CTO who can't check "SSO" and "audit log"
off a vendor security questionnaire will not adopt the product regardless of how well the collaboration
works. These are gates, not nice-to-haves.

| Feature | Consumer product phase | Backyard phase |
|---|---|---|
| Full audit log | Phase 3 | **Phase 1** (day one) |
| SSO/SAML | Phase 3 | **Phase 2** |
| Compliance export | Phase 3 | **Phase 2** |
| Private/on-premise deploy | Phase 3 | **Phase 3** (but designed for from day one) |
| SCIM provisioning | Phase 3 | **Phase 3** |
