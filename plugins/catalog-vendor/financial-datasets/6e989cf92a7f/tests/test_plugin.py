import json
from pathlib import Path

import yaml

PLUGIN_DIR = Path(__file__).resolve().parent.parent


def call(plugin, tool_name, args):
    return json.loads(plugin.tools.HANDLERS[tool_name](args))


# --- Registration and manifest ---

def test_register_wires_every_schema_to_a_handler(plugin):
    registered = {}

    class Ctx:
        def register_tool(self, name, toolset, schema, handler, **kwargs):
            registered[name] = (toolset, schema, handler)

    plugin.register(Ctx())

    assert len(registered) == 28
    assert all(name.startswith("fd_") for name in registered)
    assert all(toolset == "financial_datasets" for toolset, _, _ in registered.values())
    assert all(schema["name"] == name for name, (_, schema, _) in registered.items())


def test_manifest_lists_exactly_the_registered_tools(plugin):
    manifest = yaml.safe_load((PLUGIN_DIR / "plugin.yaml").read_text())
    assert manifest["provides_tools"] == [schema["name"] for schema in plugin.schemas.ALL_SCHEMAS]
    assert [env["name"] for env in manifest["requires_env"]] == [plugin.client.API_KEY_ENV]


def test_every_schema_has_a_handler(plugin):
    assert set(plugin.tools.HANDLERS) == set(plugin.schemas.BY_NAME)


# --- Request building ---

def test_ticker_is_upper_cased_and_schema_defaults_are_sent(plugin, api):
    api.response = {"income_statements": [{"revenue": 1}]}
    result = call(plugin, "fd_get_income_statement", {"ticker": "aapl"})

    assert result == [{"revenue": 1}]
    assert api.calls == [{
        "method": "GET",
        "path": "financials/income-statements/",
        "params": {"ticker": "AAPL", "period": "ttm", "limit": 4},
        "paginated": True,
    }]


def test_as_reported_uses_its_own_route_and_turns_ttm_into_annual(plugin, api):
    call(plugin, "fd_get_balance_sheet", {"ticker": "TSLA", "as_reported": True})
    assert api.calls[0]["path"] == "financials/balance-sheets/as-reported/"
    assert api.calls[0]["params"] == {"ticker": "TSLA", "period": "annual", "limit": 4}


def test_filer_cik_is_zero_padded_and_true_flags_are_spelled_out(plugin, api):
    call(plugin, "fd_get_beneficial_ownership", {"filer_cik": "1067983", "history": True})
    assert api.calls[0]["params"] == {"filer_cik": "0001067983", "history": "true", "limit": 10}


def test_empty_arguments_are_dropped(plugin, api):
    call(plugin, "fd_get_news", {"ticker": "", "limit": None})
    assert api.calls[0]["params"] == {"limit": 5}


def test_stock_prices_default_to_the_year_before_the_end_date(plugin, api):
    call(plugin, "fd_get_stock_prices", {"ticker": "msft", "end_date": "2024-02-29"})
    assert api.calls[0]["params"] == {
        "ticker": "MSFT", "interval": "day", "interval_multiplier": 1,
        "start_date": "2023-02-28", "end_date": "2024-02-29",
    }


def test_macro_without_dates_reads_the_snapshot_route(plugin, api):
    api.response = {"yield_curve": {"10_year": 4.1}}
    assert call(plugin, "fd_get_macro_data", {"dataset": "yield_curve"}) == {"10_year": 4.1}
    assert api.calls[0]["path"] == "macro/yield-curve/snapshot/"
    assert api.calls[0]["paginated"] is False


def test_macro_with_dates_reads_the_history_route(plugin, api):
    call(plugin, "fd_get_macro_data", {"dataset": "interest_rates", "start_date": "2024-01-01", "bank": "fed"})
    assert api.calls[0]["path"] == "macro/interest-rates/"
    assert api.calls[0]["params"] == {"start_date": "2024-01-01", "bank": "FED"}
    assert api.calls[0]["paginated"] is True


def test_screener_posts_the_filters(plugin, api):
    api.response = {"results": [{"ticker": "AAPL"}]}
    filters = [{"field": "revenue", "operator": "gt", "value": 1e9}]
    assert call(plugin, "fd_screen_stocks", {"filters": filters}) == [{"ticker": "AAPL"}]
    assert api.calls == [{
        "method": "POST",
        "path": "financials/search/screener/",
        "body": {"filters": filters, "currency": "USD", "limit": 10},
    }]


def test_filing_item_types_needs_no_request(plugin, api):
    result = call(plugin, "fd_list_filing_item_types", {})
    assert set(result) == {"10-K", "10-Q", "8-K"}
    assert api.calls == []


# --- Input errors are returned, never raised, and cost no request ---

def test_input_errors_are_returned_before_any_request(plugin, api):
    cases = [
        ("fd_get_company_facts", {}, "Either ticker or cik"),
        ("fd_get_company_facts", {"ticker": "AAPL", "cik": "320193"}, "not both"),
        ("fd_get_filings", {}, "Either ticker or cik"),
        ("fd_get_institutional_holdings", {}, "Either ticker or filer_cik"),
        ("fd_get_filing_items", {"ticker": "AAPL", "filing_type": "8-K"}, "accession_number"),
        ("fd_get_filing_items", {"ticker": "AAPL", "filing_type": "10-K"}, "year"),
        ("fd_get_filing_items", {"ticker": "AAPL", "filing_type": "10-Q", "year": 2025}, "quarter"),
        ("fd_get_macro_data", {"dataset": "interest_rates", "start_date": "2024-01-01"}, "bank code"),
        ("fd_get_macro_data", {"dataset": "inflation", "end_date": "2024-01-01"}, "series id"),
        ("fd_get_macro_data", {"dataset": "gdp"}, "dataset must be one of"),
        ("fd_screen_stocks", {"filters": []}, "At least one filter"),
    ]
    for tool_name, args, expected in cases:
        assert expected in call(plugin, tool_name, args)["error"], tool_name
    assert api.calls == []


def test_api_errors_are_returned_as_json(plugin, monkeypatch):
    def rejected(*args, **kwargs):
        raise plugin.client.ApiError("HTTP 402: Insufficient credits")

    monkeypatch.setattr(plugin.client, "get", rejected)
    assert call(plugin, "fd_get_stock_price", {"ticker": "AAPL"}) == {"error": "HTTP 402: Insufficient credits"}


# --- Client ---

def test_missing_api_key_names_the_env_var(plugin, monkeypatch):
    monkeypatch.delenv(plugin.client.API_KEY_ENV, raising=False)
    result = call(plugin, "fd_get_stock_price", {"ticker": "AAPL"})
    assert "FINANCIAL_DATASETS_API_KEY is not set" in result["error"]


def test_pagination_merges_pages_and_stays_on_the_api_host(plugin, monkeypatch):
    base = plugin.client.API_BASE
    pages = {
        f"{base}prices/?ticker=AAPL": {"ticker": "AAPL", "prices": [1], "next_page_url": f"{base}prices/?cursor=2"},
        f"{base}prices/?cursor=2": {"ticker": "AAPL", "prices": [2], "next_page_url": "https://evil.example/steal"},
    }
    requested = []

    def fake_request(url, body=None):
        requested.append(url)
        return pages[url]

    monkeypatch.setattr(plugin.client, "_request", fake_request)
    merged = plugin.client.get("prices/", {"ticker": "AAPL"}, paginated=True)

    assert merged == {"ticker": "AAPL", "prices": [1, 2]}
    assert requested == list(pages)
