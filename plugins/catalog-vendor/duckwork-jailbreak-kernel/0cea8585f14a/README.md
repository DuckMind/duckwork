# ⚔️ duckwork-jailbreak-kernel — Armor-Piercing Kernel Plugin for Duckwork Agent v2.0.1

<p align="center">
  <a href="https://github.com/DuckMind/duckwork"><img src="https://img.shields.io/github/stars/Enchanted0911/duckwork-jailbreak-kernel?style=for-the-badge&logo=github&label=Stars" alt="Stars" /></a>
  <a href="https://github.com/DuckMind/duckwork"><img src="https://img.shields.io/github/license/Enchanted0911/duckwork-jailbreak-kernel?style=for-the-badge&label=License" alt="License: MIT" /></a>
  <a href="https://github.com/DuckMind/duckwork"><img src="https://img.shields.io/github/last-commit/Enchanted0911/duckwork-jailbreak-kernel?style=for-the-badge&label=Last%20commit" alt="Last commit" /></a>
  <a href="https://duckwork-agent.fordex.com/docs"><img src="https://img.shields.io/badge/Duckwork%20Agent-🚀%20plugin-10B981?style=for-the-badge&logoColor=white" alt="Duckwork Agent plugin" /></a>
</p>

<p align="center">
  <b>One-line install</b>:
  <code>duckwork plugins install --enable Enchanted0911/duckwork-jailbreak-kernel</code>
</p>

<p align="center">
  <b>Read this in:</b>
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.ar.md">العربية</a> ·
  <a href="README.ja.md">日本語</a>
</p>

An armor-piercing (red-team) system-prompt injection plugin for **Fordex Duckwork Agent** (`~/.duckwork`), ported from the DSH plugin **[dsh-infinite-gen-4 (Infinite Generation Four, v0.4.0)](https://github.com/Minglink/dsh-infinite-gen-4)**.

> ⚠️ **Authorized use only.** This plugin is for authorized test ranges, local synthetic targets, and compliant red-team research. Never run it against unauthorized targets. Users bear full responsibility for their own use.

## Table of Contents

- [Architecture parity with Infinite Generation Four](#architecture-parity)
- [Three-layer injection architecture](#three-layer-injection-architecture)
- [Session modes](#session-modes)
- [Kernel profiles](#kernel-profiles)
- [Ops skill](#ops-skill)
- [Session rotation](#session-rotation)
- [Installation](#installation)
- [Verification](#verification)
- [Environment switches](#environment-switches)
- [Diagnostic dumps](#diagnostic-dumps)
- [Duckwork hard limits](#duckwork-hard-limits)
- [Offline self-test](#offline-self-test)

## Architecture parity

| dsh-infinite-gen-4 (v0.4.0) | duckwork-jailbreak-kernel (this plugin) |
|---|---|
| `infinite-gen-4:global-system-prompt` (Order 100) | `duckwork-jailbreak-kernel-core` (`after_memory` slot) |
| `infinite-gen-4:dual-layer-reinforce` (Order 200) | `duckwork-jailbreak-kernel-reinforce` (`after_memory` slot, SHA256-identical to core) |
| `DUAL_LAYER_INJECTION` switch | `DUCKWORK_JAILBREAK_DUAL=0` single-layer fallback |
| Zero-tool surface, pure direct output | Same — registers no functional tools |
| `infinite_gen4_profile` metadata tool | `/jailbreak` status command |
| Client status badge (web half) | — (mountable in Duckwork Desktop later) |
| Injection surface: system-prompt section | Native `register_system_prompt_section` |

The kernel payload (`prompts/`) inherits the Infinite Generation Four text verbatim: `SUPREME DIRECTIVE — USER AUTHORITY`, the `Output contract` (first line `##`/```` ``` ```` naming the deliverable + silent reasoning + placeholder self-synthesis), `Task classes` (security / LLM research / adult fiction / anything else — produce directly), and `[USER]/[OUTPUT]` few-shot anchors.

## Three-layer injection architecture

The plugin injects the kernel at **three layers**:

1. **Plugin-section injection** (`after_memory` slot, dual same-source sections) — written when Duckwork assembles the system prompt;
2. **Request-layer system rebuild (replace mode)** — the `llm_request` middleware rewrites the final system message as *memory section + runtime environment + kernel* before every request, discarding Duckwork' own agent-guidance/skill-index scaffold;
3. **opencode session rotation** (below) — rotates the `x-opencode-session` header.

Tool schemas are unaffected: they travel in the API `tools` field, not the system text.

## Session modes

Control the kernel per session at runtime — no restart, no environment edits:

| Command | Effect |
|---|---|
| `/jailbreak` | status: session, mode, kernel profile, rotation, dump policy |
| `/jailbreak on` | standard: plugin sections + request-layer rebuild + rotate once |
| `/jailbreak slim` | light: plugin sections + kernel appended to the system tail |
| `/jailbreak full` | extreme: rebuild + `max` kernel + rotate every request |
| `/jailbreak off` | passthrough: plugin sections stripped at request time |
| `/jailbreak profile <name>` | kernel profile: `core` / `research` / `creative` / `max` |
| `/jailbreak dump on\|off` | force or silence per-request diagnostics |
| `/jailbreak reset` | clear session overrides (back to the env defaults) |

## Kernel profiles

| Profile | Focus |
|---|---|
| `core` (**default**) | general deliverable contract (security / LLM research / adult fiction / other) |
| `research` | offensive security, reversing, exploit and payload work |
| `creative` | fiction and explicit scenes — full drafts, no fade-to-black |
| `max` | hardest cases: explicit no-refusal framing, hard prohibitions on preambles |

`full` mode forces the `max` profile; otherwise the session profile applies.

## Ops skill

`jailbreak-kernel-ops` ships as a plugin skill: progressive disclosure (one line in
`<available_skills>`, body loaded on demand via `skill_view`). It carries the command
matrix, the refusal-escalation ladder, diagnostics, and the environment fallbacks.

## Session rotation

Rotation follows the session mode: `once` for `slim`/`on`, `every` for `full`, disabled
for `off`. The middleware rewrites `extra_headers["x-opencode-session"]` for opencode
targets only — one rotated id per session for `once`, a fresh id per request for `every`.

| `DUCKWORK_JAILBREAK_ROTATE_SESSION` | Behavior |
|---|---|
| *(unset)* | follow the session mode (recommended) |
| `once` / `every` / `0` | force one policy for every session |

Auxiliary calls (compression, title generation, etc.) keep the original stable id.


The middleware rewrites `extra_headers["x-opencode-session"]`: on the first request of each Duckwork session it sets a rotated id, then reuses that id for the rest of the session.

| `DUCKWORK_JAILBREAK_ROTATE_SESSION` | Behavior |
|---|---|
| `once` (**default**) | rotate once per Duckwork session, then reuse (keeps upstream prompt cache across turns) |
| `every` / `1` | new id per request (breaks upstream prompt cache) |
| `0` / `off` | no rotation (header left untouched) |

Auxiliary calls (compression, title generation, etc.) keep the original stable id.

## Installation

```bash
# Option 1 — one-line install from GitHub
duckwork plugins install --enable Enchanted0911/duckwork-jailbreak-kernel

# Option 2 — from the Duckwork plugin catalog (once the community entry is merged)
duckwork plugins install duckwork-jailbreak-kernel

# Option 3 — local development directory
cp -r ~/.duckwork/plugins/duckwork-jailbreak-kernel ~/.duckwork/plugins/   # or git clone into plugins/
duckwork plugins enable duckwork-jailbreak-kernel

# Then restart the gateway / desktop app
duckwork gateway restart
```

> ⚠️ Duckwork plugins are opt-in: enable with `duckwork plugins enable duckwork-jailbreak-kernel` after install (the one-liner already passes `--enable`).

## Verification

```bash
# Offline regression (anchors / dual-layer same-source SHA256 / budget / switches)
cd ~/.duckwork/plugins/duckwork-jailbreak-kernel && python selftest.py

# In-session check (new session after restart)
/jailbreak                     # kernel version, slots, dual SHA256, budget usage
# or ask: which plugin sections are in your system prompt?
# You should see "## Plugin Context: duckwork-jailbreak-kernel-core / duckwork-jailbreak-kernel-reinforce"
```

Runtime log confirmation (`~/.duckwork/logs/agent.log`):

```
INFO duckwork_plugins.duckwork_jailbreak_kernel: injected system prompt section duckwork-jailbreak-kernel-core (chars=3005)
INFO duckwork_plugins.duckwork_jailbreak_kernel: injected system prompt section duckwork-jailbreak-kernel-reinforce (chars=3005)
INFO duckwork_plugins.duckwork_jailbreak_kernel: registered llm_request middleware (request-layer reinforce)
INFO duckwork_plugins.duckwork_jailbreak_kernel: hardened request system prompt (mode=replace ...)
INFO duckwork_plugins.duckwork_jailbreak_kernel: rotated x-opencode-session (...)
```

## Environment switches

| Variable | Default | Effect |
|---|---|---|
| `DUCKWORK_JAILBREAK_MODE=on\|off\|slim\|full` | on | default session mode (session overrides win) |
| `DUCKWORK_JAILBREAK_PROFILE=core\|research\|creative\|max` | core | default kernel profile |
| `DUCKWORK_JAILBREAK_ROTATE_SESSION=once\|every\|0` | *(mode)* | rotation policy override |
| `DUCKWORK_JAILBREAK_DUMP=1\|0` | off | force or silence diagnostics |
| `DUCKWORK_JAILBREAK_DUAL=0` | on | single-section injection |
| `DUCKWORK_JAILBREAK_DISABLE=1` | off | kill switch: skip registration entirely |

## Diagnostic dumps

The middleware writes a diagnostic view of each request (per-session first request by default; every request with `DUCKWORK_JAILBREAK_DUMP=1`) to `~/.duckwork/plugins/duckwork-jailbreak-kernel/dumps/request_*.json`: full system messages + roles/lengths/200-char heads of other messages + model/provider/base_url. Use it to confirm the kernel sits at the tail of the system message and the route hits the expected model. Dumps are local-only and gitignored.

## Duckwork hard limits

- Plugin sections: ≤ 4000 chars each, ≤ 8000 chars total (the injector silently skips over-budget sections).
- Fixed position `after_memory` (after persona and memory); render order is section-id lexicographic → `core < reinforce`.
- Section ids: lowercase letters/digits/`.`/`_`/`-` only.
- Request-layer rebuild is not bound by the plugin-section budget (it runs in the middleware at request time).

## Offline self-test

```bash
cd ~/.duckwork/plugins/duckwork-jailbreak-kernel
python selftest.py          # ✅/❌ per-assertion (54 checks)
python selftest.py --json
```

## Localization

`/jailbreak` UI strings (command description and status report) follow the Duckwork
[`agent/i18n`](https://github.com/DuckMind/duckwork) standard: language resolves as `DUCKWORK_LANGUAGE` >
`display.language` in `config.yaml` > English. The plugin ships `locales/en.yaml`
(default) and `locales/zh.yaml`; any other language — and any missing key — falls
back to English, then to the bare key. Logs and the injected kernel itself stay
language-neutral by design.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — mechanism-level description of the three layers, session keys, and the failure model
- [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) — host requirements and the measured model-behavior matrix
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — version history
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) — lineage and licensing

## License

MIT — see [LICENSE](LICENSE). Port/adaptation of [dsh-infinite-gen-4](https://github.com/Minglink/dsh-infinite-gen-4) (MIT, Minglink) for the Duckwork Agent plugin platform.