# Backyard — Roadmap

---

## MCP Coordination Server ← building now

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

**How engineers connect:** one line in `.claude/settings.json`. Works from Claude Code CLI, desktop, VS Code, or web — no new tool to install.

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
