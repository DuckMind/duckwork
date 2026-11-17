# mindgraph — Duckwork memory provider

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

MindGraph semantic graph memory for [Duckwork Agent](https://github.com/DuckMind/duckwork), implemented as a [MemoryProvider](https://github.com/DuckMind/duckwork) plugin.

Every conversation opens a MindGraph session, bakes your active goals and policies into the system prompt, prefetches topic-relevant graph context each turn, exposes 5 graph-memory tools to the model, and ingests the full transcript on session end for 5-layer extraction (Reality, Epistemic, Intent, Action, Memory).

## Install

```bash
duckwork plugins install shuruheel/mindgraph   # prompts for MINDGRAPH_API_KEY
duckwork memory setup                          # pick "mindgraph" in the picker
```

`duckwork plugins install` clones the repo to `~/.duckwork/plugins/mindgraph/` and prompts for your `MINDGRAPH_API_KEY` (get one at [mindgraph.cloud](https://mindgraph.cloud)). `duckwork memory setup` then opens an interactive picker — select this plugin to install `mindgraph-sdk` and write `memory.provider: mindgraph` to `~/.duckwork/config.yaml`.

Optional overrides (not prompted — set manually in `~/.duckwork/.env` if needed):

```
MINDGRAPH_BASE_URL=https://api.mindgraph.cloud   # override for self-hosted
MINDGRAPH_AGENT_ID=duckwork                         # provenance tag on writes
```

Only one external memory provider is active at a time — setup will swap out any previously configured provider.

## What gets wired up

| MemoryProvider method | What it does |
|-----------------------|--------------|
| `initialize(session_id)` | Opens a MindGraph `Session` node (`duckwork-<session_id[:8]>`). Idempotent — safe for per-message gateway restarts. |
| `system_prompt_block()` | Injects the behavioral contract + current graph state (active goals, policies, open questions, open decisions, weak claims) into the cached system prompt. |
| `queue_prefetch(query)` | Fires hybrid FTS + semantic retrieval in a background thread for the *next* turn. |
| `prefetch(query)` | Returns the cached prefetch result as an ephemeral context block. |
| `get_tool_schemas()` | Exposes 5 tools to the model (see below). |
| `handle_tool_call(...)` | Dispatches tool calls to the MindGraph SDK. |
| `on_session_end(messages)` | Closes the Session node and ingests the full transcript for 5-layer extraction. |
| `shutdown()` | Drains the prefetch thread and closes any still-open session. |

Subagent and cron contexts skip session open/close (the plugin checks `agent_context` in `initialize()` kwargs) so internal orchestration doesn't pollute the user-facing graph.

## The 5 tools

| Tool | Purpose |
|------|---------|
| `mindgraph_remember` | Store knowledge — entities, observations, claims, preferences, notes |
| `mindgraph_retrieve` | Query the graph — hybrid FTS + semantic, structured queries, traversal |
| `mindgraph_commit` | Track agentic state — goals, decisions, plans, tasks, risks, questions |
| `mindgraph_ingest` | Bulk content ingestion (articles, transcripts, code) |
| `mindgraph_synthesize` | Project-scoped cross-document synthesis — mine signals, generate Article nodes |

See [`tools.py`](tools.py) for action tables and parameter details; the behavioral contract the agent sees is in [`provider.py`](provider.py).

## Architecture

MindGraph's 5-layer cognitive architecture:

- **Reality** — entities, observations, facts
- **Epistemic** — claims, evidence, questions, hypotheses, concepts
- **Intent** — goals, decisions, projects, milestones
- **Action** — risks, affordances, capabilities
- **Agent** — plans, tasks, execution tracking, governance policies

The behavioral contract injected into the system prompt teaches the agent when to route knowledge into which layer, with anti-patterns to avoid (bare entity nodes, session-memory drafting, content-derived commits, confidence inflation).

## Requirements

- Duckwork Agent with the MemoryProvider interface (`agent/memory_provider.py`) — upstream `Fordex/duckwork-agent` as of the `plugins/memory/` refactor
- Python ≥ 3.10
- A MindGraph API key

## Repo layout

```
mindgraph/
├── __init__.py       # register(ctx) — hands a MindGraphMemoryProvider to Duckwork
├── provider.py       # MindGraphMemoryProvider(MemoryProvider)
├── tools.py          # SDK glue: handlers, schemas, session helpers
├── plugin.yaml       # Duckwork manifest (pip_dependencies, requires_env)
└── after-install.md  # Rendered by Duckwork after install
```

## License

MIT
