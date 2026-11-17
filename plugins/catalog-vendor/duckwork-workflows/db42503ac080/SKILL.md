---
name: workflow
description: "Workflow fan-out audit and census: run agent graphs"
version: 1.3.6
metadata:
  duckwork:
    tags: [workflows, fan-out, audit, census, orchestration]
---

# Workflow authoring (1.3.6)

Requires Duckwork Agent v2026.9.21 or newer (package >=0.21.4). A Desktop gate answer
reaches the run owner's chat via the composer SDK; on older builds it may only insert
draft text — type the resume line in the owner chat yourself. Before disabling the
plugin, list runs and stop each live run with `workflow{action:"stop",run_id:<id>}`.

Use the `workflow` tool when a task needs independent lanes, a human gate, or a
resumable graph; for one or two independent calls, delegate instead. The authoring
agent owns the graph and its side effects; the dashboard is a reader, not an executor.

## Smallest working graph

Build `{ "name": "check", "nodes": [{"id":"inspect","type":"agent","goal":"Inspect the
specified target. Return one fenced JSON object."}] }`. Submit with
`workflow{action:"run", graph:<object>}`, then carry the returned `run_id` into
`workflow{action:"wait", run_id:<id>}` and stay in that loop until a terminal state —
ending your turn right after `run` is how runs stall.

## Authoring rules

- `after` orders nodes AND injects each direct parent's committed output under
  `## Inputs`; `inputs:["a.key"]` picks a dotted path or non-parent ancestor,
  `fanout.items_from:"a.items"` an upstream `items` array. A missing input fails at
  spawn.
- A node `schema` makes the runner write the reply contract into the prompt — keep
  contract prose out of goals.
- Independent tasks: separate nodes or one `fanout` with `items`. `quorum` races:
  once N succeed, the rest are cancelled — `quorum_drain_s:<s>` (default 0) gives
  running stragglers a drain window to land before that cancel.
- Shared settings go in a graph-level `defaults` once. Leave node budgets unset and
  name a `shape`; see [budgets](references/budgets.md). A constant travels as an
  `echo` node, never an agent spawn.
- Routing: an unset `model` rides the seat default, including fan-outs — name
  `model` (with `provider`) per node only when routing matters; never change
  persistent model preferences to make a graph work. A configured tier, alias, or
  literal is a request, not a guarantee — inspect the returned routing table and its
  errors before trusting execution. Pins are fail-closed (`require_route`): a dead
  pin or fallback-ladder answer refuses the launch (`route_unavailable`) instead of
  billing another model; opt into the ladder with `require_route:false`. See
  [grammar](references/grammar.md).
- A `gate` with `question`+`options` holds until you present it and `release` the
  owner's answer; a decorative gate self-releases on `hold_timeout`+`default_option`;
  machine waits use `gate.wait`. A false `when` prunes its gate and exclusively
  dependent arms; `on_skip:"pass"` runs descendants anyway — deliberate use only.
  `when` belongs on gates; unknown fields are rejected. Examples: `approve-publish`,
  `branch-on-verdict`. Details: [grammar](references/grammar.md).
- `profile` runs a node AS a named teammate: DELEGATION, not isolation — same UID,
  the target's SOUL/memory/`.env`/tools; the target's `workflow_team.json` must list
  the launcher in `accept_from`; `default` is never a target.
- `requires` on an agent/gate fails the node (`error_class:"precondition"`, zero
  spawns) when an ancestor's committed output lacks a listed path — the run FAILS,
  never skips quietly; skip-on-missing is a `when` gate with `on_skip:"prune"`.
- After-edges block on a `partial` (harvest-on-death) ancestor
  (`blocked_by_partial_ancestor`); consume the harvest with `after_partial:true`.

## Run and handoff

- `running` needs a verified live runner; `interrupted` means unfinished work without
  one — inspect surviving outputs, then `wait` to resume. Fatal runner errors are
  `failed`, not respawn loops; held gates are not running. Every `status`/`wait`
  payload carries `next` — do what `next` says, `wait` until it is empty; `next` is
  derived, never a guess. Before `amend` or stop, read the failed node's `node_facts`
  (error_class from the closed set; `cancelled` is never a failure) and committed
  outputs. `amend` submits the WHOLE replacement graph; `run`/`amend` `dry_run:true`
  write nothing; `stop` is terminal. Details: [operations](references/operations.md).
- Lint before launching with `workflow{action:"validate", graph:…}` — the door's
  whole validation, zero writes, no liveness ping.
- Shelf: `save` reusable graphs with `tags` reused verbatim from `library`'s
  `tag_vocab` — never coin unseen tags; resaving without `tags` keeps them.
  `library` lists; `run` with `from:<name>` replays. Off-shelf graphs go to `submit`
  with `why_not_library` (>=80 chars): quarantine for review, never the shelf.
  `save` +`source:` is attribution, never access control. Details:
  [grammar](references/grammar.md).
- No double-dispatch for pollers: `run` with `lane_key:<key>` — while an UNFINISHED
  incumbent holds the key, a second `run` is deduped, never spawns. `needs_resume`
  means `wait` it — never replace it; `stop` is the explicit abandonment. Keys are
  global per runs root; prefix `<team>/` yourself. Details:
  [operations](references/operations.md).
- Report a finished run by metrics (token in/out, api calls, tool calls), not the
  dollar figure: `estimated_cost_usd` is a price-table estimate (subscription routes
  report `included`) and reads badly as spend.
- Put the `card` line alone on its own line, in plain prose (never in backticks or a
  fence — a code-blocked directive renders as dead text, not a card), in the reply
  that launches a run and the one that reports it. The desktop strip shows every run
  of this chat regardless.
- `graph_path` replaces embedding on run/save/amend/validate: a caller-authorized
  absolute JSON file, exactly one graph source. [grammar](references/grammar.md).
  File-shareable graphs: [portable](references/portable.md).

The graph vocabulary lives in [grammar](references/grammar.md); read-model/recovery in
[operations](references/operations.md); build lanes and long-run babysitting in the
[operator playbook](references/operator-playbook.md). [Development
checks](references/development.md) are for contributors, not ordinary-user prerequisites.
