# Contributor checks (not ordinary user setup)

The plugin code is stdlib-only and imports host modules lazily. Test from an isolated
checkout, with fixture homes under the checkout or unique temporary directories
there; never point tests at an active user's home, and use that checkout's own Python.
The canonical suite command, the full gate block, the strict-admission rules, and the
review checklist live **once** in
[CONTRIBUTING.md](https://github.com/DuckMind/duckwork)
— read them there; this file keeps only the one recovery command that has no other
home. An apparent bug gets a reproduction and a focused failing (RED) check before
any fix.

## Build-lane hygiene and lane recovery

When a workflow build lane runs under this plugin's own runner: never check a base
ref out over a dirty tree to produce a failing run (that overwrites uncommitted work
in place). Commit tests first, use a throwaway detached worktree or a named stash
for the failing state, and bank a work-in-progress commit before the child hits its
turn cap. If a lane still dies with work uncommitted, recovery exists:

```sh
python3 scripts/lane_recover.py --run <id> --node <node> [--out <dir>]
```

It replays the lane's journaled file writes from the profile's session database
(opened read-only) into a restore directory — a triage list by default, files plus
an unmatched-patch report with `--out`. The replay and the prompt-side hygiene
preamble are pinned by their tests under `tests/`.
