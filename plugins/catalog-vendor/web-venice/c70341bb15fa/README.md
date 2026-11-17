# Duckwork Venice Web Provider

**Native Duckwork web backend powered by Venice AI's privacy-first `/augment` endpoints.**

This plugin registers Venice as a standard `web_search` / `web_extract` backend — the same architecture used by Firecrawl, Brave, Tavily, and all other built-in providers. No toolset juggling required.

| Capability | Endpoint | Price |
| --- | --- | --- |
| `web_search` | `POST /augment/search` | $0.01/request |
| `web_extract` | `POST /augment/scrape` | $0.01/URL |

---

## Why Venice

- **Zero Data Retention** — Brave backend never stores or logs queries.
- **Anonymized Google** fallback — Venice never links identity to requests.
- **Provider-independent** — uses standalone `/augment` endpoints, works with any LLM provider (OpenAI, Anthropic, local models, etc.).
- **Clean LLM-friendly output** — structured search results and Markdown extraction.

---

## Installation

### One-command (recommended)
```bash
duckwork plugins install mnrGreg/duckwork-venice-web --enable
```

### Manual
```bash
mkdir -p ~/.duckwork/plugins/web/venice
cd ~/.duckwork/plugins/web/venice
# Copy plugin files into this folder
duckwork plugins reload
```

### API key
Get your Venice API key at https://venice.ai, then:
```bash
echo 'VENICE_API_KEY=vk-XXXXXXXXXXXXXXXX' >> ~/.duckwork/.env
```

---

## Configuration

Select Venice via `duckwork tools` or set it directly in `~/.duckwork/config.yaml`:

```yaml
web:
  backend: venice
```

Or use per-capability keys to mix providers:

```yaml
web:
  search_backend: venice       # Venice for search
  extract_backend: firecrawl   # Firecrawl for extract
```

Keep the default `web` toolset enabled — Venice powers the standard `web_search` and `web_extract` tools directly.

### Search provider

Venice routes searches through Brave (default, zero data retention) or Google. Set via environment variable:

```bash
echo 'VENICE_SEARCH_PROVIDER=brave' >> ~/.duckwork/.env   # or "google"
```

---

## How it works

```
LLM tool call → web_search / web_extract
                    ↓
            web_search_registry
                    ↓
         VeniceWebSearchProvider
                    ↓
        Venice /augment/search or /scrape
```

Unlike the legacy tool-plugin approach (which registered separate `venice_web_search` / `venice_web_scrape` tools and required disabling the default `web` toolset), this backend provider integrates natively with Duckwork's web tools infrastructure.

---

## Venice web integration approaches

| Approach | How it works | When to use |
| --- | --- | --- |
| **This plugin** (recommended) | Agent decides per-turn via standard `web_search`/`web_extract` | Agentic workflows; works with any LLM provider |
| [Model feature suffix](https://docs.venice.ai/api-reference/endpoint/chat/model_feature_suffix) | Append flags to model ID (e.g. `default:enable_web_search=on`) | Always-on search with Venice inference |
| [`venice_parameters`](https://docs.venice.ai/api-reference/endpoint/chat/completions#body-venice-parameters-enable-web-scraping) | Set `enable_web_search` / `enable_web_scraping` in request body | Direct Venice API calls |

---

## API References

- Search: https://docs.venice.ai/api-reference/endpoint/augment/search
- Scrape: https://docs.venice.ai/api-reference/endpoint/augment/scrape
- Pricing: https://docs.venice.ai/overview/pricing#additional-features
- Duckwork web provider docs: https://duckwork-agent.fordex.com/docs/developer-guide/web-search-provider-plugin

---

Made for the Duckwork community by mnrGreg
