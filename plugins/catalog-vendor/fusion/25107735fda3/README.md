# Fusion Router

A multi-model routing plugin for Duckwork Agent. It detects the model fleet your
agent harnesses actually have installed (Duckwork, Codex, Claude, Grok) and builds
a **Frontier → Middle Manager → Frontier** routing structure: a cheap capable
middle manager plans and delegates; frontier models implement; a frontier model
synthesizes and owns decisions. Models are pinned per roster with provenance
from actual execution records.

No hardcoded provider fleet. The router reads your own install.

## Install

```bash
duckwork plugins install fusion     # via the plugin catalog (once admitted)
duckwork plugins enable fusion
```

Or from a local checkout:

```bash
duckwork plugins install <path-to-this-repo>
duckwork plugins enable fusion
```

## Commands

Run `duckwork fusion --help` after enabling. Core surface:

```
duckwork fusion teams                 # Detected fleet per harness + rosters
duckwork fusion teams --harness codex # Restrict detection to one harness
duckwork fusion teams --show default  # Full roster JSON for one template
duckwork fusion validate <plan.json>  # Validate a plan packet (v3/v4)
duckwork fusion plan <raw>            # Extract + validate a packet from raw output
duckwork fusion run <plan.json>       # Execute through the middle-manager loop
duckwork fusion index                 # Sync/query the model index
duckwork fusion report                # Weekly feedback scorer report
duckwork fusion status                # Recent runs
```

## How detection works

`./roster.py` + `./harnesses.py` scan each harness's native config for what it
can actually call today:

- **Duckwork** — `config.yaml` `model:` blocks, default provider, fallback list
- **Codex** — `~/.codex/config.toml` (model, subagent model, model_providers)
- **Claude** — `~/.claude/settings.json` / `ANTHROPIC_API_KEY`
- **Grok / Grok Build / Grokbot** — `auth.json` `xai-oauth` / `XAI_API_KEY`

Each (provider, model) is tiered **frontier** / **cheap** by name heuristics
(`./classify.py`), then composed into rosters. Everything is overridable in
`DUCKWORK_HOME/fusion.yaml` (see `fusion.example.yaml`).

## Structure

The routing spine is the same in every roster:

```
T0  Frontier consult  — final synthesis / decisions (clean session)
T1  Middle Manager    — cheapest capable model runs the loop, delegates
T2  Frontier workers  — implement in continuous cached threads
```

See `./scripts/` for the packet validator, normalizer, executor and header
builder — all packaged with the plugin so it is self-contained.

## License

MIT. See `LICENSE`.
