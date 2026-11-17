# Installation

Duckwork SEO is a local Duckwork plugin. This fork does not publish a catalog or release; install from a reviewed checkout.

## Requirements

- Duckwork with plugin support
- Python 3.10+ and `venv` support (the managed runtime installs pinned dependencies)
- Git to obtain or update the checkout

Playwright/Chromium is optional and is provisioned by setup for workflows that need browser rendering. Setup downloads packages and a browser and can use substantial disk space.

## Install from a checkout

```bash
mkdir -p "${DUCKWORK_HOME:-$HOME/.duckwork}/plugins"
cp -a /path/to/duckwork-seo "${DUCKWORK_HOME:-$HOME/.duckwork}/plugins/duckwork-seo"
duckwork plugins enable duckwork-seo
duckwork plugins doctor duckwork-seo --ci
```

Initialize the isolated runtime only when needed:

```bash
duckwork seo setup
duckwork seo doctor --json
```

`duckwork seo setup` installs pinned Python dependencies and optional Chromium into Duckwork plugin data storage. `duckwork seo doctor --json` checks readiness without changing the system. Use `duckwork seo run <script.py> [args...]` for offline utilities. Credentialed utilities must use the native `duckwork_seo_run` tool so the selected profile-vault values are scoped to one child process.

## Docker sandbox

Keep the reviewed bundle immutable and give its runtime a separate persistent data directory. Configure the container with these mounts (replace the host source path with the reviewed checkout):

```yaml
volumes:
  - /host/reviewed/duckwork-seo:/opt/duckwork-seo:ro
  - /host/reviewed/duckwork-seo/scripts/duckwork:/usr/local/bin/duckwork:ro
  - duckwork-seo-data:/var/lib/duckwork-seo:rw
environment:
  DUCKWORK_SEO_ROOT: /opt/duckwork-seo
  DUCKWORK_SEO_DATA_DIR: /var/lib/duckwork-seo
```

Do not mount host credentials, the host Duckwork profile, SSH configuration, or cloud-provider configuration into this container. The data volume is the only location Duckwork SEO needs to write. Runtime setup requires outbound access to the configured Python package source and, unless `--skip-browser` is used, the Chromium download source.

In the container terminal, bind the runtime to those paths before setup, diagnosis, or execution:

```bash
export DUCKWORK_SEO_ROOT=/opt/duckwork-seo
export DUCKWORK_SEO_DATA_DIR=/var/lib/duckwork-seo
cd "$DUCKWORK_SEO_ROOT"
```

The mounted `scripts/duckwork` compatibility command accepts only `duckwork seo` and forwards it to the bundle launcher. It does not expose the host Duckwork CLI. Use it for setup, diagnosis, and offline utilities:

```bash
duckwork seo setup
duckwork seo doctor --json
duckwork seo run portability_check.py --json
```

The bundled launcher remains available directly if the compatibility command is not mounted:

```bash
./scripts/duckwork-seo setup
./scripts/duckwork-seo doctor --json
./scripts/duckwork-seo run portability_check.py --json
```

The launcher selects an available Python 3.10+ interpreter and then dispatches through the managed environment under `/var/lib/duckwork-seo`. `scripts/duckwork-seo` is a shell launcher, so do not pass it to `python3`; `python3 scripts/runtime.py ...` is the lower-level equivalent when a shell cannot execute the launcher.

Credentialed calls are different: `duckwork_seo_run` executes from the Duckwork
host plugin process and does not inherit the Docker terminal's filesystem or
network isolation. Script arguments can reference paths visible to that host
process. Review file arguments and ask for approval before paid, external, or
mutating operations; the tool itself does not enforce that approval policy.

## Use the skills

Discover skills with Duckwork `skills_list` and load them with `skill_view`. Ask Duckwork to perform an audit or analysis, or load `duckwork-seo:seo` as the router. Skills are prompt workflows; they are not shell commands. Provider-backed workflows require a separately configured compatible Duckwork MCP server and account.

Google Search Console, GA4, Google Ads, and Indexing API OAuth flows stay disabled until Duckwork provides a profile-scoped Google authorization route. The native tool supports these active-profile vault names: `GOOGLE_API_KEY`, `MOZ_API_KEY`, `BING_WEBMASTER_API_KEY`, `KEYWORDSEVERYWHERE_API_KEY`, `MATOMO_API_TOKEN` or `MATOMO_TOKEN`, `MATOMO_URL`, `MATOMO_SITE_ID` or `MATOMO_IDSITE`, `DUCKWORK_SEO_LOCAL_TARGETS`, `DATAFORSEO_USERNAME`, `DATAFORSEO_PASSWORD`, `INDEXNOW_KEY`, and Banana's `GOOGLE_AI_API_KEY`. IndexNow's key-location URL is nonsecret and remains a normal argument. Do not put secret values in the checkout, catalog entry, or tool arguments.

## Update

Review the new checkout, replace the local plugin copy, then run:

```bash
duckwork plugins doctor duckwork-seo --ci
```

## Remove

Disable the plugin with `duckwork plugins disable duckwork-seo`, then remove its directory under `${DUCKWORK_HOME:-$HOME/.duckwork}/plugins/duckwork-seo` if desired. Runtime data is held in Duckwork plugin data storage; inspect Duckwork' configured data location before removing it.
