# Handflow — a Manus-style planning flow, native to Duckwork

The agent writes a step plan **before** it starts working, marks each step
`in_progress` / `completed` / `blocked` with a one-line note as it goes, and
replans mid-flight. You watch the same plan in a dockable desktop pane and can
nudge it with a click.

One stdlib-only tool (`handflow`), one right-rail pane, three backend routes,
plan state as plain JSON under `$DUCKWORK_HOME/handflow/`. No model calls of its
own, no network, no vendored runtime, nothing to keep up to date.

```text
HAND FLOW                                  1 blocked  [active]
Ship the catalog entry
───────────────────────────────────────────────●──────  2/5
 01  write the entry                    [✓]
 02  pin the commit sha                 [✓]
 03  open the PR to plugin-catalog      [→]   note: draft pushed
 04  wait on the merged sha             [!]
 05  announce it                        [ ]
plan_1789888793_9y8q                           12s ago
```

## Why

Autonomous work that is *watchable* beats autonomous work you have to trust.
OpenManus (MIT) popularised the planning-flow shape — a plan the agent rewrites
as it executes, with statuses and notes on every step. Duckwork already has the
model, the tools and the delegation; what it lacked was that shared, visible
plan. Handflow is that piece, written from scratch as a Duckwork plugin: the
planning-flow semantics are ported from OpenManus's `PlanningFlow`, the
implementation and the pane are ours.

## Install

Inside Duckwork:

```bash
duckwork plugins install handflow          # from the catalog
duckwork plugins enable handflow           # user plugins are opt-in
```

From a checkout:

```bash
git clone https://github.com/DuckMind/duckwork
duckwork plugins install --path ./duckwork-handflow
duckwork plugins enable handflow
```

Then restart the desktop app: the **Plan** pane appears in the right rail and
the `▤ n/m` chip in the status bar. State lives in
`$DUCKWORK_HOME/handflow/plans/*.json` (override the directory with
`HANDFLOW_HOME`); it is per-profile, and deleting the folder just forgets plans.

## Using it

The agent drives it. Ask for anything with more than a couple of steps and it
should call the tool first:

> **you:** port the price parser to the new adapter and prove it on last week's data
>
> **agent:** *(handflow start — goal + 5 steps)* → works → *(handflow complete 1 … note "…")*

You can also call it yourself from chat — `handflow` is a normal tool:

| action | what it does |
| --- | --- |
| `start` | create the plan: `goal` + `steps` (list, or bullets in a string). First step goes in progress |
| `plan` | show the active plan |
| `begin` / `complete` / `block` / `reopen` | move a step; add a `note` |
| `note` | attach a note to a step |
| `add` | insert a step (replanning); `position` is 1-based |
| `finish` / `abort` | close the plan (`finish` refuses while steps are open unless `force` is set) |
| `list` / `use` | recent plans / pin one as active |

Steps are addressed by `1`-based number, `id` (`s02`), a title substring, or
nothing at all (the current step). Every call returns the rendered plan, so the
agent never spends a second call to look at its own state.

Rules worth knowing: starting a step auto-completes the previous one; completing
the last step closes the plan; adding a step or reopening one reopens it.

## What it does not do

- **No model calls.** The agent is the intelligence; Handflow stores the plan.
- **No network, no subprocess, no self-update.** The security scan runs clean
  and the plugin never fetches its own code.
- **No new palette.** The pane uses Duckwork theme variables (`--ui-*`,
  `--foreground`), so it reskins with whatever theme you run.
- **No pane-side notes.** One-line toggles only — prose belongs to the agent,
  which is why the note field is written by the tool, not typed in the UI.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install pytest pyyaml fastapi httpx
.venv/bin/python -m pytest                  # 41 tests: store, tool, routes, contract
node --test tests/desktop.test.mjs          # 6 tests: registration + render, no app needed
duckwork plugins validate .                   # the catalog gate (14 checks)
```

`tests/desktop.test.mjs` runs `desktop/plugin.js` in a `node:vm` with a stubbed
SDK, so the pane's registration shape, its render output, its click payload and
its poll interval are all checked without launching the app.

## Licence

MIT © Ritesh Patel. The planning-flow design (statuses, notes, step-wise
execution) is ported from [OpenManus](https://github.com/FoundationAgents/OpenManus)
(MIT, MetaGPT/FoundationAgents); no OpenManus code is included. Handflow is an
independent plugin and is not affiliated with, or endorsed by, Manus or the
OpenManus project.
