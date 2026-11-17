"""Tool handlers: each one turns the LLM's arguments into one Financial Datasets API request.

A `fetch` function is pure request logic: it takes the cleaned arguments,
raises on bad input, and returns the JSON-ready result. `_as_handler` wraps it
in the Duckwork handler contract (always return a JSON string, never raise).
"""

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from . import client, schemas

ITEMS_10K = [
    "Item-1", "Item-1A", "Item-1B", "Item-2", "Item-3", "Item-4", "Item-5", "Item-6", "Item-7",
    "Item-7A", "Item-8", "Item-9", "Item-9A", "Item-9B", "Item-10", "Item-11", "Item-12",
    "Item-13", "Item-14", "Item-15", "Item-16",
]
ITEMS_10Q = ["Item-1", "Item-2", "Item-3", "Item-4"]
ITEMS_8K = [
    "Item-1.01", "Item-1.02", "Item-1.03", "Item-1.04", "Item-2.01", "Item-2.02", "Item-2.03",
    "Item-2.04", "Item-2.05", "Item-2.06", "Item-3.01", "Item-3.02", "Item-3.03", "Item-4.01",
    "Item-4.02", "Item-5.01", "Item-5.02", "Item-5.03", "Item-5.04", "Item-5.05", "Item-5.06",
    "Item-5.07", "Item-5.08", "Item-6.01", "Item-6.02", "Item-6.03", "Item-6.04", "Item-6.05",
    "Item-7.01", "Item-8.01", "Item-9.01",
]

# One tool for every macro dataset. Each value maps to the REST route that serves it.
MACRO_DATASET_PATHS = {
    "yield_curve": "macro/yield-curve",
    "interest_rates": "macro/interest-rates",
    "inflation": "macro/inflation",
}


# --- Argument helpers ---

def _clean(schema: dict, args: dict) -> dict:
    """The LLM's arguments with empty values dropped and the schema's defaults filled in."""
    properties = schema["parameters"]["properties"]
    defaults = {name: spec["default"] for name, spec in properties.items() if "default" in spec}
    given = {name: value for name, value in args.items() if value is not None and value != ""}
    return {**defaults, **given}


def _query(args: dict, exclude: tuple = ()) -> dict:
    """Arguments as API query parameters: tickers upper-cased, CIKs zero-padded,
    `true` flags spelled the way the API reads them, and `false` flags omitted."""
    query = {}
    for name, value in args.items():
        if name in exclude or value is False:
            continue
        if name == "ticker":
            value = value.upper()
        elif name == "filer_cik":
            value = value.zfill(10)
        elif value is True:
            value = "true"
        query[name] = value
    return query


def _require_exactly_one(args: dict, first: str, second: str) -> None:
    if not args.get(first) and not args.get(second):
        raise ValueError(f"Either {first} or {second} is required")
    if args.get(first) and args.get(second):
        raise ValueError(f"Give either {first} or {second}, not both")


# --- Fetch functions ---

def _route(path: str, response_key: str | None = None, paginated: bool = False):
    """A tool whose arguments map one-to-one onto the query string of one route."""
    def fetch(args: dict):
        data = client.get(path, _query(args), paginated=paginated)
        return data.get(response_key) if response_key else data
    return fetch


def _beneficial_owners(args: dict):
    data = client.get("beneficial-ownership/filers/", _query(args))
    return {"total": data.get("total"), "filers": data.get("filers")}


def _beneficial_ownership(args: dict):
    _require_exactly_one(args, "ticker", "filer_cik")
    return _route("beneficial-ownership/", "beneficial_owners", paginated=True)(args)


def _institutional_holdings(args: dict):
    _require_exactly_one(args, "ticker", "filer_cik")
    return _route("institutional-holdings/", "institutional_holdings", paginated=True)(args)


def _company_facts(args: dict):
    _require_exactly_one(args, "ticker", "cik")
    return _route("company/facts/", "company_facts")(args)


def _filings(args: dict):
    if not args.get("ticker") and not args.get("cik"):
        raise ValueError("Either ticker or cik is required")
    # A ticker wins over a CIK, the same as the MCP server.
    exclude = ("cik",) if args.get("ticker") else ()
    data = client.get("filings/", _query(args, exclude=exclude), paginated=True)
    return data.get("filings")


def _filing_items(args: dict):
    filing_type = args.get("filing_type")
    if filing_type == "8-K":
        if not args.get("accession_number"):
            raise ValueError("accession_number is required for 8-K filings")
    else:
        if not args.get("year"):
            raise ValueError("year is required for 10-K and 10-Q filings")
        if filing_type == "10-Q" and not args.get("quarter"):
            raise ValueError("quarter is required for 10-Q filings")
    return client.get("filings/items/", _query(args))


def _filing_item_types(args: dict):
    return {"10-K": ITEMS_10K, "10-Q": ITEMS_10Q, "8-K": ITEMS_8K}


def _financial_statement(endpoint: str, response_key: str):
    def fetch(args: dict):
        # As-reported routes live at `<endpoint>/as-reported` and serve only
        # 'annual' or 'quarterly', so 'ttm' becomes 'annual'.
        as_reported = args.get("as_reported") is True
        path = f"financials/{endpoint}/as-reported/" if as_reported else f"financials/{endpoint}/"
        query = _query(args, exclude=("as_reported",))
        if as_reported and query.get("period") == "ttm":
            query["period"] = "annual"
        return client.get(path, query, paginated=True).get(response_key)
    return fetch


def _macro_data(args: dict):
    dataset = args.get("dataset")
    if dataset not in MACRO_DATASET_PATHS:
        raise ValueError(f"dataset must be one of: {', '.join(MACRO_DATASET_PATHS)}")

    # No dates means the snapshot route (latest values). Any date means the
    # history route, which serves one bank or one series per request.
    is_snapshot = not args.get("start_date") and not args.get("end_date")
    if not is_snapshot and dataset == "interest_rates" and not args.get("bank"):
        raise ValueError(
            "interest_rates history is served per central bank. Give a bank code "
            "(e.g. 'FED', 'ECB', 'BOJ'), or omit the dates for every bank's current rate."
        )
    if not is_snapshot and dataset == "inflation" and not args.get("series"):
        raise ValueError(
            "inflation history is served per series. Give a series id (e.g. 'cpi_all_sa'), "
            "or omit the dates for the latest month of every series."
        )

    query = _query(args, exclude=("dataset",))
    if "bank" in query:
        query["bank"] = query["bank"].upper()
    if "series" in query:
        query["series"] = query["series"].lower()

    base = MACRO_DATASET_PATHS[dataset]
    path = f"{base}/snapshot/" if is_snapshot else f"{base}/"
    return client.get(path, query, paginated=not is_snapshot).get(dataset)


def _stock_prices(args: dict):
    # Defaults: the window ends today in Eastern time and starts 1 year before it ends.
    end_date = args.get("end_date") or datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    start_date = args.get("start_date") or _one_year_before(date.fromisoformat(end_date)).isoformat()
    query = {**_query(args), "start_date": start_date, "end_date": end_date}
    return client.get("prices/", query, paginated=True).get("prices")


def _one_year_before(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # Feb 29 in a leap year
        return day.replace(year=day.year - 1, day=28)


def _screen_stocks(args: dict):
    if not args.get("filters"):
        raise ValueError("At least one filter is required. Call fd_list_stock_screener_filters to see the fields.")
    body = {"filters": args["filters"], "currency": args["currency"], "limit": args["limit"]}
    return client.post("financials/search/screener/", body).get("results")


# --- Handlers ---

def _as_handler(tool_name: str, fetch):
    """Wrap a fetch function in the Duckwork handler contract: JSON string out, never raise."""
    schema = schemas.BY_NAME[tool_name]

    def handler(args: dict, **kwargs) -> str:
        try:
            return json.dumps(fetch(_clean(schema, args or {})))
        except (client.ApiError, ValueError) as error:
            return json.dumps({"error": str(error)})
        except Exception as error:
            return json.dumps({"error": f"{tool_name} failed: {error}"})

    return handler


_FETCHERS = {
    "fd_get_beneficial_owners": _beneficial_owners,
    "fd_get_beneficial_ownership": _beneficial_ownership,
    "fd_get_company_facts": _company_facts,
    "fd_get_earnings": _route("earnings/", "earnings", paginated=True),
    "fd_get_filing_items": _filing_items,
    "fd_list_filing_item_types": _filing_item_types,
    "fd_get_filings": _filings,
    "fd_get_financial_metrics": _route("financial-metrics/", "financial_metrics", paginated=True),
    "fd_get_financial_metrics_snapshot": _route("financial-metrics/snapshot/", "snapshot"),
    "fd_get_balance_sheet": _financial_statement("balance-sheets", "balance_sheets"),
    "fd_get_income_statement": _financial_statement("income-statements", "income_statements"),
    "fd_get_cash_flow_statement": _financial_statement("cash-flow-statements", "cash_flow_statements"),
    "fd_get_index_fund": _route("index-funds/", paginated=True),
    "fd_get_insider_ownership": _route("insider-ownership/", "insider_ownership", paginated=True),
    "fd_get_insider_trades": _route("insider-trades/", "insider_trades", paginated=True),
    "fd_get_institutional_investors": _route("institutional-holdings/investors", "investors"),
    "fd_get_institutional_holdings": _institutional_holdings,
    "fd_get_interest_rates": _route("macro/interest-rates/snapshot/", "interest_rates"),
    "fd_get_kpi_guidance": _route("kpi/guidance/", "kpi_guidance", paginated=True),
    "fd_get_kpi_metrics": _route("kpi/metrics/", "kpi_metrics", paginated=True),
    "fd_get_kpi_non_gaap": _route("kpi/non-gaap/", "kpi_non_gaap", paginated=True),
    "fd_get_macro_data": _macro_data,
    "fd_get_news": _route("news/", "news", paginated=True),
    "fd_get_segmented_financials": _route("financials/segments/", "segmented_financials", paginated=True),
    "fd_get_stock_price": _route("prices/snapshot/", "snapshot"),
    "fd_get_stock_prices": _stock_prices,
    "fd_screen_stocks": _screen_stocks,
    "fd_list_stock_screener_filters": _route("financials/search/screener/filters/"),
}

HANDLERS = {name: _as_handler(name, fetch) for name, fetch in _FETCHERS.items()}
