# Node budgets

Leave `max_turns`/`timeout` unset and name a `shape`; the runner fills them from the
measured p95 presets in `wfcommon.SHAPE_PRESETS` (the single source; measured 2026-09-25):

| shape | max_turns | timeout |
|---|---|---|
| recon | 100 | 2400 |
| build | 65 | 1500 |
| review | 65 | 2400 |
| publish | 75 | 1500 |

Set `max_turns`/`timeout` explicitly only with a measured reason.
