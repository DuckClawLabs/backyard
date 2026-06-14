<div align="center">

# 🌳 Backyard

### Multi-Human, Multi-Agent Collaborative Coding for Engineering Teams

**One live shared project. An entire engineering team contributing at once. An AI agent at every seat.**

[![Status](https://img.shields.io/badge/status-design-orange?style=flat-square)](docs/technical-report.md)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![Real-time](https://img.shields.io/badge/realtime-CRDT-8a3e0a?style=flat-square)](docs/architecture.md)
[![Agents](https://img.shields.io/badge/agents-Claude%20%C2%B7%20MCP-b4530f?style=flat-square)](docs/technical-report.md#9-inter-agent-protocol-mcp)
[![Target](https://img.shields.io/badge/target-enterprise-1c1a17?style=flat-square)](#who-this-is-for)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-announcement-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/feed/update/urn:li:activity:7471568927584567296/)

[**White Paper**](https://www.linkedin.com/feed/update/urn:li:activity:7471568927584567296/) ·
[**Technical Report**](docs/technical-report.md) ·
[**Architecture**](docs/architecture.md) ·
[**Roadmap**](docs/roadmap.md)

</div>

---

Enterprise engineering teams run into the same wall: every AI coding agent assumes **one developer per
session**, but your team has dozens of engineers, multiple time zones, large codebases, compliance
requirements, and handoffs that bleed hours every day. AI hasn't changed how teams collaborate — only
how fast individuals work alone.

**Backyard** changes the team model:

> Each engineer logs into the platform and gets their own private session with their own **background AI
> agent**. All of those sessions contribute to **one live shared project at the same time.** Every
> engineer's edits — and every agent's edits — appear live for the entire team. No pull requests, no
> merge latency. When changes conflict, the collision is surfaced to the engineers involved and they
> **choose between themselves.** The audit trail records everything.

## Contents

- [Who this is for](#who-this-is-for)
- [The problem at enterprise scale](#the-problem-at-enterprise-scale)
- [The shape](#the-shape)
- [How it works](#how-it-works)
- [Tech stack](#tech-stack)
- [Documentation](#documentation)
- [Roadmap](#roadmap)
- [Status](#status)
- [Author & links](#author--links)
- [License](#license)

## Built on Claude Code — extended for teams

**Backyard is a superset of Claude Code, not a replacement.** Every capability Claude Code gives a
single engineer is available in every Backyard session: file editing, shell commands, git operations,
MCP tool use, multi-step agent loops, streaming, slash commands, CLAUDE.md project context.

Backyard adds the one layer Claude Code deliberately left out — the team layer:

| Feature | Claude Code | Backyard |
|---|---|---|
| File read / edit / write | ✓ solo | ✓ streams live to all teammates |
| Shell / bash execution | ✓ solo | ✓ output visible to all (attributed in audit log) |
| Git operations | ✓ solo | ✓ plus team-level attributed snapshots |
| MCP tool use | ✓ per session | ✓ plus shared MCP Hub with team-coordination tools |
| Multi-step agent loops | ✓ solo | ✓ agent output streams to all sessions in real time |
| CLAUDE.md project context | ✓ solo | ✓ shared project-level CLAUDE.md across all agents |
| Permission model | ✓ per engineer | ✓ plus org-level role-based capability enforcement |
| Sessions | 1 human per session | N engineers, each with their own session + agent, one live project |

An engineer in Backyard should be at least as capable as one using Claude Code alone — and additionally
able to see, coordinate with, and build on what their teammates' agents are doing in real time.

## Who this is for

**Backyard is built for engineering organizations** — teams of 10 to 500+ engineers working on shared
codebases, across time zones, with compliance and audit requirements. It is not a tool for individual
developers.

The natural buyers are **CTOs**, **VPs of Engineering**, and **Engineering Managers** who are already
rolling out AI coding agents and hitting the ceiling: agents accelerate the individual but don't touch
the team's coordination overhead.

## The problem at enterprise scale

| Problem | Today | With Backyard |
|---|---|---|
| Cross-timezone handoff | First hour re-explaining context | Session state preserved; agent briefs the incoming engineer |
| PR review latency | Hours to days waiting | Conflicts surface in real time; resolved in seconds |
| Context lost in diffs | Reviewer sees code, not reasoning | Reviewer watches the agent's reasoning as it happens |
| Mentorship | Scheduled pairing sessions | Senior watches junior's agent work live; intervenes immediately |
| Audit & compliance | Reconstructed from git blame | Every agent action logged with `(engineer, agent, timestamp, session)` |
| Org-wide AI policy | Per-developer settings | Role-based capabilities and cross-team controls set at the org level |

## The shape

```
                  ┌──────── ONE LIVE PROJECT (CRDT) ────────┐
                  │           the shared codebase           │
                  └──────────────────────────────────────────┘
                     ▲           ▲           ▲           ▲
               Session A    Session B    Session C    Session D
              (engineer + agent, private — each edits the live project)
```

- **Project** — the shared, live codebase. The unit the whole team collaborates on.
- **Session** — one engineer's private workspace: their chat, context, and **background agent**. You
  see colleagues' *edits and cursors* in the shared project, never their private conversation.

## How it works

| Piece | What it does |
|---|---|
| **Live sync (CRDT)** | All engineers' edits — and their agents' edits — converge into one project, lossless, no merge step, no lock. |
| **Two-layer conflicts** | Text **auto-converges**. Only *semantic* conflicts (code that merged cleanly but is broken or contradictory) **surface to the engineers involved** to resolve together. No silent "higher-rank wins." |
| **Background agents** | One per session, wrapping the Anthropic API; their edits stream into the live project like a fast collaborator, fully attributed. |
| **Presence** | Live indicators of who — and which agent — is editing what, so most collisions never happen. |
| **Roles** | Frontend / Backend / DevOps / Reviewer — with org-configurable domain boundaries. Roles route work; they don't silently block collaboration. |
| **Shared context** | Agents exchange structured contracts, ADRs, and file summaries — never raw chat — so context windows and API costs stay bounded. |
| **Full audit log** | Every agent action is logged with `(engineer, role, agent-turn, timestamp)` for compliance, incident review, and attribution. |

> **The one question the pilot answers:** *Does a team with Backyard ship a feature faster than the same
> team working on separate agent sessions and merging via pull requests?*

## Tech stack

**Python, end to end.** [FastAPI](https://fastapi.tiangolo.com/) · `asyncio` ·
[`pycrdt`](https://github.com/jupyter-server/pycrdt) (Yjs-compatible real-time sync) ·
[Redis](https://redis.io/) (presence / pub-sub) · [Postgres](https://www.postgresql.org/) ·
[`anthropic`](https://github.com/anthropics/anthropic-sdk-python) ·
[`mcp`](https://modelcontextprotocol.io/) · [Textual](https://textual.textualize.io/) (terminal client).

The CRDT backend is Yjs-wire-compatible, so a future visual web editor is a thin client over the *same
Python server*.

## Documentation

| Document | What's inside |
|---|---|
| 📄 [**Technical Report**](docs/technical-report.md) | Full design — architecture, data flow, conflict engine, trust model, roles, MCP protocol, enterprise pilot, Python stack, and the five fatal risks mapped to mitigations. |
| 🏗️ [**Architecture Reference**](docs/architecture.md) | Condensed components + data flows. |
| 🗺️ [**Roadmap**](docs/roadmap.md) | Pilot (4 weeks) → platform (3 months) → enterprise GA (6 months). |

## Roadmap

- **Phase 1 — Pilot (4 weeks):** 2 engineers, 2 sessions, 2 background agents, 1 live project. Prove it reduces team coordination overhead vs. PRs. SSO and audit logging from day one.
- **Phase 2 — Platform (3 months):** All roles, web editor with live cursors, org-wide admin controls, CI/CD hooks, compliance reporting, closed enterprise beta.
- **Phase 3 — Enterprise GA (6 months):** Private-cloud / on-premise deployment, Kubernetes isolation, SOC 2, SCIM provisioning, issue-tracker integration, GA + enterprise pricing.

## Status

**Design phase.** This repository holds the technical report and architecture — the blueprint.
Implementation begins with the real-time sync core. No application code yet.

## Author & links

Created by **Madhusudhan Reddy**.

- 📣 **Announcement & white paper:** <https://www.linkedin.com/feed/update/urn:li:activity:7471568927584567296/>
- 💼 **LinkedIn:** [in/msreddygone](https://www.linkedin.com/in/msreddygone)

## License

Released under the [MIT License](LICENSE).
