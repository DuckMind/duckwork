# ard-kit

An agent should hold a catalog, not the whole workshop. It looks up the one
tool a task needs instead of hauling every manual up front.

Turn what you already have into a discoverable catalog. Point it at a folder
of scripts or at a packaged repo and it writes a valid `ai-catalog.json`:
docstrings, argparse flags, `SKILL.md` frontmatter, `.mcp.json` servers and
declared console commands become
[Agentic Resource Discovery (ARD)](https://agenticresourcediscovery.org/)
entries. Nothing to annotate, no account to create, no dependencies to add.

Serving is included, but it is not the point: the same catalog goes out as a
static manifest at `/.well-known/ard.json`, a dynamic `POST /search`,
`GET /agents` and `POST /explore` facet aggregation, or over stdio as an MCP
front. `python3 selfcheck.py` asserts the pipeline end-to-end and is the
gate to run locally; `.gitlab-ci.yml` defines that plus the official
conformance CLI (`ards-project/ard-spec`) as CI jobs.

ARD is the discovery layer that sits in front of MCP (tools), Skills
(instructions), and A2A (agents). It answers one question: *"what capability
can help with this task?"* — invocation stays with the resource's own
mechanism.

## Publish what you already have

Three shapes, all zero-config:

```bash
# A folder of scripts: docstrings, argparse flags, SKILL.md, .mcp.json
ard-catalogize --dir scripts

# A packaged Python repo: console commands it already declares
cd my-project && ard-catalogize

# An npm package: the bin field it already declares
cd my-node-project && ard-catalogize
```

The first walks the directory — `*.py` and `*.sh` files (first docstring or
header comment as the description, argparse flags as the invoke schema),
`SKILL.md` agent skills, `.mcp.json` client configs. The second reads
`[project.scripts]` from the workspace manifest and catalogs the commands
your package already ships: `urn:air:<host>:cli:<command>`, arguments mined
from the module behind the entry point (flat and src layouts),
`distribution` and `version` from `[project]`. A packaged repo with no
`scripts/` directory is a normal case, not an error.

The third reads `bin` from `package.json` the way npm resolves it itself:
the string form is the package name without its scope (`@org/tool` installs
as `.bin/tool`, so it is cataloged as `urn:air:<host>:cli:tool`), and the
object form follows npm's `.bin/` resolution rather than the raw key: the
directory part of a key is dropped (`@org/tool` links as `tool`,
`deep/sub/dir` as `dir`), a later key wins a basename collision, and the
commands are cataloged sorted instead of in declaration order.
JavaScript has no argparse to mine, so `arguments`
stays empty — a declared command is cataloged, not validated, and a `bin`
path that does not exist yet is the publisher's problem rather than the
catalogizer's. A workspace shipping both manifests is read as Python:
`pyproject.toml` wins and `package.json` is not read.

All three shapes also read a `.mcp.json` at the workspace root, not only the
ones found under a scanned directory: a client config sits above `--dir
scripts` by definition, and without it the servers a workspace declares stay
invisible to the catalog an agent asks "which of these can do X". They become
`urn:air:<host>:mcp:<server>` — `command` + `args` shell-quoted into `invoke`
for a stdio server, the `url` for an http one — appended after the scanned
entries, so re-catalogizing an existing catalog stays a pure append. `env` is
never copied: that is where client configs keep their secrets. A `disabled:
true` server is still cataloged — under JIT mounting a switched-off server is
exactly what discovery should surface — and carries `metadata.disabled` so its
card does not read as callable right now; the flag is kept out of
`description`, which is search text. A workspace holding nothing but a root
client config catalogs on its own.

A manifest says a server exists and how to start it, never what it does, so a
card's description is generated — `MCP server <name> (stdio).` — and the card
is found by the server's name. To make it findable by capability, declare prose
in a sibling file: `.mcp.json` → `.mcp.ard.json`, keyed by the exact
`mcpServers` key, each value `{"description": ..., "tags": [...], "aliases":
[...]}`, every field optional and every value a plain string or list of
strings. Declared prose replaces the generated description and feeds tags,
aliases and representative queries; the name is always kept as an alias and
`mcp` as a tag. A wrongly-typed field is dropped, and a missing, unreadable,
misshapen or orphan-keyed sidecar costs one line on stderr and never the scan —
prose is optional, so it cannot be allowed to abort the thing carrying it. Write
it in a language the tokenizer reads (`[a-z0-9]+`).

What you do not do: write metadata files, decorate your code, register an
account, or install anything beyond the Python 3.10+ stdlib. If a tool is
already documented for humans, it is already documented for agents. The card
prose above is the one exception, and it exists because a client config is the
one source that documents nothing for humans: it holds a name and a command, so
there is no prose to lift and the alternative is a card nothing can find.

## Why this exists

The pieces started life as a private in-house integration — a catalogizer
over a large pile of local scripts and a registry serving them for
intent-based lookup. When the ARD specification was announced
(HF blog: [Agentic Resource Discovery: Let agents search](https://huggingface.co/blog/agentic-resource-discovery-launch)),
the salvageable pieces were pulled out, generalized, and aligned to the
spec. The original registry server code was lost in a workspace cleanup;
`registry.py` here is a faithful rebuild against the public shape.

## Pieces

| File | Role |
|------|------|
| `ard_kit/catalogize.py` | Scans directories for `.py`/`.sh` scripts (AST docstrings, argparse flags, shell header comments), `SKILL.md` agent skills (YAML frontmatter → `text/markdown; profile="urn:air:agent-skills"` entries) and `.mcp.json` MCP client configs (→ `application/mcp-server-card+json` per server; env values never cataloged; an optional `<manifest>.ard.json` sibling declares per-server card prose). Also reads the commands a package already declares straight from the workspace manifest, with no file scan at all — `[project.scripts]` in `pyproject.toml`, `bin` in `package.json` (string form unscoped, the way npm links it into `.bin/`; object form by the name npm links each key as, sorted) — cataloged as `cli` entries. A publisher-declared name — a `bin` key, an `mcpServers` key — is cataloged as the single segment it is, never as URN path structure. A manifest, client config or skill file it cannot read or parse is skipped with one line on stderr, never a traceback: one bad workspace never costs you the scripts already collected, and when two sources collide on one identifier the dropped one is named on stderr instead of vanishing. Emits ARD entries into `ai-catalog.json` plus an `ai-catalog.inspect.json` invoke-schema sidecar. Stdlib only. |
| `ard_kit/registry.py` | Minimal HTTP registry: serves the manifest and `POST /search` (token-overlap ranking, `pageToken` paging), `GET /agents` (deterministic listing), `POST /explore` (facet counts over the matched set), optional `--upstreams` federation fan-out — every peer row screened, a SUSPECT one dropped and named on stderr — `GET /inspect` over the sidecar, optional `--token` bearer auth. Stdlib only. |
| `ard_kit/mcp_server.py` | MCP stdio front over the same catalog: `ard_search` (ranked summaries), `ard_inspect` (invoke command + CLI arguments) and `ard_verify` (trust verdict) as MCP tools, so an editor mounts a command instead of being handed a URL. Stdlib only. |
| `ard_kit/trust.py` | The verdict engine and the `ard-verify` CLI: screens an entry for injection markers, invisible characters and padded fields, checks a `trustManifest.identity` against the domain its URN claims, verifies a detached Ed25519 JWS attestation against a JWKS, and reports VERIFIED / UNVERIFIED / SUSPECT / UNSUPPORTED. Stdlib only — JWS verification uses `cryptography` when it is importable and degrades to UNSUPPORTED when it is not. |
| `ard_kit/doctor.py` | The install preflight and the `ard-doctor` CLI: seven checks in chain order — interpreter, wrappers on PATH, one wrapper actually runnable, catalog readable, registry `/health`, an authenticated search probe using a term taken from the catalog itself, the harness — each failure with a `hint` and a pasteable `next` command. Warnings pass, failures exit 1. Stdlib only. |
| `selfcheck.py` | End-to-end pipeline check over a temp workspace: catalogize, ranking, schema conformance, the invoke sidecar, bearer auth, the MCP front, two-registry federation, trust verdicts and the federation screen, and declared entry points. New extraction contracts are pre-registered here as expected failures before the code that satisfies them exists. |
| `systemd/ard-registry.service` | Unit template for running the registry as a user service. |

No dependencies beyond Python 3.10+ stdlib.

## Install

```bash
pipx install agentic-ard-kit  # isolated venv, five commands on PATH
pipx install .         # same, from a checkout
```

This installs `ard-catalogize`, `ard-registry`, `ard-mcp`, `ard-verify` and
`ard-doctor` — the same entry points as `python3 -m ard_kit.catalogize`,
`python3 -m ard_kit.registry`, `python3 -m ard_kit.mcp_server`,
`python3 -m ard_kit.trust` and `python3 -m ard_kit.doctor`. Running straight
from a clone stays supported and needs no install at all.

Preflight the result rather than guessing at it: `ard-doctor` (from a clone,
`python3 -m ard_kit.doctor`) walks interpreter → wrappers → catalog →
registry `/health` → a live search probe → the harness, and every failure
prints the command that fixes it. The exit status is the verdict — 0 means
the install works, 1 means a row above says why. On Windows read
[Windows](#windows) first: the interpreter there is not called `python3`.

## Qoder plugin

ard-kit also ships as a self-contained [Qoder](https://qoder.com) plugin —
the same code plus an agent-facing wrapper:

| Component | What it gives the agent |
|-----------|-------------------------|
| `skills/ard-registry` | The discover → inspect → run → discard contract (env-driven endpoint: `ARD_REGISTRY_URL`, optional `ARD_REGISTRY_TOKEN`). |
| `/ard-catalogize` | Slash command: index a script directory into `ai-catalog.json` and re-verify live. |
| `/ard-serve` | Slash command: serve a catalog, confirm via `/health`. |
| `/ard-doctor` | Slash command: preflight the install, report the first failure with its fix. |
| `bin/ard-registry`, `bin/ard-catalogize`, `bin/ard-mcp`, `bin/ard-verify`, `bin/ard-doctor` | Entry points added to PATH (stdlib-only, no install step). Each has a `.cmd` twin of the same name, because Windows cannot exec a `#!/bin/sh` script. |

```bash
qoder plugins install ./ard-kit   # then /plugins reload
qoder plugins validate ./ard-kit  # manifest + component check
```

## Quickstart

```bash
# 1. Catalog your scripts and agent skills (default scan dir: ./scripts)
python3 -m ard_kit.catalogize --dir scripts --dir .agents/skills --host myhost.example.com

# 2. Serve it
python3 -m ard_kit.registry --catalog ai-catalog.json --port 8390

# 3. Search (the ARD registry API shape)
curl -s http://127.0.0.1:8390/search \
  -H 'Content-Type: application/json' \
  -d '{"query": {"text": "scan subdomains"}, "pageSize": 5}'

# 4. Explore what the catalog holds (facet counts, no ranking)
curl -s http://127.0.0.1:8390/explore \
  -H 'Content-Type: application/json' \
  -d '{"resultType": {"facets": [{"field": "type"}, {"field": "tags", "limit": 5}]}}'

# 5. Inspect before running (invoke command + CLI arguments)
curl -s 'http://127.0.0.1:8390/inspect?identifier=urn:air:myhost.example.com:script:scripts:scan_subdomains'

# 6. Static manifest (for crawlers / federation)
curl -s http://127.0.0.1:8390/.well-known/ard.json

# 7. Verdict its trust (exit 1 if anything came back SUSPECT or UNSUPPORTED)
python3 -m ard_kit.trust --catalog ai-catalog.json --quiet
```

The discover → inspect → run flow mirrors commercial directories like
monid.ai, minus the marketplace: `POST /search` finds the capability,
`GET /inspect?identifier=<urn>` returns its invoke command and parsed
argparse flags (404 for unknown identifiers, 501 when the sidecar is
absent), and the run itself stays with your shell.

`ai-catalog.json` is the `./`-relative default of both `--output` and
`--catalog`, not a protocol constant: a deployment names its catalog after
itself and hands every reader (`ard-registry`, `ard-verify`, the MCP front)
that same path. Keep the pair together — catalogize also writes
`<name>.inspect.json` beside it, and `/inspect` answers 501 without the
sidecar.

`POST /search` returns one page: the rows are under `results` and their count
under `totalResults` (not `entries` — that is the catalog file's key),
`pageSize` is 1–100 (default 10) and the
response carries a `pageToken` cursor while more local rows remain — pass it
back unchanged for the next page. Rows are ranked by `(score, identifier)`, so
a score tie cannot fall back to catalog order and move a page boundary the
next time the catalog is regenerated. The cursor names the last row of the
page it came from rather than a position in the result set: entries cataloged
or removed mid-walk shift nothing that was already handed out, and a row added
ahead of the cursor simply belongs to the next walk. The cursor also carries
the query it was minted for, so replaying it against a different
`text`/`filter` is refused with 400 instead of quietly paging a different
result set. Cursors are versioned; one minted by an older release is refused
the same way rather than reinterpreted. Paging is local: send
`"federation": "none"` alongside a `pageToken`, because merged peer ordering
is not stable between requests. A `pageSize` outside 1–100 and an unknown
`federation` mode are 400s as well, not silent clamps.

`GET /agents` is the deterministic half of the same catalog (spec 5.3.4):
no relevance, no federation, stable order, and a different envelope —
`items` + `total`, per the spec's `ListResponse`. Rows are ordered by the `orderBy`
field with `identifier` as the tiebreak: a `displayName` shared by several
scripts would otherwise fall back to catalog order and move a page boundary
the next time the catalog is regenerated. It takes `filter`, `orderBy`,
`pageSize` (1–100, default 20) and the same `pageToken` cursor, with the same
guarantee: every row present when the walk started is delivered exactly once,
whether or not the catalog is regenerated in between. `orderBy=... DESC` reads
the same order backwards, and a cursor minted by one direction or ordering is
refused by the other. The filter
grammar is the Appendix A subset this catalog can honour — `field=value`
clauses joined by `AND`, comma-separated values inside one field meaning
OR — over `displayName` (case-insensitive) and `type`. `publisherId`,
`createdAfter` and `updatedAfter` are in the spec, but a catalogized script
carries no publisher and no timestamps, so they are refused with 400
instead of matching everything:

```bash
curl -sG http://127.0.0.1:8390/agents \
  --data-urlencode 'filter=type=application/vnd.ard-kit.skill+json' \
  --data-urlencode 'orderBy=displayName DESC' \
  --data-urlencode 'pageSize=5'
```

`POST /explore` answers the other question — what the catalog *contains*.
It returns facet counts over the whole matched set instead of ranked
entries: ask for `resultType.facets` (per facet `limit` and `minCount`
optional, `otherCount` reports the tail beyond `limit`), and narrow with the
same `query.text`/`query.filter` search takes, or neither to aggregate the
whole registry. Explore is scoped to this registry — it never federates —
and a filter key the registry cannot honour returns 400 rather than being
silently ignored, because over-counted buckets look identical to correct
ones on the client side.

**For clients:** the registry is stateless and nothing attaches to your
session. `POST /search` returns ranked summaries only; pull a full invoke
schema via `/inspect` for the single entry you actually run. Discard both
afterwards — keep the URN if you might reuse the tool, not the payload.
Discovery costs a query, not a mounting: there is nothing to unload because
nothing was loaded.

Require a bearer token on every endpoint except `/health` when the registry
leaves loopback. For service deployments prefer the `ARD_REGISTRY_TOKEN`
environment variable over `--token` — the command line is world-readable:

```bash
python3 -m ard_kit.registry --catalog ai-catalog.json --port 8390 --token "$(openssl rand -hex 16)"
# or: ARD_REGISTRY_TOKEN=<token> python3 -m ard_kit.registry --catalog ai-catalog.json --port 8390
```

A token that is set but empty is rejected at startup (fail closed).

Federate with peer registries — with `"federation": "auto"` (default) queries
fan out to `--upstreams` and results merge (every result names its `source`
registry and carries a clamped score); `"federation": "referrals"` returns the peers in
a `referrals` array instead; `"federation": "none"` stays local. Under `auto`,
`totalResults` counts each peer's own total for the query rather than the rows
its page happened to return, and a peer still holding rows beyond that page
comes back as a `referrals` entry — a merged page has no cursor, so the
remainder gets an address instead of only a number:

```bash
python3 -m ard_kit.registry --catalog ai-catalog.json --port 8390 \
  --upstreams https://peer.example.com --public-url https://me.example.com
```

Self-check the whole pipeline:

```bash
python3 selfcheck.py
```

## Windows

The Python is stdlib-only and behaves identically; what differs is how it is
launched and how paths are read. Everything below is what the 2026-09-19
onboarding report reproduced on a clean Windows install.

- **The interpreter is `python` or `py`, never `python3`.** A `python.exe`
  that resolves but opens the Microsoft Store is a stub, not an interpreter:
  `python -c "import sys"` tells them apart. `python -m ard_kit.<module>` is
  the form that always works, with `PYTHONPATH` at the plugin or checkout
  root when the package is not installed.
- **Every `bin/ard-*` wrapper has a `.cmd` twin** of the same name. Git Bash
  runs the POSIX one (`bin/ard-registry`); cmd and PowerShell need
  `bin\ard-registry.cmd`. A pip/pipx install sidesteps both: it puts a real
  `ard-registry.exe` on PATH.
- **A POSIX path does not fail loudly.** `/home/me/catalog.json` handed to a
  Windows process resolves against the current drive
  (`C:\Program Files\Git\home\me\catalog.json`) and reads as "file not
  found", or — for a writer like `--output` — silently creates the tree.
  `catalogize` refuses a POSIX `--output` on Windows and says what to pass
  instead; readers cannot refuse, so pass a Windows path
  (`D:/work/catalog.json`) or, for a catalog that lives in WSL, a UNC path in
  slash notation (`//wsl.localhost/<distro>/home/...`; `wsl -l -q` lists
  distros). Every ard-kit error names the resolved path it actually looked at.
- **In Git Bash a backslash is an escape**, so invoke lines in a catalog are
  written with forward slashes; a `\\` there arrives at the shell as `\`.
- **PowerShell aliases `curl`** to `Invoke-WebRequest` and has no `${VAR:+…}`.
  `skills/ard-registry/SKILL.md` carries the `Invoke-RestMethod` form of every
  request; the bash snippets here do not paste as-is.
- **Persistent service:** `systemd/ard-registry.service` is Linux-only. The
  Windows equivalents — Task Scheduler XML, NSSM, and the plain foreground
  console — are in [`docs/windows-service.md`](docs/windows-service.md).

Then preflight it: `python -m ard_kit.doctor --catalog <windows-visible path>`.

## MCP front

The registry is HTTP, which means something has to hand the agent a URL
first. Editors that speak MCP mount a command instead, so the same catalog
is also served over stdio — no server to start, no port, no token:

```json
{
  "mcpServers": {
    "ard": {
      "command": "python3",
      "args": ["-m", "ard_kit.mcp_server",
               "--catalog", "/path/to/ai-catalog.json"],
      "cwd": "/path/to/ard-kit"
    }
  }
}
```

Installed through pipx, the same front is `"command": "ard-mcp"` with no
path to keep in sync.

Mounted as a plugin (Duckwork reads `mcp.json` from the plugin root), `command`
must be a bare executable or `./`-relative: `${PLUGIN_ROOT}` expands in
`args`/`cwd`/`env`, never in `command`. The form that resolves from the plugin
root is `./bin/ard-mcp`.

**Cross-platform.** The Python is stdlib-only and runs on Linux, macOS and
Windows unchanged — only the launch form is platform-flavoured. `python3` is
the interpreter name on Linux/macOS; on Windows it is `python` (or `py`), and
the `-m ard_kit.mcp_server` module form is identical. The `bin/ard-*` wrappers
are `#!/bin/sh` scripts, so Windows cannot exec them by those names: there
mount either the pipx console script (`"command": "ard-mcp"` — pip installs a
real `ard-mcp.exe`), the interpreter form (`"command": "python"`,
`"args": ["-m", "ard_kit.mcp_server", ...]`, `"cwd"` at the checkout), or the
`.cmd` twin (`"command": "./bin/ard-mcp.cmd"`). macOS is POSIX and needs none
of this; its one caveat is that a source ZIP (unlike `git clone`) drops the
executable bit, so `./bin/ard-mcp` may want a `chmod +x bin/*` first — or run
it as `sh bin/ard-mcp`.

Three tools, the same discover → inspect → run contract:

| Tool | Returns |
|------|---------|
| `ard_search` | Ranked summaries (`identifier`, `displayName`, `description`, `type`, `score`) for an intent, optionally filtered by media type. |
| `ard_inspect` | The invoke command and parsed CLI arguments for one `urn:air:` identifier. |
| `ard_verify` | The trust verdict and its findings for one identifier, over the same catalog. It takes no URL: the front never fetches on model-supplied input. |

Search deliberately returns summaries only: the invoke schema arrives once,
for the single entry the agent actually runs. The catalog is re-read per
call, so re-running `ard-catalogize` is picked up without a restart, and the
host owns the process lifetime — the server exits when stdin closes.

### Wiring agent harnesses

Two lanes; pick per harness, they serve the same catalog:

1. **MCP lane** — native tools, present in every session's tool list. Any
   MCP client runs the stdio front (`ard-mcp --catalog <absolute path to
   catalog.json>`); the JSON block above is the generic mount, and harnesses
   with a CLI write the same config for you (Duckwork: `duckwork mcp add <name>
   --command ard-mcp --args ...` — the args option must come last). The
   front reads the catalog file directly, so it works while the HTTP
   registry is down; refresh is just re-running `ard-catalogize`.
2. **Skill lane** — a `SKILL.md` documenting the HTTP registry
   (`/search`, `/inspect`, bearer token sourced out-of-band) loaded by the
   harness like any other skill. Zero prompt cost until triggered, and
   paging/filtering live server-side; the trade is that the agent must
   follow curl instructions instead of calling a tool.

Running one catalog over both lanes is normal: skills for the agents that
read docs, MCP for the agents that call tools.

## Entry shape

Each catalog entry carries the fields ARD consumers key on:

```json
{
  "@context": "https://agenticresourcediscovery.org/context/v1",
  "identifier": "urn:air:myhost.example.com:script:scripts:scan_subdomains",
  "displayName": "scan_subdomains",
  "description": "Enumerate subdomains via passive sources",
  "type": "application/vnd.ard-kit.script+json",
  "url": "file:///path/to/scripts/scan_subdomains.py",
  "tags": ["scan", "subdomains", "recon"],
  "aliases": ["scan_subdomains"],
  "representativeQueries": [
    "Enumerate subdomains via passive sources",
    "scan", "subdomains", "recon"
  ],
  "metadata": { "invoke": "python3 scripts/scan_subdomains.py", ... }
}
```

`representativeQueries` lead with the natural description phrase and pad
with keywords, so both sentence-style and token-style agent queries hit.
Every entry carries the field: when a resource offers no keywords, the file
or skill name is split to pad the list, which is always 2–5 phrases.
Entries keep exactly one of `url`/`data` (spec §3.4) and scalar-only
`metadata` values, and the manifest envelope carries only
`specVersion`/`host`/`entries` — the shape the official
`ai-catalog.schema.json` validates.

The `type` media type is free-form per the spec, but entries use a standard
name wherever one exists — `application/mcp-server-card+json` for MCP servers,
`text/markdown; profile="urn:air:agent-skills"` for agent skills — so any
conformant registry routes them without a local mapping. Plain local scripts
have no standard type yet and keep the vendor one.
Identifiers follow the spec's Appendix C form
(`urn:air:<publisher>:<namespace>:<name>`), and the served manifest prepends
a self-advert entry of type `application/ai-registry+json` so peers can
discover this registry's search base URL. Search results carry a `score` in
the spec's 0–100 relevance band (relevance only — ARD decouples trust into
the trust manifest, §5).

## Trust verdicts

A relevance score says nothing about whether an entry is telling the truth,
and a search row is echoed into an agent's context verbatim — `description`,
`displayName`, `url` and `metadata.invoke`, all of it. `ard_kit/trust.py`
answers the other question, per entry:

| Verdict | Meaning |
|---------|---------|
| `VERIFIED` | Evidence beyond the entry's own text: the manifest was fetched from the domain its URNs claim, and its `trustManifest.identity` binds to that same domain. |
| `UNSUPPORTED` | A check was asked for that this install cannot perform — an identity the spec allows but nothing here can resolve (`did:key`, SPIFFE, ANS), or a detached JWS with no `cryptography` importable. Not an accusation: SUSPECT is. |
| `UNVERIFIED` | Nothing wrong, nothing proven. The normal verdict for a local catalog, where the entry is the only witness to itself. |
| `SUSPECT` | A concrete reason not to believe it, and the findings name it: an injection marker, an invisible or control character, a field padded past its ceiling, shell chaining inside `metadata.invoke`, a URL scheme the catalog has no business carrying, or an identity that does not match the URN authority. |

The worst verdict wins per entry, so a correctly bound identity cannot
launder an injection marker. Every ceiling and marker list was calibrated
against the station's live catalog (~1700 entries, regenerated hourly)
before shipping: the one SUSPECT it turned up was a real defect — two raw
control bytes a script's docstring carried into the catalog — since fixed at
the source, so the catalog now comes back clean. Nothing verdicts
UNSUPPORTED, which is what makes a SUSPECT actionable instead of noise. Two
rules were loosened by that measurement —
`\bexec\b` fires on the ordinary `bash -lc 'exec $HOME/…/run.sh'` launcher
line, and a 200-char list cap fired on real `representativeQueries` — and
`selfcheck.py` pins both loosenings with an honest entry that must come back
clean.

```bash
# A catalog on disk: nothing is proven, but every defect is found.
ard-verify --catalog ai-catalog.json --quiet

# A live registry. Fetching the manifest from the claimed domain is itself
# the hosting evidence, so this is the only mode that can return VERIFIED
# (ora.ai: 5/5 VERIFIED, did:web:ora.ai over urn:air:ora.ai:...).
ard-verify --url https://ora.ai --quiet

# A detached Ed25519 JWS attestation, checked against the issuer's JWKS.
ard-verify --attestation attestation.json --jwks https://ora.ai/.well-known/jwks.json
```

`--catalog`, `--url` and `--attestation` are mutually exclusive and one is
required. `--max-age-days` (default 90) rejects a stale attestation, `--json`
emits `{source, hostedFrom, counts, verdicts}`, `--quiet` prints only the
flagged rows (SUSPECT and UNSUPPORTED). Exit is 0 when every row came back
VERIFIED or UNVERIFIED, 1 when anything did not, 2 when the source could not
be loaded — so it drops into a CI step or a pre-run gate unchanged.

Federation enforces the same verdicts without being asked: `--upstreams`
screens every peer row and **drops** the SUSPECT ones, naming each on stderr.
Dropped rather than annotated, because the `/search` body is
conformance-validated and has no room for a verdict field. A peer row is
never given `hosted_from`: an aggregator relaying third-party entries is
doing its job, and demanding hosting there would condemn every row it relays
and break federation. `ard_verify` over MCP is the same engine over the same
catalog file, for the agent that is about to run something — identifier only,
because a fetch driven by model input is an SSRF surface. The operator CLI
keeps `--url`.

## Prior art / positioning

- [HF Discover](https://github.com/huggingface/hf-discover) — reference
  implementation over the Hugging Face Hub; federated, semantic search.
- [ARD spec](https://github.com/ards-project/ard-spec) — the standard itself
  (Apache-2.0).
- [monid.ai](https://monid.ai/docs/guide/quickstart-skill) — commercial take
  on the same pattern: a CLI/Skill teaching an agent to `discover → inspect →
  run` endpoints by intent. The difference: monid is a paid marketplace of
  third-party data endpoints behind an API key; ard-kit is the self-hosted,
  no-network, no-account version for resources you already own.

Known limitation: search here is lexical token overlap, not semantic ranking.
That is deliberate — zero dependencies, and good enough for a few thousand
private entries. The upgrade path is embeddings behind the same endpoint.

## License

MIT.

## Acknowledgements

Developed and hardened in [Qoder](https://qoder.com) — from the ARD v0.91
conformance rebuild through the ultra-review cycle.
