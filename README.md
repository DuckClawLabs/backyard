# Backyard

**Multi-human, multi-agent collaborative coding.**

Every AI coding agent today assumes *one human per session*. But software is built by teams. **Backyard**
is the design for the missing quadrant: *many humans, many agents, one shared project, in real time* —
a shared workspace where each engineer keeps their own AI agent, everyone sees the work as it happens,
the agents coordinate instead of trading pull requests, and disagreements are settled **together, in one
session** rather than days later in review.

Companion to the white paper *The Unbuilt Product* (M. Reddy, June 2026).

## Status

**Design phase.** This repo currently holds the technical report and architecture — the blueprint for
implementation. No application code yet.

## Documents

- **[Technical Report](docs/technical-report.md)** — the full design, end to end.
- **[Architecture Reference](docs/architecture.md)** — condensed components + data flows.
- **[Roadmap](docs/roadmap.md)** — MVP, platform, and product phases.

## The one question

> *Do two humans driving agents in one shared session ship faster than two humans on separate sessions
> merging through pull requests?*

The 4-week MVP exists to answer exactly that. Everything else follows from the result.

## Core design choices

- **Stack:** Python — FastAPI + asyncio, Redis (locks/pub-sub), Postgres (durable state), the
  `anthropic` and `mcp` SDKs, a Textual terminal client.
- **Conflicts are surfaced to the session.** When two people (or their agents) collide — on a file or on
  contradicting instructions — the conflict is posted into the one shared session and the humans **choose
  between themselves**. No silent "higher-rank wins."
- **Roles are hints, not handcuffs.** Domain ownership routes work and sets defaults; helping elsewhere
  just asks first, in the open.
- **Agents coordinate through a structured substrate** (contracts, decisions, file summaries, signals) —
  never by sharing raw conversation history — so context windows and costs stay bounded.
