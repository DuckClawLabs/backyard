# Backyard — Architecture Reference

Full design in [`technical-report.md`](./technical-report.md).

---

## MCP Coordination Server

An MCP server that gives every engineer's Claude Code agent a **shared brain** — shared context, real-time signals, contracts, and a full audit trail.

### How engineers connect

```json
// .claude/settings.json  (one-time addition per engineer)
{
  "mcpServers": {
    "backyard": { "url": "https://backyard.yourcompany.com/project/abc" }
  }
}
```

Works from any Claude Code surface: CLI, desktop app, VS Code extension, web. No new tool to install.

### System shape

```
                      ┌──────────── BACKYARD MCP SERVER ────────────┐
                      │            (Python · FastAPI · asyncio)      │
                      │                                              │
                      │  ① MCP Hub          ② Shared Context Store  │
                      │  ③ Signal Engine    ④ Project Briefing       │
                      │  ⑤ Audit Log        ⑥ Conflict Surface       │
                      └──────────────────────────────────────────────┘
                           ▲              ▲               ▲
              MCP          │              │               │  MCP
       ┌──────────────┐    │    ┌─────────┴──────┐    ┌──┴───────────┐
       │ Engineer A   │    │    │  Engineer B    │    │  Engineer C  │
       │ Claude Code  │         │  Claude Code   │    │  Claude Code │
       │ (any surface)│         │  (any surface) │    │  (any surface│
       └──────────────┘         └────────────────┘    └──────────────┘

                      Redis (pub/sub, signals, hot state)
                      Postgres (context store, audit log)
```

### Components

| # | Component | What it does |
|---|---|---|
| ① | **MCP Hub** | The MCP server engineers connect to. Exposes both standard file tools and team-coordination tools. |
| ② | **Shared Context Store** | Contracts, ADRs, file summaries — structured artifacts agents publish and query. Never raw conversation history. |
| ③ | **Signal Engine** | Redis pub/sub: `signal_ready` / `wait_for_signal`. Agent B publishes; Agent A unblocks automatically. |
| ④ | **Project Briefing** | Auto-injected into every agent turn (≤2k tokens): who's active, recent activity, published contracts, open decisions. |
| ⑤ | **Audit Log** | Every agent action logged: `(engineer, role, agent-turn, timestamp, tool, result)`. Postgres. Always on. |
| ⑥ | **Conflict Surface** | When two agents make contradictory decisions, posts a resolution card to the involved engineers. |

### MCP tool catalog

| Group | Tools |
|---|---|
| **Context** | `query_shared_context`, `publish_context`, `get_file_summary`, `get_project_status` |
| **Signals** | `signal_ready`, `wait_for_signal` |
| **Coordination** | `propose_cross_domain_edit`, `raise_resolution`, `request_clarification` |
| **Standard file tools** (pass-through) | `read_file`, `write_file`, `list_files` |
| **Review** (Reviewer role) | `create_review_comment`, `approve_change`, `request_changes` |

### Data flows

**Shared context:** Agent B implements an endpoint → calls `publish_context(contract=user-api-v1)` + `signal_ready("user-api")` → Agent A's pending `wait_for_signal("user-api")` resolves → Agent A receives the typed contract and builds against the real shape. **The stand-up never happens.**

**Conflict:** Two agents issue contradictory instructions (A: "use Postgres"; B: "use SQLite") → both agents call `raise_resolution` → a decision card appears in the web dashboard for the two engineers → they choose → decision recorded as an ADR → agents resume.

**Briefing:** At the start of every agent turn, the Project Briefing is auto-injected:
```
=== PROJECT BRIEFING ===
Active: Frontend(A), Backend(B), Reviewer(C)
Recent: B published user-api-v1 · A built UserCard component
Contracts: user-api-v1 → GET /api/users/:id → UserDTO
Open decisions: none
=== END ===
```

### Storage

| Store | What lives there |
|---|---|
| **Redis** | Signals, pub/sub, active sessions, hot briefing cache |
| **Postgres** | Contracts, ADRs, file summaries, audit log, project config |

No vector database. All context queries are structured (by role, file path, contract ID) — faster, cheaper, never stale within an active session.
