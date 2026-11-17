<div align="center">

  <a href="https://github.com/DuckMind/duckwork">
    <img src="https://github.com/user-attachments/assets/ac2f5702-c842-4b2e-9340-737481fa0ece" width="96" height="96" alt="Fordex Duckwork mark" />
  </a>

  # Duckwork Jina

  **Hand Duckwork a link. Get back the page, not the markup.**

  Duckwork Jina plugs [Jina Reader](https://jina.ai/reader/) into the `web_extract` and `web_search` tools Duckwork already has.
  Pages come back as clean Markdown. Reading works without an account; search needs a free key.

  <sub>POWERED BY <a href="https://github.com/DuckMind/duckwork">DUCKWORK AGENT</a> &nbsp;·&nbsp; COMMUNITY PLUGIN &nbsp;·&nbsp; VERSION 0.1.0</sub>

  <br /><br />

  [What it does](#the-web-as-markdown) &nbsp;·&nbsp; [Install it](#make-it-yours) &nbsp;·&nbsp; [Where your data goes](#privacy-you-can-explain-in-one-breath)

</div>

![A marble hand pulls a web page out of a browser window as a scroll of Markdown](assets/catalog-banner.png)

## Powered by Duckwork

Duckwork Jina is a community-built web backend for [Duckwork Agent](https://github.com/DuckMind/duckwork). It adds no tools of its own. It registers a provider named `jina` through Duckwork's web provider API, so the agent keeps calling `web_extract` and `web_search` exactly as before, and Duckwork routes those calls to Jina when you choose it.

It works in the CLI, Duckwork Desktop, the messaging gateway, cron jobs and subagents: anywhere the web tools run.

## The web as Markdown

| | |
| --- | --- |
| **Read**<br />`web_extract` sends each URL to `r.jina.ai` and returns the page as Markdown, with title and final URL. No key needed. | **Search**<br />`web_search` queries `s.jina.ai` and returns titles, URLs and snippets. Needs `JINA_API_KEY`. |
| **Mix and match**<br />Use Jina only for reading and keep your current search backend, or use it for both. | **Fail per page**<br />One broken URL comes back with its own error. The rest of the batch still arrives. |

## Small decisions, already made

- Duckwork never switches you to Jina on its own. Without a key, Jina is used only when you name it in your config.
- Several URLs are read in parallel: 2 at a time without a key, 5 with one, to stay under Jina's rate limits.
- Only `http://` and `https://` links are sent. Anything else is refused before a request is made.
- Images are dropped from the Markdown, since the agent reads text.
- Search asks Jina for snippets only, not every result's full page, to save tokens. At most 20 results.
- Errors say what to do next: set a key, wait out a rate limit, or check Jina's status page.
- Each request times out after 60 seconds.

## Make it yours

### Install

```sh
duckwork plugins install Adolanium/duckwork-jina
```

The installer asks for `JINA_API_KEY`. Leave it empty if you only want reading.

Duckwork Jina needs Duckwork Agent 0.21.6 or later.

### Choose it

Pick **Jina Reader** in `duckwork tools`, or set the backends in `~/.duckwork/config.yaml`:

```yaml
web:
  extract_backend: jina   # web_extract through Jina Reader, key optional
  search_backend: jina    # web_search through Jina Search, key required
```

Set only `extract_backend` to keep your current search provider.

### Add a key

Get one at [jina.ai/api-dashboard](https://jina.ai/api-dashboard/). New keys come with free tokens. A key turns on search and raises the reading limit above the anonymous one, about 20 requests a minute.

Set it with `duckwork tools`, or as `JINA_API_KEY` in your Duckwork environment. The plugin reads it through Duckwork's secret scope, so each profile keeps its own key.

### Test

The tests use Duckwork's real plugin discovery with a mocked HTTP transport, so they make no network calls:

```sh
DUCKWORK_SOURCE=/path/to/duckwork-agent bash scripts/test.sh
```

Check the plugin the same way the catalog does:

```sh
duckwork plugins validate . --install-deps
```

CI runs both on every push, against Duckwork 0.21.6 and 0.22.2 on Python 3.11 and 3.13.

## Privacy you can explain in one breath

```text
Duckwork web_extract / web_search  →  r.jina.ai / s.jina.ai (Jina AI)  →  the page or the results
```

- **What leaves your machine.** The URLs the agent reads go to `r.jina.ai`, and its search queries go to `s.jina.ai`. Jina fetches and processes the pages on its own servers. See [Jina's privacy policy](https://jina.ai/legal/#privacy-policy).
- **Your key.** Sent to Jina as a bearer token when it is set. The plugin reads it only through Duckwork. It never stores, logs or writes it, and it is never echoed back in an error.
- **Nothing else.** No files read or written, no shell commands, no background processes, no telemetry.

## Compatibility

| Duckwork Agent | Python | Status |
| --- | --- | --- |
| 0.22.2 | 3.11, 3.13, 3.14 | Tested in CI and by hand |
| 0.21.6 (minimum) | 3.11, 3.13 | Tested in CI |

The plugin depends only on `httpx`, which Duckwork already ships.

## Limits

- Without a key, reading shares Jina's anonymous rate limit with everyone on your IP. Heavy use needs a key.
- Search always needs a key.
- Jina may serve a cached copy of a page. When it does, the result carries Jina's warning in its metadata.
- Pages behind a login, a paywall or a bot wall may come back empty or partial. Those come back as a per-page error, not a crash.
- Jina has no batch endpoint, so a long list of URLs is read a few at a time.

<br />

<div align="center">
  <strong>Duckwork Jina</strong><br />
  <sub>Any page, as text your agent can read.</sub>
</div>

<br />

## License

[MIT](LICENSE).

> **Community project**
>
> Duckwork Jina is an independent community plugin. It is not affiliated with, endorsed by, sponsored by, or officially associated with [Fordex](https://github.com/DuckMind/duckwork), the [Duckwork Agent project](https://github.com/DuckMind/duckwork), or [Jina AI](https://jina.ai). Duckwork, Duckwork Agent, Fordex, Jina and Jina Reader are names and marks belonging to their respective owners.
