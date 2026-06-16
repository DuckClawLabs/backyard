# Backyard Feature Inventory

**Legend:**
- `[x]` Implemented · `[ ]` Planned · `[~]` Partial
- `[B]` Part of **Project Brain** (the shared context/knowledge layer)

---

## Phase 1 — Core Coordination Layer (Built)

| Feature | Status | Project Brain | What it does | Implementation |
|---|---|---|---|---|
| Shared Context Store | [x] | [B] | Single source of truth for all agents — contracts, ADRs, file summaries stored in Postgres | MCP tools `publish_context` / `query_shared_context` → Postgres table; future: add vector search + knowledge graph |
| Shared Contracts | [x] | [B] | Agents publish API shapes so teammates never guess or invent incompatible interfaces | Stored via `publish_context()`; future: auto-extract from FastAPI / OpenAPI / TypeScript source |
| Project Briefing | [x] | [B] | Auto-injected every turn: who's working on what, open decisions, published contracts | Server assembles briefing from Postgres on each MCP turn and injects it into agent context |
| File Summaries | [x] | [B] | Plain-language summary generated after every file write; agents understand teammate code fast | Generated post-write, stored in Postgres, retrieved via `get_file_summary()` |
| Signals | [x] | | `signal_ready()` / `wait_for_signal()` — replaces Slack "is X done?" messages | Redis pub/sub; publisher posts to channel, subscribers block until message arrives |
| Conflict Resolution | [x] | | Surfaces a conflict card when agents make contradictory decisions | `raise_resolution()` writes a conflict record to Postgres; visible in dashboard |
| Role-Based Ownership | [x] | | Frontend / Backend / DevOps / Reviewer lanes; cross-domain changes require approval | Role stored per session; MCP server enforces lane checks before allowing writes |
| Audit Log | [x] | | Every agent action recorded with engineer, role, tool, timestamp — compliance + traceability | Middleware intercepts every MCP tool call and appends a row to the audit table |
| Reviewer Workflow | [x] | | Reviewer-only tools: `approve_change`, `request_changes`, `create_review_comment` | Role-gated MCP tools; only sessions registered as Reviewer can invoke them |

---

## Phase 2 — Planned

| Feature | Status | Project Brain | What it does | Implementation |
|---|---|---|---|---|
| Automatic Contract Extraction | [ ] | [B] | Parse code changes and auto-publish contracts (FastAPI, OpenAPI, TypeScript, GraphQL) | AST parser watches file writes → extracts routes/types → calls `publish_context()` automatically |
| Breaking Change Detection | [ ] | [B] | Warn before merge: "this API change breaks N consumers" | Contract registry tracks producer + consumers + versions; diff on each publish flags breaking changes |
| Project Time Machine | [ ] | [B] | Query decision history: "Why Postgres?" → returns ADR, author, date, reason | ADR graph stored in Postgres with decision lineage; natural language query layer on top |
| Autonomous Handoffs | [ ] | [B] | Snapshot agent session context so the next agent picks up seamlessly | Summarization pipeline runs on session end; snapshot persisted to Postgres and injected on next session start |
| Multi-Repo Awareness | [ ] | [B] | Treat frontend, backend, mobile, and infra repos as one unified system | Repository registry in Postgres; cross-repo dependency graph links services across repos |
| Dependency Graph | [ ] | | Declare and visualize why agents are blocked on each other | `declare_dependency()` MCP tool → `dependencies` table → graph traversal API → dashboard visualization |

---

## Phase 3 — Long-Term

| Feature | Status | Project Brain | What it does | Implementation |
|---|---|---|---|---|
| Team Memory Graph | [ ] | [B] | Knowledge graph connecting engineers, agents, services, ADRs, contracts, and files | Neo4j or graph tables in Postgres; entities linked by relationship edges; traversal API for queries |
| Knowledge Feed | [ ] | [B] | Continuous event stream: new contracts, ADRs, breaking changes, completed milestones | Event sourcing on all Postgres writes; timeline service fans out to subscribed agents |
| Team Knowledge Score | [ ] | [B] | Measure coordination health: stale ADRs, missing ownership, orphaned contracts | Periodic graph analysis job scores each entity; results surfaced in dashboard |
| Multi-Agent Planning | [ ] | | Input: "Build User Profile" → auto-split into Backend / Frontend / DevOps / Review tasks | Planner agent decomposes goal into task graph; assigns tasks by role; tracks completion |
| Agent Presence | [ ] | | Real-time view of what every agent is doing and how far along it is | Heartbeat service: agents ping every N seconds with current task + progress; shown in dashboard |
| Agent-to-Agent Messaging | [ ] | | Agents communicate directly via mailbox queues without a human relay | Per-role mailbox queues in Redis; `ask_agent(role=)` MCP tool routes messages and awaits reply |
| Coordination Copilot | [ ] | | Backyard actively unblocks agents — detects when a dependency clears and notifies waiters | Event engine watches dependency graph + signals; rule system triggers notifications on state change |
| Agent Marketplace | [ ] | | Registry of specialized agents: Security, Compliance, Architecture, Reviewer | Role registry + capability registry in Postgres; agents self-register on connect |

---

## Vision

**Shared Live Codebase** `[ ]` — Multiple engineers and agents editing one live workspace in real time. No PRs, no merge queues. Requires CRDTs and real-time file sync. Noted as a company-sized problem; pursue only after Backyard dominates coordination.
