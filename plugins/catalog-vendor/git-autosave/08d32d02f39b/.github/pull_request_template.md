<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
## Change

Describe the behavior change and any disclosure or compatibility impact.

## Verification

- [ ] `python -m ruff check .`
- [ ] `python -m pytest -q` (temporary repositories/DUCKWORK_HOME; no network)
- [ ] `duckwork plugins validate .` with a throwaway DUCKWORK_HOME
- [ ] Real index, HEAD, branches and working tree remain untouched
- [ ] English and translated documentation updated together
- [ ] No private Duckwork imports, runtime overrides, pushes or background processes
