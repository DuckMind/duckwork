<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Little Canary for Duckwork Agent

Little Canary screens Duckwork Agent user turns with structural checks and a local
powerless canary model. A BLOCK verdict withdraws downstream tool access for
that turn. The original prompt still reaches Duckwork's model.

With Duckwork Agent 0.21.3 or later, local Ollama, and `qwen2.5:1.5b`:

```bash
ollama pull qwen2.5:1.5b
duckwork plugins install little-canary
duckwork plugins enable little-canary
duckwork plugins list
```

The catalog entry installs this directory at a reviewed commit. The directory
bundles Little Canary's runtime and compatible `requests` dependency. It runs
inside Duckwork; it does not require the separate `little-canary serve` adapter.

For a direct install before the catalog entry reaches your client:

```bash
duckwork plugins install duckwork-labs-ai/little-canary/integrations/duckwork-agent --no-enable
duckwork plugins enable little-canary
```

Set `LITTLE_CANARY_MODEL` in the Duckwork Agent process environment to an installed Ollama tag to select the sacrificial model, for example `LITTLE_CANARY_MODEL=gemma3:1b`. The default remains `qwen2.5:1.5b`. The model receives no tools; selecting a model does not grant it any host authority.

The `pre_llm_call` hook screens the current user message once and can add a
bounded warning. It cannot prevent the prompt from reaching the model. On a
genuine BLOCK, `pre_tool_call` refuses downstream tools for that turn. If
screening is unavailable, the plugin leaves tools available and reports
degraded coverage. `on_session_end` clears the session's stored decisions.

For setup, verification and behavior, read the
[Little Canary Duckwork Agent guide](https://github.com/DuckMind/duckwork).
