# SerpApi for Duckwork Agent

[![PyPI version](https://img.shields.io/pypi/v/serpapi-duckwork-plugin.svg)](https://pypi.org/project/serpapi-hermes-plugin/)
[![CI](https://github.com/DuckMind/duckwork)](https://github.com/DuckMind/duckwork)
[![Python versions](https://img.shields.io/pypi/pyversions/serpapi-duckwork-plugin.svg)](https://pypi.org/project/serpapi-hermes-plugin/)
[![License: MIT](https://img.shields.io/pypi/l/serpapi-duckwork-plugin.svg)](https://github.com/DuckMind/duckwork)

Give [Duckwork Agent](https://duckwork-agent.fordex.com/) fresh web, local, news, shopping, hotel, flight, and destination results with [SerpApi](https://serpapi.com/).

The plugin adds SerpApi to Duckwork in two ways:

- Duckwork's built-in `web_search` uses the fast Google Light engine.
- Dedicated Maps, News, Shopping, Hotels, Flights, and Travel Explore tools let Duckwork choose the right SerpApi engine for each request.
- Direct SerpApi tools return token-efficient Markdown by default, including tables, links, and YAML frontmatter designed for agents.

## Ask Duckwork to install it

You can let Duckwork install and configure the plugin for you. Paste the message below into a Duckwork chat, then approve the install or terminal commands if Duckwork prompts you:

```text
Install and configure the SerpApi plugin from its official GitHub repository:

duckwork plugins install serpapi/serpapi-duckwork-plugin --enable

Request my approval for install or terminal commands whenever required; do not
bypass approvals. Follow Duckwork's prompts to install Python dependencies and
enable the plugin named serpapi.

If Duckwork asks whether to allow this plugin to replace built-in tools, answer
no; serpapi-duckwork-plugin does not need tool-override access.

Use my existing SERPAPI_API_KEY if configured. Otherwise, ask me for my SerpApi
Private API Key when installation or setup requests it. I can copy it from
https://serpapi.com/dashboard. Save it through Duckwork's configuration in
~/.duckwork/.env without printing, logging, or committing it.

Configure SerpApi as the Duckwork web search backend, tell me whether Duckwork must
be restarted, and verify that web search, Maps, News, Shopping, Hotels, Flights,
and Travel Explore tools are available. Use this key for future SerpApi
searches and never expose it in output.
```

## Install

You need a working [Duckwork Agent installation](https://duckwork-agent.fordex.com/docs/getting-started/quickstart/) and a SerpApi account. Choose one installation method below. Both register the plugin as `serpapi` and provide the same search tools.

### From GitHub (recommended)

Use Duckwork's [plugin installer](https://duckwork-agent.fordex.com/docs/user-guide/features/plugins/#managing-plugins):

```bash
duckwork plugins install serpapi/serpapi-duckwork-plugin --enable
```

Follow the prompts for Python dependencies, enablement, and your SerpApi API key. Use a current Duckwork version with [plugin dependency management](https://duckwork-agent.fordex.com/docs/developer-guide/plugins#python-dependencies); older installers may clone the plugin without installing its dependencies.

To update a Git installation later:

```bash
duckwork plugins update serpapi
```

### From PyPI

For Duckwork installations whose Python environment you manage yourself, install the published package into the interpreter that runs Duckwork:

```bash
uv pip install --python /path/to/duckwork/python serpapi-duckwork-plugin
duckwork plugins enable serpapi
```

If your Duckwork installation uses `~/.duckwork/duckwork-agent/venv`, the install command is:

```bash
uv pip install --python ~/.duckwork/duckwork-agent/venv/bin/python serpapi-duckwork-plugin
```

The explicit [`--python`](https://docs.astral.sh/uv/pip/environments/#using-arbitrary-python-environments) selects Duckwork's environment without activating it. If that environment already has pip and is activated, `python -m pip install serpapi-duckwork-plugin` is equivalent. Use the GitHub option for current Duckwork-managed installations, as described in Duckwork's [pip distribution guidance](https://duckwork-agent.fordex.com/docs/developer-guide/plugins#distribute-via-pip).

Restart any running Duckwork session after installation.

## Get your SerpApi API key

1. [Create a SerpApi account](https://serpapi.com/users/sign_up), or sign in to
   your existing account.
2. Open the [SerpApi dashboard](https://serpapi.com/dashboard).
3. Find your **Private API Key** in the dashboard and copy it.

One API key powers every engine in this plugin. Keep it private and never add it
to source control.

## Connect the API key to Duckwork

If the plugin is not enabled yet, enable it:

```bash
duckwork plugins enable serpapi
```

If prompted about permission to replace built-in tools, answer **no**. This
plugin adds new tools and a web-search provider; it does not replace built-in
tool handlers.

Open Duckwork's interactive tool configuration:

```bash
duckwork tools
```

In the **Web Search & Extract** section:

1. Select **SerpApi**.
2. Paste the Private API Key copied from your SerpApi dashboard.
3. Confirm the selection.

Duckwork saves the key as `SERPAPI_API_KEY` in its environment configuration and
selects SerpApi for future `web_search` calls. Restart Duckwork if a session was
already running.

## Manual API-key setup

Instead of using `duckwork tools`, add the key to `~/.duckwork/.env`:

```dotenv
SERPAPI_API_KEY=your_private_api_key
```

Then configure `~/.duckwork/config.yaml`:

```yaml
plugins:
  enabled:
    - serpapi

web:
  search_backend: serpapi
```

You may also export `SERPAPI_API_KEY` in the environment that starts Duckwork.
The environment variable takes precedence over the value in `~/.duckwork/.env`.

## Search capabilities

Duckwork's built-in `web_search` contract requires structured web records, so the plugin requests JSON for that provider and converts it to Duckwork's standard response. The six directly registered SerpApi tools request [`output=md`](https://serpapi.com/search-api#api-parameters-output) by default and return SerpApi's Markdown without reparsing it. This preserves result tables and links while using fewer tokens than full JSON.

Each direct tool also accepts `output: "json"` when the agent needs structured fields such as a Google Flights `departure_token`. Markdown remains the schema default.

| What you ask for | Duckwork tool | SerpApi engine |
|---|---|---|
| General web research | `web_search` | `google_light` |
| Places and local businesses | `serpapi_maps_search` | `google_maps` |
| Current and recent news | `serpapi_news_search` | `google_news_light` |
| Products, prices, and merchants | `serpapi_shopping_search` | `google_shopping_light` |
| Hotels and vacation rentals | `serpapi_hotels_search` | [`google_hotels`](https://serpapi.com/google-hotels-api) |
| Fixed-route flight fares | `serpapi_flights_search` | [`google_flights`](https://serpapi.com/google-flights-api) |
| Flexible destinations and dates | `serpapi_travel_explore_search` | [`google_travel_explore`](https://serpapi.com/google-travel-explore-api) |

Duckwork chooses a tool from your request. Each tool selects and validates its own SerpApi engine, so you do not need to specify an engine name. Flight and Travel Explore location fields accept individual uppercase airport codes such as `LHR`, `CDG`, or `AUS`, as well as `/m/` or `/g/` location KGMIDs. Use Travel Explore when the traveler has a city or region in mind but no exact airport.

Example prompts:

- "Search the web for the latest Python 3.14 release notes."
- "Find highly rated coffee shops near Times Square."
- "Show me recent news about reusable rockets."
- "Find well-reviewed laptops under $1,200 with free shipping."
- "Find four-star hotels in Kyoto for October 10 to October 15."
- "Compare nonstop business-class flights from JFK to LAX next month."
- "Where can I go from Bengaluru for a one-week beach trip in December?"

Google Flights returns outbound choices first for round trips. To inspect return-flight choices, call `serpapi_flights_search` with `output: "json"`, select a `departure_token`, then call the tool again with that token and the same route and dates.

## Contributing

See [CONTRIBUTING.md](https://github.com/DuckMind/duckwork)
for development setup, tests, pull request guidelines, and the release process.

## License

[MIT](https://github.com/DuckMind/duckwork)
