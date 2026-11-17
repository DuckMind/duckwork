# Duckwork Plugin Generator 🔌

**Scaffold, extend, and bundle Duckwork Agent plugins from natural language descriptions.**  
Describe what you want — it generates the full plugin structure with `plugin.yaml`, `__init__.py`, `schemas.py`, `tools.py`, and optional bundled skill.

## Features

- **`plugin_scaffold`** — Create a complete plugin from a description. Generates production-quality code with proper `check_fn`, `emoji`, `kind: standalone`, and PEP-8-compliant Python.
- **`plugin_add_tool`** — Add a new tool to an existing plugin. Updates schemas, handlers, registration, and YAML manifest.
- **`plugin_add_skill`** — Bundle a skill with an existing plugin. Creates skill directory, registers it in `__init__.py`, and updates `plugin.yaml`.
- **Plays well with Duckwork** — Generated code matches the [official Duckwork plugin conventions](https://duckwork-agent.fordex.com/docs/guides/build-a-duckwork-plugin).
- **Zero dependencies** — pure Python 3.11+ stdlib. Works on Windows, Linux, macOS.

## Quick Start

```bash
# Clone and install
git clone https://github.com/DuckMind/duckwork
cp -r duckwork-plugin-gen ~/.duckwork/plugins/duckwork-plugin-gen

# Enable
duckwork plugins enable duckwork-plugin-gen

# Restart Duckwork / start new session
```

Then ask the agent:

> *"Create a plugin called 'joke-teller' with a 'tell_joke' tool"*

Or use it directly:

```python
from duckwork_tools import plugin_scaffold

result = plugin_scaffold({
    "name": "weather-alert",
    "description": "Weather alert plugin with SMS notifications",
    "tools": [
        {"name": "check_weather", "description": "Check current conditions", ...},
        {"name": "send_alert", "description": "Send weather alert via SMS", ...}
    ],
    "requires_env": [{"name": "WEATHER_API_KEY", "description": "Weather API key"}],
    "with_skill": True
})
```

## Generated Structure

```
~/.duckwork/plugins/your-plugin/
├── plugin.yaml         # Manifest with kind, requires_env, provides_tools
├── __init__.py          # register(ctx) with check_fn, emoji, description
├── schemas.py           # LLM tool schemas
├── tools.py             # handlers + check_requirements()
└── skills/your-plugin/
    └── SKILL.md         # Bundled skill (optional)
```

## Installation

**As a plugin** (recommended for agents):
```bash
cp -r duckwork-plugin-gen ~/.duckwork/plugins/duckwork-plugin-gen
duckwork plugins enable duckwork-plugin-gen
```

**As standalone scripts** (for CLI use):
```bash
# The tools.py can be imported directly in scripts
python -c "from duckwork_plugin_gen.tools import plugin_scaffold; ..."
```

## Requirements

- Duckwork Agent (any profile)
- Python 3.11+

## Documentation

Bundled skill at `skills/duckwork-plugin-gen/SKILL.md` — load it in-session with `load skill duckwork-plugin-gen`.

## Contributing

PRs welcome! The generated code must always pass PIP 8, include proper error handling, and match official Duckwork conventions.

## License

MIT
