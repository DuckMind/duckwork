# Duckwork Plugin: Brave Search

Live web search inside Duckwork Agent via the [Brave Search API](https://brave.com/search/api/).

Registers one tool (`brave_web_search`) under the `brave-search` toolset.

## Install

```bash
duckwork plugins install rabilrbl/duckwork-brave-search-plugin
```

During installation you will be prompted to enter your Brave Search API key (`BRAVE_API_KEY`). The value is saved to `~/.duckwork/.env`.

## Getting your API key

1. Go to [https://api-dashboard.search.brave.com/app/keys](https://api-dashboard.search.brave.com/app/keys).
2. Sign up or log in.
3. Click **+ Add API Key** and copy the subscription token.

Then set it manually if you skipped the prompt:

```bash
# ~/.duckwork/.env
BRAVE_API_KEY="your-api-key-here"
```

Restart Duckwork or run `/reset` to reload.

## Usage

Enable the `brave-search` toolset:

```bash
duckwork tools enable brave-search
```

Then ask Duckwork to search:

```
Search for the latest Rust release notes
```

## Parameters

| Parameter     | Type    | Required | Description                                       |
|---------------|---------|----------|---------------------------------------------------|
| `query`       | string  | Yes      | Search query                                       |
| `count`       | integer | No       | Number of results (1–20, default 10)               |
| `country`     | string  | No       | Country code, e.g. `us`, `in`                      |
| `search_lang` | string  | No       | Result language code, e.g. `en`                    |
| `freshness`   | string  | No       | Recency filter: `pd` (day), `pw` (week), `pm` (month), `py` (year) |
| `safesearch`  | string  | No       | `off`, `moderate` (default), or `strict`           |

## Example output

```json
{
  "query": "Rust release notes",
  "count": 10,
  "results": [
    {
      "title": "Rust 1.78.0 | Rust Blog",
      "url": "https://blog.rust-lang.org/2024/05/02/Rust-1.78.0.html",
      "description": "Announcing Rust 1.78.0...",
      "source": "Rust Blog",
      "age": "2 weeks ago"
    }
  ]
}
```

## Files

- `plugin.yaml` — manifest and env requirements
- `schemas.py` — tool schema shown to the model
- `tools.py` — Brave Search API implementation
- `__init__.py` — plugin registration wiring

## License

MIT