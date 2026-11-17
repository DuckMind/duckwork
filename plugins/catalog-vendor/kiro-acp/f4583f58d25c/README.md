# duckwork-kiro-provider

Use the [Kiro CLI](https://kiro.dev/) (AWS's agentic coding CLI) as a model
provider inside [Duckwork Agent](https://github.com/DuckMind/duckwork) —
Kiro's agent runs as an ACP subprocess behind Duckwork' normal provider
interface, so `duckwork -m kiro-acp`, `/model`, profiles, and the gateway all
work like any other backend.

Shipped as a **standalone plugin repo** per the upstream vendor-integration
policy ([duckwork-agent#80362](https://github.com/DuckMind/duckwork)):
zero edits to duckwork-agent core; it rides the documented
`auth_type="external_process"` provider seam
([Model Provider Plugins → External-process (ACP) providers](https://duckwork-agent.fordex.com/docs/developer-guide/model-provider-plugin)).

## Prerequisites

- duckwork-agent installed and working (`duckwork doctor` clean)
- [Kiro CLI](https://kiro.dev/docs/cli/) installed and **logged in**
  (`kiro-cli` on PATH; login state in `~/.kiro`)

Verified against Kiro CLI 2.22.0 (`kiro-cli acp`, ACP protocol v1 over stdio).

## Install

**Via the plugin installer** (recommended):

```bash
duckwork plugins install tobenwarrior/duckwork-kiro-provider
```

**Or manual drop-in**:

```bash
git clone https://github.com/DuckMind/duckwork
mkdir -p "${DUCKWORK_HOME:-$HOME/.duckwork}/plugins/model-providers"
cp -r duckwork-kiro-provider "${DUCKWORK_HOME:-$HOME/.duckwork}/plugins/model-providers/kiro-acp"
```

Both paths register the `kiro-acp` provider for the next session.

## Use

```bash
duckwork -m kiro-acp "what can you do?"
```

Or pick **Kiro (AWS)** in `duckwork model` / `/model`. The provider name and
aliases are `kiro-acp`, `kiro`, `kiro-cli`.

Auth is handled by the `kiro-cli` subprocess itself (your existing `~/.kiro`
login) — no API keys to configure.

## Configuration (optional env overrides)

| Env var | Purpose | Default |
|---|---|---|
| `DUCKWORK_KIRO_ACP_COMMAND` | Path to a custom kiro binary | `kiro-cli` |
| `KIRO_CLI_PATH` | Older alias for the same | — |
| `DUCKWORK_KIRO_ACP_ARGS` | Extra argv (shlex-split), e.g. `"acp --agent builder --effort high"` | `acp` |

## How it works

`KiroACPProfile` is a `ProviderProfile` with `auth_type="external_process"`
that spawns `kiro-cli acp` and adapts it to Duckwork' OpenAI-style client
interface by extending the in-tree `copilot-acp` ACP shim (`agent.copilot_acp_client`)
— session lifecycle, streaming updates, permission handling, and the
file-safety bridge are inherited, so upstream fixes flow through. Model
listing is delegated to the subprocess; `model="kiro-acp"` means "use the
session default model".

## Development

```bash
# unit + discovery tests (need a duckwork-agent checkout; defaults to ~/.duckwork/duckwork-agent)
DUCKWORK_REPO=/path/to/duckwork-agent python -m pytest tests/ -q
```

Tests cover the profile contract (registration, env overrides, client
construction) and real discovery from an isolated `$DUCKWORK_HOME` — no live
Kiro calls.

## License

MIT
