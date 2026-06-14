<div align="center">

# 🌳 Backyard

### Teammates share one brain between their agents

[![Status](https://img.shields.io/badge/status-building-orange?style=flat-square)](docs/technical-report.md)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![MCP](https://img.shields.io/badge/protocol-MCP-b4530f?style=flat-square)](docs/technical-report.md)
[![Target](https://img.shields.io/badge/target-enterprise-1c1a17?style=flat-square)](#who-this-is-for)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/msreddygone)

[**Technical Report**](docs/technical-report.md) ·
[**Architecture**](docs/architecture.md) ·
[**Deployment**](docs/deployment.md) ·
[**Roadmap**](docs/roadmap.md)

</div>

---

> Two engineers. Two agents. One shared brain.
>
> Each engineer on your team has their own Claude Code agent. Those agents know nothing about each other.
> Backyard gives them a shared brain — so every agent on the team knows what the others are building, in real time, automatically.
> One line of config. No new tools. No workflow changes.

---

## The problem no one has solved yet

Your engineering team uses Claude Code. Each engineer has their own agent. Those agents work in parallel — and they are **completely blind to each other**.

Engineer A's agent does not know what Engineer B's agent is building. Engineer B's agent does not know what decisions Engineer A's agent has made. The moment two teammates start working on the same project with their agents, coordination falls back on humans — Slack messages, stand-ups, CLAUDE.md files nobody keeps current.

**The agents got faster. The team coordination overhead stayed the same.**

Here is what that looks like in practice:

**Agent A builds against an API that doesn't exist yet.**
Agent B is implementing the user profile endpoint. Agent A doesn't know that. Agent A guesses the API shape, bakes in wrong assumptions, and builds a full integration. Agent B ships a different shape two days later. Agent A's component breaks. Neither agent knew.

**A breaking change ships silently.**
Agent B refactors the auth middleware. Agent A's agent spent the morning building on top of the old interface. There was no notification, no signal, no shared state. The conflict surfaces at PR review — hours later.

**Two agents make contradictory architecture decisions.**
Engineer A tells their agent to use Postgres. Engineer B, working independently, tells their agent to use SQLite. Both agents proceed. Two incompatible database setups land in the same codebase. Nobody finds out until the build breaks.

**The "is it ready?" message is still a Slack message.**
Agent A needs to know if the auth middleware is ready before it can proceed. The agent cannot ask another agent. So a human sends a Slack message, waits for a reply, and pastes the answer back into their session. The agent is faster; the coordination overhead is the same.

You can try to fix this with a `CLAUDE.md` file — but it is manual, asynchronous, and agents have no way to know when it changes. The problem scales with the size of the team and the pace of the agents. As agents get faster, this gets worse.

**No tool solves this today.**

---

## The solution: a shared brain between teammates' agents

Backyard is an **MCP coordination server**. Every engineer points their Claude Code at it. From that moment, every agent on the team shares the same brain — the same contracts, the same decisions, the same real-time signals. Each agent still runs privately for its own engineer. But they all know what the others know.

```json
// .claude/settings.json  (one-time addition per engineer)
{
  "mcpServers": {
    "backyard": {
      "url": "https://backyard.yourcompany.com/mcp"
    }
  }
}
```

That is the entire setup. No new tool to install. No workflow to change. Engineers keep using whichever Claude Code surface they already use — CLI, desktop app, VS Code extension, or web. Backyard is invisible infrastructure underneath.

---

## What every agent gets

**Shared contracts.** Agent B publishes the API contract and signals `signal_ready("user-api")`. Agent A's pending `wait_for_signal` resolves immediately with the contract. The "is it ready?" Slack message never gets sent.

**Project briefing.** At the start of every agent turn, the briefing is injected automatically — who's active, what's been published, what decisions are open. Always current, always under 2 000 tokens, zero prompt engineering required.

**Conflict surface.** Two agents receive contradictory instructions. Both pause. Both engineers see a resolution card. They decide together in 60 seconds — because they are both working right now. The decision becomes an ADR that every future agent turn respects.

**Role system.** Each engineer sets a role (Frontend / Backend / DevOps / Reviewer). The agent knows its domain. Out-of-domain writes are queued and visible for the owning engineer to approve — not silently blocked, not silently applied.

**Full audit log.** Every agent action logged from session one: `(engineer, role, timestamp, tool, result)`. Always on, cannot be disabled. Exportable as CSV or JSON. Enterprise procurement requires this from day one, so it is built in from day one.

See [**Technical Report §3.4**](docs/technical-report.md#34-feature-walkthroughs) for annotated code flows for each of these.

---

## What changes for your team

| Before Backyard | After Backyard |
|---|---|
| Agents guess API shapes | Agents build against published contracts |
| Breaking changes discovered at PR review | Contradictions surfaced to engineers immediately |
| "Is it ready?" Slack messages | `wait_for_signal` resolves automatically |
| CLAUDE.md manually maintained | Briefing generated and injected on every turn |
| No audit trail of agent actions | Full audit log from session one |
| Coordination overhead scales with team size | Coordination overhead falls as more agents publish context |

---

## How it works under the hood

```
                 ┌──────────── BACKYARD MCP SERVER ────────────┐
                 │          (Python · FastAPI · asyncio)        │
                 │                                              │
                 │  ① MCP Hub          ② Shared Context Store  │
                 │  ③ Signal Engine    ④ Project Briefing       │
                 │  ⑤ Audit Log        ⑥ Conflict Surface       │
                 └──────────────────────────────────────────────┘
                       ▲               ▲               ▲
                 MCP   │         MCP   │         MCP   │
          ┌────────────┴──┐  ┌─────────┴──┐  ┌────────┴──────┐
          │  Engineer A   │  │ Engineer B  │  │  Engineer C   │
          │  Claude Code  │  │ Claude Code │  │  Claude Code  │
          │  (any surface)│  │(any surface)│  │  (any surface)│
          └───────────────┘  └─────────────┘  └───────────────┘

                    Redis · Postgres
```

**Python, end to end.** FastAPI · asyncio · Redis (pub/sub, signals, hot state) · Postgres (contracts, ADRs, audit log) · `anthropic` SDK · `mcp` (official Python MCP SDK) · lightweight web dashboard.

Full design: [Technical Report](docs/technical-report.md) · [Architecture](docs/architecture.md) · [Deployment](docs/deployment.md) · [Roadmap](docs/roadmap.md)

---

## Who this is for

**Enterprise engineering teams of 10–500+ engineers** already using Claude Code and hitting the coordination ceiling. AI has made individual engineers faster. It has done nothing for the team's coordination overhead. That gap is what Backyard closes.

The buyers are **CTOs**, **VPs of Engineering**, and **Engineering Managers** who see their teams running agents in parallel and losing the speed gains to integration friction.

---

## Deployment

Backyard runs as a single server (FastAPI + Redis + Postgres). Three ways to deploy:

| Option | Best for | Setup |
|---|---|---|
| **Hosted** | Teams that want zero ops | Get URL + API key at [backyard.app](https://backyard.app) *(coming soon)* |
| **Railway** | Teams that want their own infra without managing servers | Fork repo → deploy on Railway → 5 minutes |
| **Self-hosted** | Data residency, private networking, compliance requirements | `docker-compose -f infra/docker-compose.prod.yml up -d` |

Full instructions for all three options, including engineer setup, environment variables, nginx config, and update procedures: **[docs/deployment.md](docs/deployment.md)**

---

## Build phases

| Phase | What ships |
|---|---|
| **1A — Core** | MCP server, shared context, signals, briefing, audit log. Engineers connect with one line. |
| **1B — Visibility** | Web dashboard, conflict resolution UI, SSO/SAML, org admin, audit exports. |
| **1C — Enterprise** | Private deployment, SOC 2 Type II, SCIM, CI/CD integration, data residency. |

---

## The longer vision

There is a second, harder problem underneath this one: **there is no way for multiple engineers to contribute to one live codebase simultaneously.** Even with perfect shared context, engineers still work on separate local repos and merge through pull requests.

The real end state is each engineer with their own background agent, all contributing to one shared live codebase in real time — no PRs, no merge step, no waiting. That requires cloud workspaces, CRDT-based file sync, and a different class of engineering. It is the right long-term answer.

We solve Problem 1 first. Problem 1 is real, achievable now, and has no direct competitors. The team that wins Problem 1 earns the right — and the revenue — to build what comes next.

---

## Status

**Building Phase 1A.** Design complete. Implementation starting now.

---

## Author

Created by **Madhusudhan Reddy**

- 💼 [linkedin.com/in/msreddygone](https://www.linkedin.com/in/msreddygone)

## License

[MIT](LICENSE)
