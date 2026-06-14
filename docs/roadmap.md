# Backyard — Roadmap

Two problems. One product. We build Problem 1 first.

---

## Problem 1 — MCP Coordination ← building now

**The problem:** agents on the same engineering team are completely blind to each other.
Every Claude Code session is isolated. No shared context, no signals, no awareness of what teammates' agents are doing.

**The solution:** an MCP coordination server every engineer's Claude Code connects to with one line of config — giving every agent a shared brain.

### Phase 1A — Core coordination server

| What | Description |
|---|---|
| **MCP server** | Serves both standard file tools and team-coordination tools (`publish_context`, `query_shared_context`, `signal_ready`, `wait_for_signal`, `raise_resolution`) |
| **Shared context store** | Postgres-backed store of contracts, architecture decisions (ADRs), and auto-generated file summaries — always current, always available to every agent |
| **Real-time signals** | Redis pub/sub: `signal_ready("auth-api")` → waiting agents unblock immediately, no Slack message needed |
| **Audit log** | Every agent action logged with `(engineer, role, timestamp, session)` from day one |
| **Project briefing** | Auto-injected into each agent turn: who's working on what, recent activity, published contracts, open decisions |

**How engineers connect:** add one line to `.claude/settings.json`. Works from Claude Code CLI, desktop, VS Code, or web — no new tool to install.

### Phase 1B — Visibility and enterprise controls

| What | Description |
|---|---|
| **Web dashboard** | Presence (who's active, what their agent is doing), team activity feed, audit log viewer |
| **Conflict resolution UI** | When two agents make contradictory decisions, surface a resolution card to the involved engineers |
| **SSO / SAML** | Enterprise login — non-negotiable for most corporate procurement |
| **Org-wide admin** | User management, role assignments, usage and cost reporting per engineer |
| **Compliance exports** | Audit log as CSV/JSON, filterable by engineer / session / time range |

### Phase 1C — Enterprise hardening

| What | Description |
|---|---|
| **Private deployment** | Self-hosted on the customer's cloud — required for financial services, healthcare, defense |
| **SOC 2 Type II** | Security certification required by enterprise procurement |
| **SCIM provisioning** | Auto-sync engineers from Okta / Azure AD |
| **CI/CD integration** | Failing test or deploy → notification surfaced into the shared project context |

---

## Problem 2 — Live Collaboration ← the bigger vision

**The problem:** there is no way for multiple engineers to contribute to one live codebase simultaneously.
The pull-request model was designed for isolated humans working asynchronously. AI agents inherited it unquestioned.

**The vision:** each engineer logs into a shared project and gets their own background AI agent. Every agent's edits appear live for the whole team — no PRs, no merge step, no waiting. Conflicts surface to the engineers involved in real time.

This requires:
- **Cloud workspaces** — Backyard provisions a container per engineer; all containers share the codebase
- **Real-time sync** — CRDT-based file sync across all containers (`pycrdt`, Yjs-wire-compatible)
- **Background agents** — a server-side agent loop per engineer, running autonomously against the Anthropic API
- **Semantic conflict detection** — AST-aware detection of logically incompatible edits, not just text conflicts
- **Shared resolution UI** — live conflict cards surfaced to the involved engineers

**This is a 1–2 year build and a different class of engineering.** We earn the right to build it by winning Problem 1 first.

### Why Problem 1 comes first

- Problem 1 is real, achievable now, and has no direct competitors
- Problem 1 can be shipped to enterprise teams already using Claude Code — today
- Problem 1 validates the market before we commit to cloud infrastructure
- The team that wins Problem 1 has the relationships, trust, and revenue to fund Problem 2

---

## One-line summary

> Build the shared brain first. Then build the shared workspace.
