<div align="center">

# 🌳 Backyard

### Multi-Agent Coordination for Engineering Teams

[![Status](https://img.shields.io/badge/status-building-orange?style=flat-square)](docs/technical-report.md)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![MCP](https://img.shields.io/badge/protocol-MCP-b4530f?style=flat-square)](docs/technical-report.md)
[![Target](https://img.shields.io/badge/target-enterprise-1c1a17?style=flat-square)](#who-this-is-for)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-announcement-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/feed/update/urn:li:activity:7471568927584567296/)

[**White Paper**](https://www.linkedin.com/feed/update/urn:li:activity:7471568927584567296/) ·
[**Technical Report**](docs/technical-report.md) ·
[**Architecture**](docs/architecture.md) ·
[**Roadmap**](docs/roadmap.md)

</div>

---

> **Backyard is a team coordination layer that wraps Claude Code for enterprise engineering teams.**
> Each engineer connects their existing Claude Code to one shared project — their agent has full shared context of what every other agent on the team is doing, in real time.
> When agents make contradictory decisions or collide on the same code, the conflict surfaces to the engineers involved and they choose between themselves.

---

## Two problems. One product.

### Problem 1 — Agents on the same team are completely blind to each other ← *we are building this now*

Every team using Claude Code today has this problem. Each agent knows only what its own engineer has told it. There is no shared state between sessions.

- Agent A writes an integration for an API that Agent B hasn't shipped yet — wrong assumptions baked in silently
- Agent B makes a breaking change — Agent A's agent doesn't know for hours
- Two agents make contradictory architecture decisions independently — nobody finds out until PR review
- Agent A needs to know if the auth middleware is ready — only a Slack message can answer it, not an agent

**No tool solves this today.** You can put shared context in a `CLAUDE.md` file — but it's manual, asynchronous, and agents don't get notified when it changes.

Backyard fixes it with an **MCP coordination server**: a shared brain all agents on the team connect to. Every agent knows what contracts have been published, what decisions have been made, what each teammate's agent is working on — in real time, automatically, without any human manually updating a doc.

```json
// .claude/settings.json  (one-time setup per engineer)
{
  "mcpServers": {
    "backyard": { "url": "https://backyard.yourcompany.com/project/abc" }
  }
}
```

That one line gives every agent on the team a shared brain. No new tool to install. No workflow to change. Engineers keep using Claude Code exactly as they do today.

---

### Problem 2 — There is no way for multiple engineers to contribute to one live codebase simultaneously ← *the bigger vision*

The pull-request model was designed for humans working in isolation, asynchronously. AI agents inherited it unquestioned. The result: even with AI, teams still wait on PRs, lose context at every handoff, and burn the first hour of every cross-timezone session re-explaining what happened.

The real vision: **each engineer logs into a shared project, gets their own background AI agent, and every agent's edits appear live for the whole team — no PRs, no merge step, no waiting.**

This requires cloud workspaces, real-time sync infrastructure, and a different class of engineering. It is the right long-term answer. It is not where we start.

**We solve Problem 1 first.** Problem 1 is real, achievable now, and has no direct competitors. The team that wins Problem 1 earns the right to build Problem 2.

---

## What we're building (Problem 1)

An **MCP coordination server** that every engineer's Claude Code connects to. It gives every agent on the team:

| What agents get | How |
|---|---|
| **Shared project context** | Architecture decisions, active work, what's in progress — always current |
| **Published contracts** | Agent B publishes the API schema → Agent A's agent gets it immediately, no Slack needed |
| **Real-time signals** | `signal_ready("auth-middleware")` → Agent A unblocks automatically |
| **Team activity feed** | What each agent has done in the last hour, visible to all |
| **Full audit log** | Every agent action logged with `(engineer, role, timestamp)` for compliance |

Engineers keep using whichever Claude Code surface they already use — CLI, desktop app, VS Code extension, or web. Backyard is invisible infrastructure that makes their agents smarter about the team they're part of.

---

## Who this is for

**Enterprise engineering teams** of 10–500+ engineers already using AI coding agents and hitting the ceiling: agents accelerate the individual but do nothing for the team's coordination overhead. The natural buyers are **CTOs**, **VPs of Engineering**, and **Engineering Managers**.

---

## Tech stack

**Python, end to end.** [FastAPI](https://fastapi.tiangolo.com/) · `asyncio` · [Redis](https://redis.io/) (pub/sub, signals) · [Postgres](https://www.postgresql.org/) (context, audit) · [`anthropic`](https://github.com/anthropics/anthropic-sdk-python) · [`mcp`](https://modelcontextprotocol.io/) (official Python SDK) · lightweight web dashboard (presence, audit log).

---

## Documents

| Document | What's inside |
|---|---|
| 📄 [**Technical Report**](docs/technical-report.md) | Full design of both problems — MCP coordination architecture (Problem 1) and live collaboration vision (Problem 2), with all five fatal risks mapped to mitigations. |
| 🏗️ [**Architecture Reference**](docs/architecture.md) | Problem 1 component breakdown + data flows. |
| 🗺️ [**Roadmap**](docs/roadmap.md) | Problem 1 build plan → Problem 2 vision. |

## Roadmap

- **Now — Problem 1:** MCP coordination server. Shared context, contracts, signals, audit. Engineers plug in with one line of config.
- **Next — Problem 1 complete:** Web dashboard (presence, activity feed, conflict cards). Enterprise SSO, audit exports, org-wide admin.
- **Later — Problem 2:** Cloud workspaces. Live shared codebase. Background agents. Real-time sync. No pull requests.

## Status

**Building Problem 1.** Design phase complete; implementation starting with the MCP coordination server.

## Author & links

Created by **Madhusudhan Reddy**.

- 📣 **Announcement & white paper:** <https://www.linkedin.com/feed/update/urn:li:activity:7471568927584567296/>
- 💼 **LinkedIn:** [in/msreddygone](https://www.linkedin.com/in/msreddygone)

## License

Released under the [MIT License](LICENSE).
