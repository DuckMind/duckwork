# Contributing

Epistemic Harness is an AI-assisted contribution maintained by project
contributors. Code, tests, and documentation are not presented as authored by
any individual user. Keep public examples and fixtures generic: do not commit
private profiles, case logs, transcripts, credentials, machine-specific paths,
or evaluation artifacts.

## Development

The runtime dependency is Duckwork Agent's public plugin API. The plugin declares
no additional runtime Python dependencies in `plugin.yaml`. Test-only
requirements are `pytest` and `PyYAML` with bounded versions.

Run the standalone tests with the canonical Duckwork runner when a Duckwork
checkout is available:

```bash
DUCKWORK_PYTHON=/path/to/python \
  bash /path/to/duckwork-agent/scripts/run_tests.sh tests -j 2 --file-retries 0
```

For a quick local-only run with test dependencies installed:

```bash
python -m pytest tests -q
```

Validate the registration contract through Duckwork before publishing:

```bash
duckwork plugins validate /path/to/epistemic-harness
```

Run the native runtime smoke with an installed Duckwork CLI. These commands copy
the checkout into an isolated profile, enable it through the public CLI without
granting built-in tool overrides, and pass the exact `DUCKWORK_HOME` to the smoke
script:

```bash
(
  SMOKE_ROOT="$(mktemp -d)"
  export HOME="$SMOKE_ROOT"
  export DUCKWORK_HOME="$SMOKE_ROOT/.duckwork"
  mkdir -p "$DUCKWORK_HOME/plugins/epistemic-harness"
  cp -R . "$DUCKWORK_HOME/plugins/epistemic-harness/"
  duckwork plugins enable epistemic-harness --no-allow-tool-override
  python tests/runtime_smoke.py "$DUCKWORK_HOME"
)
```

Use a newly created `SMOKE_ROOT` for each run. Do not replace the final
argument with `$HOME`: `runtime_smoke.py` writes fixtures and verifies state
under the exact `DUCKWORK_HOME` it receives. The `duckwork` and `python` commands
must come from the same Duckwork installation.

Use temporary `HOME`/`DUCKWORK_HOME` directories for tests that exercise state.
Keep verification logs outside the publishable plugin tree. Do not install the
plugin into a live profile, modify Duckwork core, or publish from a development
checkout.
