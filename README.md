<div align="center">

# 🌳 Backyard

### Multi-Human, Multi-Agent Collaborative Coding

**One live shared project. Many contributors. An AI agent at every seat.**

[![Status](https://img.shields.io/badge/status-design-orange?style=flat-square)](docs/technical-report.md)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![Real-time](https://img.shields.io/badge/realtime-CRDT-8a3e0a?style=flat-square)](docs/architecture.md)
[![Agents](https://img.shields.io/badge/agents-Claude%20%C2%B7%20MCP-b4530f?style=flat-square)](docs/technical-report.md#9-inter-agent-protocol-mcp)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-announcement-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/feed/update/urn:li:activity:7471568927584567296/)

[**White Paper**](https://www.linkedin.com/feed/update/urn:li:activity:7471568927584567296/) ·
[**Technical Report**](docs/technical-report.md) ·
[**Architecture**](docs/architecture.md) ·
[**Roadmap**](docs/roadmap.md)

</div>

---

Every AI coding agent today assumes **one human per session**. But software is built by teams.
**Backyard** fills the missing quadrant: a single live codebase that a whole team contributes to *at
once*, in real time, with an AI agent working alongside each person.

> Many humans log in. **Each gets their own private session with their own background AI agent.** All of
> those sessions contribute to **one live shared project at the same time.** Everyone's edits — and every
> agent's edits — appear live for everyone. No pull requests, no merge step. When two changes truly
> conflict, the collision is surfaced to the humans involved and they **choose between themselves.**

> Companion to the white paper *The Unbuilt Product* (M. Reddy, June 2026).

## Contents

- [What it is](#what-it-is)
- [The shape](#the-shape)
- [How it works](#how-it-works)
- [Tech stack](#tech-stack)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Status](#status)
- [Author & links](#author--links)
- [License](#license)

## What it is

The pull-request model predates AI agents by two decades — it was built so isolated humans could
reconcile work *asynchronously*. Agents inherited it unquestioned. Backyard replaces it with a shared,
always-merged project:

- 🟢 **No merge step.** The shared state is *always already merged*. Your edits and your agent's edits
  land in the live project as they happen.
- 👀 **Everyone sees everything, live.** Watch another person's agent refactor a module in real time —
  not in a diff three hours later.
- 🤖 **An agent at every seat.** Each human's background agent does real work autonomously and streams
  its edits into the shared project, attributed to that person.

## The shape

```
                  ┌──────── ONE LIVE PROJECT (CRDT) ────────┐
                  │           the shared codebase           │
                  └──────────────────────────────────────────┘
                     ▲           ▲           ▲           ▲
               Session A    Session B    Session C    Session D
              (human + agent, private — each edits the live project)
```

- **Project** — the shared, live codebase. The unit everyone collaborates on.
- **Session** — one human's private space: their chat, context, and **background agent**. Many sessions
  attach to one project. You see others' *edits and cursors*, never their private agent chat.

## How it works

| Piece | What it does |
|---|---|
| **Live sync (CRDT)** | Many people's edits converge into one project — lossless, no merge step, no lock. Built on [`pycrdt`](https://github.com/jupyter-server/pycrdt). |
| **Two-layer conflicts** | Text **auto-converges**. Only *semantic* conflicts (code that merged cleanly but is broken or contradictory) **surface to the humans involved** to choose between themselves — no silent "higher-rank wins." |
| **Background agents** | One per session, wrapping the Anthropic API; their edits stream into the live project like a fast collaborator. |
| **Presence** | Live cursors + "who/which agent is editing what" so most collisions never happen. |
| **Roles** | Frontend / Backend / DevOps / Reviewer — *hints, not handcuffs*. Helping elsewhere just asks first, in the open. |
| **Shared context** | Agents exchange structured contracts, ADRs, and file summaries — never raw chat — so context windows and cost stay bounded. |

> **The one question the MVP answers:** *Do two humans + two background agents on one live project ship
> faster than two humans on separate sessions merging through pull requests?*

## Tech stack

**Python, end to end.** [FastAPI](https://fastapi.tiangolo.com/) · `asyncio` ·
[`pycrdt`](https://github.com/jupyter-server/pycrdt) (Yjs-compatible real-time sync) ·
[Redis](https://redis.io/) (presence / pub-sub) · [Postgres](https://www.postgresql.org/) ·
[`anthropic`](https://github.com/anthropics/anthropic-sdk-python) ·
[`mcp`](https://modelcontextprotocol.io/) · [Textual](https://textual.textualize.io/) (terminal client).

The CRDT backend is Yjs-wire-compatible, so a future visual web editor is a thin client over the *same
Python server* — the team stays in Python for everything that matters.

## Documentation

| Document | What's inside |
|---|---|
| 📄 [**Technical Report**](docs/technical-report.md) | The full design, end to end — architecture, data flow, conflict engine, trust model, roles, MCP protocol, MVP, stack, and the five fatal risks mapped to mitigations. |
| 🏗️ [**Architecture Reference**](docs/architecture.md) | Condensed components + data flows. |
| 🗺️ [**Roadmap**](docs/roadmap.md) | MVP (4 weeks) → platform (3 months) → product (6 months). |

## Roadmap

- **Phase 1 — MVP (4 weeks):** 2 humans, 2 sessions, 2 background agents, 1 live project. Prove it beats PRs.
- **Phase 2 — Platform (3 months):** all roles, web editor with live cursors, AST-level merges, CI hooks, beta.
- **Phase 3 — Product (6 months):** Kubernetes isolation, SSO, audit/retention, async mode, GA + pricing.

## Status

**Design phase.** This repository currently holds the technical report and architecture — the blueprint.
Implementation begins with the `pycrdt` live-sync core (the riskiest, highest-value piece). No
application code yet.

## Author & links

Created by **Madhusudhan Reddy**.

- 📣 **Announcement & white paper:** <https://www.linkedin.com/feed/update/urn:li:activity:7471568927584567296/>
- 💼 **LinkedIn:** [in/msreddygone](https://www.linkedin.com/in/msreddygone)

## License

Released under the [MIT License](LICENSE).
