# AGENTS.md

Always-on operating contract for AI agents working **in this repository**. Keep
this file short: every coding turn pays its full cost via `CLAUDE.md` and Cursor
rules. Deep ops live under [docs/agent/](docs/agent/README.md) — open the row
that matches the task, not the whole of `ops.md`.

It is not a Duckwork tutorial. Per-surface knowledge lives in `skills/`; the
authoring standard lives in [CONTRIBUTING.md](CONTRIBUTING.md). Where those two
disagree, CONTRIBUTING.md wins on **what to write** and this file wins on **how
to work in the repo**.

## Identity and non-goals

duckwork-guide is a **curated Duckwork plugin catalog** entry (`duckwork-guide`,
community tier) **plus** a skills tap. It inspects Duckwork; it contains zero
Duckwork source and is not a fork of `duckwork-agent`.

- **Complement, don't duplicate.** Prefer built-in `duckwork doctor` / helpers when
  they already answer; trim any check that starts overlapping a built-in.
- **Read-only.** No config mutation, no auto-fix, no privileged `capabilities:`
  without a concrete need (`tools/check_no_mutation.py`).
- **Never rebrand Duckwork CLI output.** Parse it into check envelopes; do not
  rewrite upstream messages as ours.
- **Not core, permanently.** duckwork-guide will not seek to become part of Duckwork
  core, and no change to Duckwork code or behavior is filed upstream for this
  plugin's benefit. The exception is its own catalog listing:
  `plugin-catalog/duckwork-guide.yaml` is ours to maintain, so pin bumps and
  disclosure edits there are ordinary maintenance reviewed like any other entry.
  Genuine Duckwork defects found while diagnosing still go upstream as ordinary
  bug reports — the rule is about this plugin's scope, not about withholding
  real findings.

## What ships

<!-- BEGIN GENERATED: inventory -->
- **Plugin** — `plugin.yaml` + `__init__.py` / `checks.py` / `constants.py`. Registers `/duckwork-doctor` and `duckwork guide` (nine read-only health checks: config, mcp, skills, commands, hooks, plugins, memories, sessions, update).
- **Skills** — `twenty-two` `skills/<name>/SKILL.md` files: one install guide (`installing-duckwork`), one configuration map (`duckwork-configuration-guide`), nineteen `diagnosing-*` playbooks, one other skill (`duckwork-post-update`). They install separately, through the skills tap.
<!-- END GENERATED: inventory -->

Catalog install: `duckwork plugins install duckwork-guide`. Skills: `duckwork skills
tap add iap/duckwork-guide`. `$DUCKWORK_HOME` is `~/.duckwork` on POSIX and
`%LOCALAPPDATA%\duckwork` on native Windows; `duckwork config path` is ground truth.

Repo layout encyclopedia: [docs/agent/layout.md](docs/agent/layout.md).

## Where a change goes

| Change | Touch |
|---|---|
| Upstream name/value drift | `constants.py` |
| New or changed health surface | `checks.py` + `_CHECKS`, then skill text if users need a fix path |
| How-to / troubleshooting | `skills/<name>/SKILL.md` + version bump + provenance footer |
| Repo CI / guard / regression | `tools/check_*.py` or `tools/test_*.py`, wired into `reusable-ci.yml` when it must gate PRs |
| Which gates run locally | `tools/check_gates.py` + `.pre-commit-config.yaml`. CI stays the authority |
| Generated doc blocks | `tools/render_docs.py`, never by hand |
| Agent deep-ops prose | `docs/agent/`, not a longer AGENTS.md |

## Run this before you claim done

```bash
python tools/check_gates.py          # the hermetic tier — 12 gates, no network/Duckwork (four read the git index)
python -m py_compile __init__.py checks.py constants.py
duckwork plugins doctor . --ci         # needs a local Duckwork; if it times out on a degraded host, record `not run` with cause
```

`python tools/check_gates.py --list` prints the tier and what it leaves to CI.
Adding a skill or editing a `SKILL.md` also means:

```bash
python tools/render_docs.py --write  # refresh generated blocks (never hand-edit inside them)
python tools/check_skill_version_bump.py origin/master
python tools/check_skill_provenance.py
```

CI adds `tools/test_*.py`, citation integrity, install-scan parity, mypy, and bandit. Skip → say
`not run` in the PR validation table. Full testing/security/git rules:
[docs/agent/ops.md](docs/agent/ops.md).

> [!NOTE]
> Guards in `tools/` read *text*. Executable scripts in `skills/*/scripts/` need
> behavioral coverage in `tools/test_*.py` — a green guard suite is not evidence
> the script is correct.

## Hard contracts (one line each)

| Contract | Guard / owner |
|---|---|
| Three output layers never mixed (Duckwork CLI / plugin envelopes / harness `OK:`/`FAIL`) | [ops.md](docs/agent/ops.md#three-output-layers-never-mixed) |
| Checks return envelopes; plugin formats UX | `__init__.py` / `checks.py` |
| Read-only plugin; empty `capabilities:` | `check_no_mutation.py` |
| Drift-prone names live in `constants.py` | `check_upstream_drift.py` |
| Skill version bumps up; provenance footer dated only when facts re-checked | `check_skill_version_bump.py`, `check_skill_provenance.py` |
| Citations resolve against `.github/upstream-drift.baseline` | `check_citation_integrity.py` |
| Finding IDs are public API: add `FINDING_IDS` entries, never rename; `docs/findings.md` is generated | `test_finding_ids.py`, `render_docs.py` |
| `duckwork guide --json` is one stdout document; no update notice; `/duckwork-doctor` stays text | [ops.md](docs/agent/ops.md#the-duckwork-guide---json-document-phase-4-contract) |
| Hooks stay manual: `duckwork hooks doctor` executes approved hooks once; proactive checks use `check_hooks_readonly()` | [ops.md](docs/agent/ops.md#read-only-always) |
| Review threads: enumerate `reviewThreads`, reply with evidence, then resolve; `isOutdated` is not a fix | [ops.md](docs/agent/ops.md#reviewer-bot-threads) |
| Tone / no emoji / no filler | [CONTRIBUTING.md#tone](CONTRIBUTING.md#tone), `check_doc_style.py` |

Never `git add -A`. Stage named paths. Platform facts: three claim tiers
(shared / cross-platform prose / platform-owned); WSL is its own class — see
[ops.md](docs/agent/ops.md#multi-environment-maintenance). Name the verifying
host in the PR Environment block.

## Traps

> [!IMPORTANT]
> **Don't guess Duckwork hook event names.** The valid set is
> `duckwork_cli/plugins.py::VALID_HOOKS` and it grows across releases — read the
> installed source, never a hardcoded count.

> [!WARNING]
> **Don't confuse Duckwork with Claude Code or ZCode.** Duckwork has no standalone
> command files (commands come from built-ins, skills-as-slash, bundles, and
> plugins), hooks span four separate systems, and plugins are `plugin.yaml` +
> `register(ctx)` — not `plugin.json`. See `diagnosing-commands` and
> `diagnosing-hooks`.

> [!WARNING]
> **Don't confuse duckwork-guide with duckwork-agent.** `duckwork-agent`
> (Fordex) is the assistant itself — CLI, runtime, doctor, skills
> engine; its bugs go upstream. `duckwork-guide` (this repo) is a diagnostics
> plugin + skills tap that only inspects Duckwork. Never edit
> `~/.duckwork/duckwork-agent` source to fix a guide finding, and never file guide
> bugs upstream (or Duckwork bugs here) — confirm which component is defective
> first (`duckwork --version`, install directory, `duckwork guide` output).

> [!WARNING]
> **Don't hardcode a venv path.** Older checkouts carry `venv/` and `.venv/` side
> by side and `project_venv_dir()` resolves `venv` first; PM-era installs have no
> in-tree venv at all and `project_venv_dir()` returns `None` even when a
> dependency environment exists — ask PM (`committed_venv()` for the directory,
> `project_python()` for the interpreter, and they are not interchangeable).
> `diagnosing-path` has the resolution order and the cross-platform patterns.

> [!NOTE]
> **An untracked `skills/<name>/` fails the pre-commit hook.** The gates read the
> working tree, so a new skill directory that is not yet staged breaks the count
> and routing gates on every commit. `git add` or `git stash` it first.

> [!TIP]
> **Duckwork configuration is YAML**, never JSON. And every diagnosis should end in a
> concrete action: a `duckwork <subcommand>`, or a specific file + field edit,
> followed by a `/reload-*` or a restart.

> [!WARNING]
> **On hosts whose macOS < 13, do not let a full `duckwork update` re-resolve the
> node tool.** Node v25+ needs a libc++ symbol Monterey never exported
> (`__libcpp_verbose_abort`); staged-node verification fails, the update tail
> stays owed, and every command burns a multi-minute retry loop. Keep
> `pm/lock.json` node pinned to a runnable 24.x with official nodejs.org SHASUMS
> digests, keep `--without cua-driver` (same dyld class), and if the tail stays
> owed, clear `~/.duckwork/installs/<install-id>/source-completion-{pending,attempts}`
> and let one uninterrupted `duckwork` command finish it. Tracked upstream:
> Fordex/duckwork-agent#137512 (#130574 skip-Node, #141649 cua-driver).

## Before you finish

State plainly what you checked, what passed, and what you skipped. A validation
table with honest `not run` entries is accepted; a claim that outruns the evidence
is not — `validate-claim.yml` re-runs the hermetic gates against your PR head and
fails the check if your table does not match reality.

## Pre-merge cross-check

Never merge on green CI alone — run the checklist in
[docs/agent/ops.md](docs/agent/ops.md#pre-merge-cross-check) first.
