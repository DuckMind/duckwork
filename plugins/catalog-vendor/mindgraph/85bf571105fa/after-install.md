# MindGraph memory plugin installed

Activate it as your memory provider:

```
duckwork memory setup
```

That opens an interactive picker — select **mindgraph**. Setup will:

1. Install `mindgraph-sdk` into the Duckwork environment.
2. Write `memory.provider: mindgraph` to `~/.duckwork/config.yaml`.

If you haven't already set your `MINDGRAPH_API_KEY` (get one at https://mindgraph.cloud), the plugin install step prompted for it. You can also add these optional overrides to `~/.duckwork/.env`:

```
MINDGRAPH_BASE_URL=https://api.mindgraph.cloud   # override for self-hosted
MINDGRAPH_AGENT_ID=duckwork                         # provenance tag on writes
```

Next conversation, Duckwork will:

- Open a MindGraph session node on the first turn.
- Bake your active goals, policies, open questions, and open decisions into the system prompt.
- Prefetch topic-relevant graph context each turn.
- Expose 5 tools to the model: `mindgraph_remember`, `mindgraph_retrieve`, `mindgraph_commit`, `mindgraph_ingest`, `mindgraph_synthesize`.
- Ingest the full transcript on session end for 5-layer extraction (Reality, Epistemic, Intent, Action, Memory).

Docs: https://github.com/shuruheel/mindgraph
