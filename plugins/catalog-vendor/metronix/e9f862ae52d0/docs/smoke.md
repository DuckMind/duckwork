<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Duckwork Smoke

## Quick setup

```bash
python3 -m pip install --upgrade "duckwork-memory-metronix>=2026.34.1"
duckwork-metronix-setup
```

The setup command stores a REST JWT or `mtk_…` personal key securely.
`mtk_…` keys require Metronix core's shared REST authentication resolver. Do
not use `METRONIX_MCP_API_KEY` for the provider.

## Verify plugin

```bash
uv run --extra dev pytest tests/unit -v
RUN_INTEGRATION_TESTS=1 uv run --extra dev pytest tests/integration/test_live_metronix.py -v
```

## Verify Duckwork

1. Verify the real Duckwork API before installation:

   ```bash
   DUCKWORK_AGENT_SRC=/absolute/path/to/duckwork-agent \
     uv run --extra dev pytest \
     tests/unit/test_real_abc_contract.py tests/unit/test_duckwork_plugin.py -v
   ```

2. Run `duckwork memory status` and confirm it shows `Provider: metronix`.
3. Run `duckwork chat`, store a unique fact, then start a fresh chat session.
4. Ask for that fact and verify it is retrieved.
