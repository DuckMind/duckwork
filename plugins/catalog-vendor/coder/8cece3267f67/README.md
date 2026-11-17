# duckwork-plugin-coder

Third-party [Coder](https://coder.com/) terminal environment provider for Duckwork Agent.

## Requirements

- A Coder deployment reachable over HTTPS and an existing workspace.
- Duckwork Agent with the terminal-backend plugin contract.
- Python dependencies declared in `pyproject.toml`.

## Configuration

Upstream Duckwork currently passes only the standard provider factory arguments to terminal plugins, so this compatibility branch reads Coder settings from the active profile environment:

```dotenv
CODER_URL=https://coder.example.com
CODER_API_KEY=...
CODER_WORKSPACE=my-workspace
TERMINAL_CODER_FORWARD_ENV=["GITHUB_TOKEN"]
TERMINAL_CODER_WORKSPACE_STARTUP_TIMEOUT=180
```

The first three variables are required. `TERMINAL_CODER_FORWARD_ENV` defaults to `[]`, and `TERMINAL_CODER_WORKSPACE_STARTUP_TIMEOUT` defaults to `180`. Invalid or explicitly empty values fail closed.

Profile YAML under `terminal.backends.coder`, Dashboard/Desktop configuration fields, and config-aware probing are temporarily unavailable until upstream Duckwork gains the provider-owned configuration contract. The API key remains stripped from model-authored subprocesses and is never included in probe details.

## Development installation

Duckwork source plugins are directories under `$DUCKWORK_HOME/plugins` containing `plugin.yaml` and a root `__init__.py`. A symlink is sufficient:

```bash
ln -s /path/to/duckwork-plugin-coder "${DUCKWORK_HOME:-$HOME/.duckwork}/plugins/coder-dev"
duckwork plugins enable coder
```

The symlink makes the source plugin discoverable; `plugins enable` opts it into the active profile. Select it with `duckwork config set terminal.backend coder`. The plugin registers a `TerminalEnvironmentProvider`; upstream Duckwork owns environment creation and task lifecycle, while this compatibility branch resolves Coder settings from the active profile environment.

Coder workspaces are durable user infrastructure, so the provider keeps dangerous-command guards enabled even though it uses isolated remote filesystem semantics. Only names explicitly listed in `forward_env` are copied into the remote session snapshot. Their values are delivered after the authenticated PTY WebSocket opens and are never placed in its request URL.

## Tests

From a Duckwork Agent checkout with its virtual environment available:

```bash
PYTHONPATH=/path/to/duckwork-plugin-coder:/path/to/duckwork-agent \
  /path/to/duckwork-agent/.venv/bin/python -m pytest tests -q
```
