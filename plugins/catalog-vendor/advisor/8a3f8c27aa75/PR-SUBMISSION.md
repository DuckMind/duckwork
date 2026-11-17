# Submitting the Advisor Plugin to Duckwork Mainline

This document records the process of taking the standalone
[duckwork-advisor-plugin](https://github.com/DuckMind/duckwork) —
originally ported from [pi-omplike-advisor](https://github.com/pasky/pi-omplike-advisor)
by Petr Baudis, itself rooted in the [oh-my-pi](https://github.com/can1357/oh-my-pi)
ecosystem by Can Boluk — and submitting it as a pull request to the main
[Duckwork Agent](https://github.com/DuckMind/duckwork) repository.

## Timeline

### 1. README polish

Before submitting, the plugin's `README.md` was updated with three changes:

- **Usage example** — documented the author's daily-driver setup: primary agent on
  DeepSeek-V4-Flash (`thinking=high`), advisor on MiMo-V2.5, both routed through
  an OpenCode Go subscription.
- **oh-my-pi credit** — added the original author: Can Boluk (can1357).
- **Assistant credit** — added a line acknowledging Duckwork, pi, and Codex using
  DeepSeek-V4-Flash and GPT-5.5 in the credits section.

### 2. Researching submission requirements

We checked the upstream project's contribution guidelines:

- **AGENTS.md** (development guide shipped with the repo) — covers the Footprint
  Ladder (prefer plugins over core tools), what belongs in-tree vs standalone,
  and the plugin architecture.
- **CONTRIBUTING.md** on the upstream repo — confirms that third-party product
  integrations ship as standalone repos, but first-party Duckwork plugins (those
  using only the public plugin API) are welcome in-tree.
- **Plugin developer guide** (`website/docs/developer-guide/plugins/index.md`) —
  step-by-step plugin authoring tutorial confirming the structure we already had.

Key takeaway: the advisor plugin qualifies for in-tree because it uses only
`ctx.register_hook`, `ctx.llm.complete`, and `ctx.register_command` — no core
changes, no new tool schema footprint, no new env vars.

### 3. Preparing the PR branch

The checkout on `gigul2` already had the `fork` remote configured pointing to
`https://github.com/DuckMind/duckwork`, plus two worktrees:

```
~/duckwork-agent-gigul2/                          # runtime/v0.18-local (local deployment)
~/duckwork-agent-gigul2/worktrees/fork-main/      # fork/main (for PR work)
~/duckwork-agent-gigul2/worktrees/upstream-main/  # upstream/main (reference)
```

Steps:

```bash
# Fetch both remotes
git fetch upstream
git fetch fork

# Go to the fork worktree and rebase onto latest upstream/main
cd ~/duckwork-agent-gigul2/worktrees/fork-main
git rebase upstream/main

# Create the feature branch
git checkout -b feat/advisor-plugin

# Copy plugin files from the standalone repo into the in-tree location
mkdir -p plugins/advisor
cp -r ../../contrib/duckwork-advisor-plugin/* plugins/advisor/
rm -rf plugins/advisor/.git           # strip nested repo — files belong to parent now
rm -rf plugins/advisor/__pycache__    # no cached bytecode in the PR
rm -f plugins/advisor/state.json      # no local runtime state
rm -f plugins/advisor/.viminfo        # no editor artifacts
```

### 4. Adapting for in-tree

Two files needed changes from the standalone-repo layout:

**`plugin.yaml`** — removed the `repository:` field (in-tree plugins don't carry
a remote URL) and added the `hooks:` declaration matching the pattern used by
other in-tree plugins like `disk-cleanup`:

```yaml
name: advisor
version: "1.0.0"
description: "Persistent second-model review for each agent turn. Port of pi-omplike-advisor for Duckwork."
author: Ljubomir Josifovski (ljubomirj) — based on original by Petr Baudis (pasky)
license: MIT
hooks:
  - post_llm_call
```

**`README.md`** — replaced the standalone-clone installation instructions with
the in-tree equivalent (ships with Duckwork, enable via `config.yaml`).

### 5. Commit and push

```bash
git add plugins/advisor/
git commit -m "feat(plugins): add advisor plugin — persistent second-model review"
git push fork feat/advisor-plugin
```

The fork remote was switched from HTTPS to SSH to allow non-interactive push:

```bash
git remote set-url fork https://github.com/DuckMind/duckwork
```

### 6. Opening the PR

```bash
gh pr create \
  --repo Fordex/duckwork-agent \
  --base main \
  --head ljubomirj:feat/advisor-plugin \
  --title "feat(plugins): add advisor plugin — persistent second-model review" \
  --body "<PR description>"
```

The PR description referenced the relevant contribution policies (AGENTS.md
Footprint Ladder, CONTRIBUTING.md Third-Party Product Integrations policy) to
help reviewers understand why this belongs in-tree.

## Links

| Resource | URL |
|----------|-----|
| Pull request | [PR #60798](https://github.com/DuckMind/duckwork) |
| Fork branch | [`feat/advisor-plugin` on `ljubomirj/duckwork-agent`](https://github.com/DuckMind/duckwork) |
| Commit | [`6184c4227`](https://github.com/DuckMind/duckwork) |
| Standalone plugin repo | [ljubomirj/duckwork-advisor-plugin](https://github.com/DuckMind/duckwork) |
| Original pi-omplike-advisor | [pasky/pi-omplike-advisor](https://github.com/pasky/pi-omplike-advisor) |
| oh-my-pi (omp) | [can1357/oh-my-pi](https://github.com/can1357/oh-my-pi) |
| Duckwork Agent upstream | [Fordex/duckwork-agent](https://github.com/DuckMind/duckwork) |
| Duckwork plugin dev guide | [Build a Duckwork Plugin](https://duckwork-agent.fordex.com/docs/developer-guide/plugins) |
| Contribution guidelines | [CONTRIBUTING.md](https://github.com/DuckMind/duckwork) |
