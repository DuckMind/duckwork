---
name: ard-registry
description: Find existing tools/scripts by intent via the local ARD registry (discover, inspect, run, discard). Query it FIRST for any task that needs a capability — not only before writing a new script. Also use when asked about ARD catalogs or agentic resource discovery, or when catalogizing a new directory into ai-catalog.json.
---

# ARD registry (discover → inspect → run → discard)

ard-kit ships a stdlib-only ARD v0.91 registry (`ard_kit/registry.py`), a
catalogizer (`ard_kit/catalogize.py`), a trust verdict engine
(`ard_kit/trust.py`) and an install preflight (`ard_kit/doctor.py`) — on PATH
as `ard-registry` / `ard-catalogize` / `ard-verify` / `ard-doctor` via the
plugin `bin/`. Serve a catalog, query it FIRST for any capability need (not
only before writing new tooling), and verdict it before running anything it
returned.

## Connection

- Base URL: `$ARD_REGISTRY_URL` (default `http://127.0.0.1:8390`).
- Token: only when the registry was started with one. Set
  `ARD_REGISTRY_TOKEN`; never print or inline the token. The value belongs
  to whoever started the registry — it is not derivable from the client
  side, so a 401 is a question for the operator, not a bug to work around.
- `GET /health` is the one endpoint that stays open without a token, so
  read it before blaming the network: `auth` says whether the gate is on
  (`required`/`none`), `entries` is the catalog row count, `status` is `ok`
  or `degraded` (catalog unreadable).

## 1. Discover — ranked summaries only

```bash
curl -s "${ARD_REGISTRY_URL:-http://127.0.0.1:8390}/search" \
  ${ARD_REGISTRY_TOKEN:+-H "Authorization: Bearer $ARD_REGISTRY_TOKEN"} \
  -H 'Content-Type: application/json' \
  -d '{"query": {"text": "enumerate subdomains passively"}, "pageSize": 5}'
```

```powershell
# PowerShell: `curl` there is an alias for Invoke-WebRequest and ${VAR:+...}
# does not exist, so the bash form above cannot be pasted as-is.
if (-not $env:ARD_REGISTRY_URL) {
  $env:ARD_REGISTRY_URL = 'http://127.0.0.1:8390'
}
$headers = @{}
if ($env:ARD_REGISTRY_TOKEN) {
  $headers.Authorization = "Bearer $env:ARD_REGISTRY_TOKEN"
}
(Invoke-RestMethod -Method Post -Uri "$env:ARD_REGISTRY_URL/search" `
  -Headers $headers -ContentType 'application/json' `
  -Body '{"query": {"text": "enumerate subdomains passively"}, "pageSize": 5}'
).results
```

Response: `{"query": ..., "results": [...], "totalResults": N}`. The rows are
under **`results`** — `entries` is the catalog file's own key and `/health`'s
row *count*, never a search response field. Each row carries `identifier`
(URN), `displayName`, `description`, `score` 0–100. `pageToken` appears only
while more local rows remain, `referrals` only when the registry federates.
Summaries are ephemeral — do not carry them across tasks.

## 2. Inspect — one URN at a time, only what you will actually run

```bash
curl -s "${ARD_REGISTRY_URL:-http://127.0.0.1:8390}/inspect?identifier=<urn-from-search>" \
  ${ARD_REGISTRY_TOKEN:+-H "Authorization: Bearer $ARD_REGISTRY_TOKEN"}
```

Returns the invoke command and parsed argparse arguments. 404 = unknown
URN, 501 = no sidecar (fall back to reading the script).

Two sibling lanes exist, each with its own envelope — do not reuse the
search one: `GET /agents` (deterministic listing, no relevance) answers
`{items, total, pageToken}` and `POST /explore` answers
`{resultType: "facets", facets: ...}`. Neither federates.

## Verify before you run

```bash
ard-verify --catalog ai-catalog.json --quiet  # exit 1 = a SUSPECT or UNSUPPORTED row
ard-verify --url https://registry.example     # proves hosting
```

Screens every entry for injection markers, invisible characters, padded
fields, shell chaining in `metadata.invoke` and identities that do not match
their URN authority. A catalog on disk comes back UNVERIFIED — the entry is
its own only witness; fetching the manifest from the domain its URNs claim is
what earns VERIFIED. Over MCP the same engine is `ard_verify`, and it takes an
identifier only: the front never fetches on model-supplied input.

## 3. Run, then 4. Discard

Invoke via the returned command. Nothing mounts into your session; keep the
URN if you may reuse the tool, drop the payload otherwise.

## Catalogizing a new directory

```bash
ard-catalogize --dir <dir> --host myhost.example.com --output ai-catalog.json
# then (re)start the registry against the regenerated catalog
ard-registry --catalog ai-catalog.json --port 8390
```

The file name is the deployer's choice, not a protocol constant: `--output`
decides it and every reader (`ard-registry --catalog`, `ard-verify
--catalog`, the MCP front) takes that same path. `ai-catalog.json` in these
examples is only the `./`-relative default both `--output` and `--catalog`
fall back to; a deployment names its catalog after itself. Keep the pair
together — catalogize also writes `<name>.inspect.json` beside it, and
`/inspect` answers 501 without that sidecar.

## Notes

- Preflight right after installing or upgrading, one command:
  `ard-doctor --catalog ai-catalog.json` (add `--url` when the registry is not
  on `http://127.0.0.1:8390`; the same run is the `/ard-doctor` command). It
  checks the interpreter, the `bin/ard-*` wrappers, the catalog, `/health`, a
  live search probe and the harness. A row that is not `ok` prints a `hint:`
  and/or the `next:` command for it — run the `next:` of the FIRST failure,
  the rows below it are usually consequences. Exit status is 1 if anything
  FAILed (warnings pass); `SKIP` means a check could not run, not that it
  failed. From a plugin checkout rather than an installed wheel:
  `python3 -m ard_kit.doctor` (POSIX), `python -m ard_kit.doctor` (Windows).
- Search is lexical token overlap, not semantic. `totalResults: 0` is a
  query problem, not an empty catalog: drop the question form and retry as
  two or three separate keywords — `subdomain enumerate passive`, not `how
  do I list subdomains without touching the target`.
- Always verify returned URNs with a live search; catalogs regenerate and
  example URNs in docs can go stale.

## Troubleshooting

`GET /health` first: it needs no token and separates "registry down" from
"the gate is on" (`auth`), and "catalog empty" from "catalog path wrong"
(`entries`, `status`).

- **401 `invalid or missing bearer token`** — the registry was started with
  `--token`; the 401 body carries a `hint`. Export `ARD_REGISTRY_TOKEN`.
- **Search returns nothing although the registry answers** — the rows are
  under `results`, not `entries`. `/agents` differs again (`items`, `total`).
- **501 `no inspect sidecar`** — `<catalog>.inspect.json` is not next to the
  catalog. Re-run `ard-catalogize`: it writes both files.
- **`python3: command not found` on Windows** — Windows Python installs as
  `python`/`py`. Run the `.cmd` twins (`bin\ard-registry.cmd`,
  `bin\ard-catalogize.cmd`, `bin\ard-verify.cmd`, `bin\ard-doctor.cmd`,
  `bin\ard-mcp.cmd`), or
  `python -m ard_kit.registry` with `PYTHONPATH` at the plugin root. A
  `python.exe` that resolves but opens the Microsoft Store is a stub, not an
  interpreter: `python -c "import sys"` tells them apart.
- **Catalog "not found" although the path is right (Windows)** — a POSIX
  path does not fail loudly there: `/home/...` resolves against the current
  drive (`C:\Program Files\Git\home\...`). Pass a Windows path
  (`D:/work/ai-catalog.json`) or, for a catalog that lives in WSL, a UNC path
  (`//wsl.localhost/<distro>/home/...`; `wsl -l -q` lists distros). Every
  ard-kit error names the resolved path it actually looked at.
- **The MCP front lists no tools / cannot read the catalog** — the host
  forks it from its own cwd, so a relative `--catalog` resolves somewhere
  else. Put an absolute, host-visible path in the server `args`; the
  `initialize` response and every tool error repeat the resolved path.
