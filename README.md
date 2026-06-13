# Backyard

**Multi-human, multi-agent collaborative coding.**

Every AI coding agent today assumes *one human per session*. But software is built by teams. **Backyard**
fills the missing quadrant with a specific shape:

> Many humans log in. **Each gets their own private session with their own background AI agent.** All of
> those sessions contribute to **one live shared project at the same time.** Everyone's edits, and every
> agent's edits, appear live for everyone. No pull requests, no merge step. When two changes truly
> conflict, the collision is surfaced to the humans involved and they **choose between themselves.**

One shared project that the whole team contributes to at once, in real time, with an AI agent working
alongside each person. Companion to the white paper *The Unbuilt Product* (M. Reddy, June 2026).

## Status

**Design phase.** This repo holds the technical report and architecture — the blueprint. No application
code yet.

## Documents

- **[Technical Report](docs/technical-report.md)** — the full design, end to end.
- **[Architecture Reference](docs/architecture.md)** — components + data flows.
- **[Roadmap](docs/roadmap.md)** — MVP, platform, and product phases.

## The shape

- **Project** = the shared, live codebase. The unit everyone collaborates on.
- **Session** = one human's private space: their chat, context, and **background agent**. Many sessions
  attach to one project. You see others' *edits and cursors*, not their private agent chat.

```
                  ┌──────── ONE LIVE PROJECT (CRDT) ────────┐
                  └──────────────────────────────────────────┘
                     ▲           ▲           ▲           ▲
               Session A    Session B    Session C    Session D
              (human+agent, private — each edits the live project)
```

## The one question

> *Do two humans + two background agents on one live project ship faster than two humans on separate
> sessions merging through pull requests?*

The 4-week MVP exists to answer exactly that.

## Core design choices

- **Stack:** Python — FastAPI + asyncio, **`pycrdt`** (a CRDT for real-time convergence, Yjs-compatible)
  for live sync, Redis (presence/pub-sub), Postgres (durable state), the `anthropic` and `mcp` SDKs, a
  Textual terminal client. The CRDT backend is Yjs-wire-compatible, so a later web editor is a thin
  client over the *same Python server* — the team stays in Python.
- **Two-layer conflicts.** Text **auto-converges** (CRDT, lossless, no merge step). Only *semantic*
  conflicts — code that converged but is broken or contradictory — **surface to the humans involved**,
  in a shared view, to choose between themselves. No silent "higher-rank wins."
- **Agents are per-person and run in the background.** Each session's agent edits the live project the
  same way its human does — streaming, live, attributed.
- **Roles are hints, not handcuffs.** Domain ownership routes work; helping elsewhere just asks first.
