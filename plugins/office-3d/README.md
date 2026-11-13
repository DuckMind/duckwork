# Office 3D for Duckwork

Bundled isometric office view, adopted from oslook's MIT Office 3D v1.4.4.
Upstream commit: `127c28accc950d1a10ff55ced992538eda656f16`.
See `UPSTREAM.json` for provenance, original file hashes and local adaptations;
`LICENSE` preserves the original MIT notice byte-for-byte.

The desktop half uses only `@duckwork/plugin-sdk`, React and the JSX runtime.
It contributes `/office-3d`, an Office navigation item, a status chip, palette
command, keybinding and profile-visibility settings. It does not require
Developer Mode. The bundled dashboard API is discovered through
`dashboard/manifest.json`; explicit plugin disables and existing consent gates
remain authoritative. The optional `office_status` agent tool retains the
standard `duckwork plugins enable office-3d` opt-in.

## Data and permissions

Reads gateway liveness, gateway status JSON, profile display-name metadata and
read-only SQLite aggregate session counts, input/output token totals, cost and
latest activity. Delegation routing extracts only profile labels and counts
inside SQLite: full task JSON never enters Python. No messages, prompts or
session titles are selected from SQLite. Missing/corrupt databases degrade to
zero. No credentials, telemetry, network requests or shell execution are added.
Desktop REST/RPC goes through Duckwork's existing scoped SDK. Clicking a profile
can open a new chat; the latest-session action asks the host for session metadata
and opens it through the host, never fetching messages itself.

## Verification

Run translated upstream tests with Duckwork's canonical test runner:

```
DUCKWORK_PYTHON="$PWD/.venv/bin/python" scripts/run_tests.sh plugins/office-3d/tests/test_*.py tests/plugins/test_office_3d_integration.py -q
node --experimental-vm-modules plugins/office-3d/tests/route-query.mjs
node --experimental-vm-modules plugins/office-3d/tests/profile-visibility.mjs
```

Canvas/browser regression builders are preserved under `tests/`; always pass
an isolated output directory and existing dependency directory. They use only
synthetic profile fixtures, not real user profiles. Windows liveness code is
retained; native Windows and packaged-app acceptance belong to release testing.
