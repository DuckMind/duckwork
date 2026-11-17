# Markdown.new for Duckwork

**Search the web. Read the useful parts. Bring back Markdown.**

Give Duckwork access to [Markdown.new](https://markdown.new) for public web research: search results with source links, readable page content, site crawls, and document conversion. No API key is required.

It works through Duckwork's existing `web_search` and `web_extract` tools, so ordinary research stays familiar. A separate `markdown_new` tool gives you more control when you need it.

## What you can do

- **Search and follow the sources.** Get search results with usable links, or request extracted content alongside results. Choose a country and language for locale-specific searches.
- **Read pages as Markdown.** Convert a public URL with `auto`, `ai`, or `browser` mode, with an option to retain images.
- **Crawl a public site.** Start a bounded crawl, check progress, retrieve its Markdown, or reconnect using its job ID. Cancelling a job requires approval.
- **Convert documents.** Convert a public file URL, including PDFs, or explicitly approve an upload of a non-sensitive local file. Format support depends on Markdown.new.
- **Keep your existing setup.** Select Markdown.new as your web provider without removing other providers. Duckwork still owns fallback behavior.

## Try asking Duckwork

> Find recent articles about Cloudflare Markdown for Agents and include the source links.

> Read this public documentation page and summarize the installation steps.

> Use markdown_new to crawl this public documentation site, with a maximum of 20 pages, then download the Markdown.

> Convert this public PDF URL to Markdown.

These are example prompts, not demonstrations of a completed crawl or conversion.

## Install

Requires a Duckwork version with `register_web_search_provider`, Python 3.10+ for the native plugin, and the companion `markdown-new` CLI on your `PATH`. The CLI is included in this repository and has no runtime Python dependencies.

### 1. Install the companion CLI

With [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/nosliwhtes/hermes-markdown-new@v1.0.0
markdown-new --version
```

The plugin release is **1.0.0**; its companion CLI reports **0.2.0**. These are separate components with separate version numbers.

### 2. Install and enable the plugin

```bash
duckwork plugins install "nosliwhtes/duckwork-markdown-new#plugin/markdown-new" --no-enable
duckwork plugins enable markdown-new
duckwork plugins doctor --ci markdown-new
```

This is a direct repository install, not a claim of approval by the Duckwork catalog. Review the installer's source and capability disclosures. For an immutable install, add `--ref` with the full 40-character commit SHA shown on the GitHub release.

The Duckwork catalog submission is pending maintainer review. If it is admitted, `duckwork plugins install markdown-new` will install the catalog's reviewed, SHA-pinned version.

### 3. Choose it for public web tasks

To use it for ordinary search and extraction, set these existing keys in your active Duckwork `config.yaml`:

```yaml
web:
  search_backend: markdown-new
  extract_backend: markdown-new
```

For the advanced tool, add `markdown_new` to your existing `toolsets` list. Keep your other toolsets. For example, if you currently use `duckwork-cli`:

```yaml
toolsets:
  - duckwork-cli
  - markdown_new
```

Start a new Duckwork session after changing the provider or toolsets. Installing the plugin does not change these settings for you.

## The advanced tool

`markdown_new` supports eight operations:

| Operation | Purpose |
|---|---|
| `url_convert` | Convert a public web page, with method and image options |
| `search_extract` | Search with optional country, language, and extracted page content |
| `crawl_run` | Start a bounded crawl and poll it in one call |
| `crawl_start` | Start a bounded public-site crawl |
| `crawl_status` | Check a job's progress and page outcomes |
| `crawl_download` | Retrieve a job's available Markdown |
| `crawl_cancel` | Cancel a job after native approval |
| `file_convert` | Convert a public file URL or an approved local upload |

You can also edit Markdown in [Markdown.new's web editor](https://markdown.new/markdown-editor). It remains a website, not a tool operation or an embedded Duckwork editor.

## Privacy and limits

**This is a public web service, not a local-only converter.** Search queries, submitted URLs, and approved file uploads go to Markdown.new. Crawls and file conversion may involve its upstream processing services. Read its [privacy policy](https://markdown.new/privacy) and [terms](https://markdown.new/terms).

Local uploads and crawl cancellation require approval for each invocation. The plugin blocks private-network URLs, sensitive-looking local paths, and file-substitution attempts. These checks are safeguards, not a content classifier: they cannot prove that a file is safe to upload. Do not submit credentials, confidential documents, authenticated pages, or internal URLs.

No API key is required, but service limits, availability, conversion quality, and supported formats are controlled by Markdown.new. A crawl may return a cached job; that does not establish that every page was fetched again. Existing Duckwork providers remain available, but fallback depends on your host configuration.

## Verification and development

The release uses the previously reviewed client and native plugin without runtime-code changes. Its full suite was run against the active Duckwork host: **69 tests passed, with no skips**. Coverage includes native provider contracts, source-link normalization, all eight advanced operations, approval denial and replay, URL safety, symlinks, and file identity checks.

To exercise native host contracts as well as the standalone client tests, point to your Duckwork source checkout and use its Python environment:

```bash
export DUCKWORK_ACTIVE_SOURCE=/path/to/duckwork-agent
PYTHONPATH="$DUCKWORK_ACTIVE_SOURCE:src" "$DUCKWORK_ACTIVE_SOURCE/venv/bin/python" -m unittest discover -s tests -v
duckwork plugins validate plugin/markdown-new --json
```

Without `DUCKWORK_ACTIVE_SOURCE`, the native host contract tests are skipped. Do not report that run as the full release suite.

Bug reports and pull requests are welcome at [nosliwhtes/duckwork-markdown-new](https://github.com/DuckMind/duckwork).

## License and affiliation

MIT licensed. Community integration by [nosliwhtes](https://github.com/nosliwhtes), not affiliated with or endorsed by Markdown.new, Cloudflare, or Fordex. The MIT license covers this repository's code, not the third-party service or content you retrieve.
