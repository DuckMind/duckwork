# Financial Datasets plugin for Duckwork Agent

Stock market data for [Duckwork Agent](https://duckwork-agent.fordex.com), from the [Financial Datasets](https://financialdatasets.ai) API. The plugin adds 28 read-only tools: financial statements, stock prices, SEC filings, insider and institutional ownership, KPIs, news, macro data, and a stock screener.

## Install

```bash
duckwork plugins install financial-datasets/duckwork-plugin
duckwork plugins enable financial-datasets
```

Duckwork asks for `FINANCIAL_DATASETS_API_KEY` during the install and saves it to `~/.duckwork/.env`. Get a key at [financialdatasets.ai](https://financialdatasets.ai). API usage is billed to that key, see [pricing](https://www.financialdatasets.ai/pricing).

## Try it

- "What was Apple's revenue and net income over the last 4 quarters?"
- "Show me insider trades at Nvidia this year."
- "Which companies have revenue above $100B and a P/E ratio under 20?"
- "What does the US Treasury yield curve look like today?"
- "Pull the risk factors from Tesla's latest 10-K."

## Tools

Every tool name starts with `fd_`, so it cannot collide with tools from other plugins.

| Group | Tools |
|---|---|
| Company | `fd_get_company_facts` |
| Financial statements | `fd_get_income_statement`, `fd_get_balance_sheet`, `fd_get_cash_flow_statement`, `fd_get_segmented_financials` |
| Metrics | `fd_get_financial_metrics`, `fd_get_financial_metrics_snapshot` |
| Earnings | `fd_get_earnings` |
| KPIs | `fd_get_kpi_metrics`, `fd_get_kpi_guidance`, `fd_get_kpi_non_gaap` |
| Prices | `fd_get_stock_price`, `fd_get_stock_prices` |
| SEC filings | `fd_get_filings`, `fd_get_filing_items`, `fd_list_filing_item_types` |
| Insiders | `fd_get_insider_trades`, `fd_get_insider_ownership` |
| Institutions (13F) | `fd_get_institutional_investors`, `fd_get_institutional_holdings` |
| Beneficial owners (13D/13G) | `fd_get_beneficial_owners`, `fd_get_beneficial_ownership` |
| Index funds | `fd_get_index_fund` |
| Macro | `fd_get_macro_data`, `fd_get_interest_rates` |
| News | `fd_get_news` |
| Screener | `fd_screen_stocks`, `fd_list_stock_screener_filters` |

The tools mirror the [Financial Datasets MCP server](https://docs.financialdatasets.ai/mcp-server). Full API reference: [docs.financialdatasets.ai](https://docs.financialdatasets.ai).

## Security

- Every tool is read-only.
- The plugin uses the Python standard library only. It has no dependencies.
- It sends requests to `api.financialdatasets.ai` and to no other host. The API key goes in the `X-API-KEY` header of those requests only.
- It writes no files and does not update itself.

## Development

```bash
pip install pytest pyyaml
python -m pytest tests
```

The tests need no API key and send no requests.

## License

MIT
