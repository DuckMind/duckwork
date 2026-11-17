# duckwork-anysearch

[AnySearch](https://www.anysearch.com) web search and content extraction for
[Duckwork Agent](https://github.com/DuckMind/duckwork), plus two real-time
fallback chains that keep the web tools working when a primary backend fails.

| Provider | What it does | Select with |
|---|---|---|
| `anysearch` | AnySearch alone (REST `/v1/search` + `/v1/extract`) | `web.backend` or per-capability keys |
| `exa-anysearch` | Exa first → AnySearch on any Exa failure | `web.search_backend` |
| `firecrawl-anysearch` | Firecrawl first → AnySearch on any Firecrawl failure | `web.extract_backend` |

## Why the chains

Duckwork' built-in runtime rescue only rescues a failed call to its keyless
anonymous ring, which is heavily throttled. AnySearch's free tier is
**1,000 requests/day** (20 QPS with a key; anonymous access works without one),
which makes it a strong second backend:

- **Search**: Exa's free credits drain under burst use; the chain retries Exa on
  every call, so a reset quota is picked up automatically with no manual switch-back.
- **Extract**: in a batch replay of 20 URLs that had previously failed on
  Firecrawl, most failures were backend-level (unconfigured, 60s scrape
  timeouts) rather than hard pages, and AnySearch recovered 65% of them.
  Firecrawl stays first because it clears anti-bot walls AnySearch cannot
  (npmjs, WeChat, z-lib).

## Install

1. Clone into your Duckwork plugin directory:

   ```bash
   git clone https://github.com/<owner>/duckwork-anysearch "$DUCKWORK_HOME/plugins/anysearch"
   ```

2. Enable the plugin (Duckwork requires explicit opt-in for user plugins):

   ```bash
   duckwork plugins enable anysearch
   ```

3. Optional but recommended — add an AnySearch API key. A free key raises the
   quota to 1,000 requests/day; get one at
   <https://www.anysearch.com/console/api-keys>.

   ```env
   # $DUCKWORK_HOME/.env
   ANYSEARCH_API_KEY=as_sk_...
   ```

4. Point the web tools at the chains (or pick them via `duckwork tools`):

   ```yaml
   # $DUCKWORK_HOME/config.yaml
   web:
     search_backend: exa-anysearch
     extract_backend: firecrawl-anysearch
   ```

5. Fully restart Duckwork Desktop — plugins and config load at startup.

### Multiple profiles

Plugins are per-profile (`$DUCKWORK_HOME/plugins`), so naively this directory
would need a copy per profile and drift. Instead, make every other profile a
directory junction (Windows) or symlink (Unix) to the single checkout:

```bash
python scripts/link-to-profiles.py           # create/repair links
python scripts/link-to-profiles.py --verify  # check only
```

Duckwork' plugin scanner follows junctions/symlinks, so one checkout serves every
profile. Note that `plugins.enabled` and `.env` stay per-profile: a new profile
still needs `duckwork plugins enable anysearch` and its own `ANYSEARCH_API_KEY`.

## Notes from testing against the live API

- `/v1/search` returns both `snippet` and `content`, but `content` is an
  abstract. With `format: "markdown"` it becomes a structured digest (roughly
  2x the default length), never the full page — full text requires
  `/v1/extract`. This provider requests `format: "markdown"` and maps `content`
  to the result description.
- `POST /v1/extract` is the official REST endpoint and measured about 2x faster
  than the MCP `extract` tool (0.45s vs 0.91s for the same page). The MCP path
  is kept only as a fallback; its `result.content[].text` is a JSON *string*
  that needs a second parse.
- With an `Authorization` header present but the key invalid, the API returns
  401/403 — it does not silently fall back to anonymous.

## Tests

Run with the Duckwork venv Python:

```bash
<duckwork-agent>/venv/Scripts/python tests/test_provider.py    # providers + simulated failover
<duckwork-agent>/venv/Scripts/python tests/test_chains.py      # extract chain
<duckwork-agent>/venv/Scripts/python tests/test_e2e.py normal  # through tools.web_tools
<duckwork-agent>/venv/Scripts/python tests/test_e2e.py broken  # real failures → rescue
```

## License

MIT
