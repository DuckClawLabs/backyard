# Contributing to Backyard

Backyard is being built **in the open** — the white paper's whole argument is that whoever closes this
gap *and documents the journey publicly* earns the credibility of having seen a category before it had a
name. Contributions, critiques, and replication attempts are all welcome.

## Where things stand

The project is in the **design phase**. The blueprint lives in [`docs/`](docs/):

- [`docs/technical-report.md`](docs/technical-report.md) — the full design.
- [`docs/architecture.md`](docs/architecture.md) — components + data flows.
- [`docs/roadmap.md`](docs/roadmap.md) — phased plan.

Start there. If you disagree with a design decision, open an issue — the open questions in
[§16 of the report](docs/technical-report.md#16-open-questions) are the liveliest places to push.

## Build order (when implementation starts)

Per the report, the riskiest surfaces come first:

1. `protocol/` — the shared Pydantic event/message models.
2. `sync/` — the CRDT live-edit core, tested in isolation.
3. `gateway/` — the Agent Gateway (agent edits applied as CRDT updates).
4. `watcher/` — the Semantic Conflict Watcher.
5. `mcp_hub/` — the inter-agent MCP tools.
6. `client/` — the Textual TUI.

## The most valuable contribution

The MVP exists to answer one question (see the report, §10.1):

> *Do two humans + two background agents on one live project ship faster than two humans on separate
> sessions merging through pull requests?*

If you run that experiment — in either direction — and write up the result honestly, that is the single
most useful thing you can add right now.

## Conventions

- Python ≥ 3.11, formatted and linted with **ruff**, typed with **mypy** (strict).
- Tests with **pytest** + **pytest-asyncio**; the sync engine and watcher get correctness tests *first*.
- Conventional, descriptive commit messages.
