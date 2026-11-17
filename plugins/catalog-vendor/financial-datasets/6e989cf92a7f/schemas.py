"""Tool schemas: what the LLM sees.

Each schema mirrors the same tool on the Financial Datasets MCP server
(https://mcp.financialdatasets.ai), with an ``fd_`` prefix on the name so it
cannot collide with tools from other plugins.
"""

GET_BENEFICIAL_OWNERS = {'name': 'fd_get_beneficial_owners',
 'description': "Lists beneficial owners (holders of more than 5% of a company's shares, from SEC "
                'Schedules 13D/13G) with their filer CIK and reporting-person name. Optionally '
                "filter by case-insensitive name prefix. The response's `total` is the full match "
                'count; when it exceeds the returned page, narrow the search with `name`. Use this '
                'to discover the filer_cik to pass to fd_get_beneficial_ownership.',
 'parameters': {'type': 'object',
                'properties': {'name': {'type': 'string',
                                        'description': 'Optional case-insensitive name prefix to '
                                                       'filter the beneficial-owner list (e.g. '
                                                       "'Saba'). Use this tool to discover the "
                                                       'filer_cik to pass to '
                                                       'fd_get_beneficial_ownership.'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 1000,
                                         'default': 100,
                                         'description': 'Number of owners to return (default: 100, '
                                                        "max: 1000). The response's `total` is the "
                                                        'full match count; when it exceeds the '
                                                        'page, narrow with `name`.'}},
                'required': []}}

GET_BENEFICIAL_OWNERSHIP = {'name': 'fd_get_beneficial_ownership',
 'description': 'Retrieves beneficial-ownership stakes (holders of more than 5% of a class of '
                'shares) from SEC Schedules 13D and 13G. Schedule 13D stakes are ACTIVIST (intent '
                'to influence control: proxy fights, board seats, pushing for a sale); Schedule '
                '13G stakes are passive (large asset managers). Query by ticker (who owns this '
                'company) OR by filer_cik (what stakes does this owner hold) — exactly one is '
                "required. Use type=activist to isolate activist stakes. By default each stake's "
                'CURRENT state is returned; set history=true for the full amendment chain. Each '
                'row is one reporting person with voting/dispositive powers, percent_of_class, and '
                '(for 13D) the stated purpose_of_transaction. Coverage begins January 2025.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The subject company's ticker (e.g. "
                                                         "'BB'). Returns its 5%+ beneficial "
                                                         'owners. Provide exactly one of ticker or '
                                                         'filer_cik.'},
                               'filer_cik': {'type': 'string',
                                             'description': 'SEC CIK of the beneficial owner (e.g. '
                                                            "'0001510281' for Saba Capital). "
                                                            'Returns their stakes across '
                                                            'companies. Will be zero-padded to 10 '
                                                            'digits. Provide exactly one of ticker '
                                                            'or filer_cik. Use '
                                                            'fd_get_beneficial_owners to look up '
                                                            'CIKs by owner name.'},
                               'type': {'type': 'string',
                                        'enum': ['activist', 'passive'],
                                        'description': "Filter by stake type: 'activist' (Schedule "
                                                       '13D, intent to influence control) or '
                                                       "'passive' (Schedule 13G). Omit for both."},
                               'history': {'type': 'boolean',
                                           'description': 'When true, returns the full amendment '
                                                          'history of each stake instead of only '
                                                          'its current state (the default).'},
                               'filing_date': {'type': 'string',
                                               'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                               'description': 'Exact filing date filter in '
                                                              'YYYY-MM-DD format'},
                               'filing_date_gte': {'type': 'string',
                                                   'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                   'description': 'Filing date greater than or '
                                                                  'equal to (YYYY-MM-DD)'},
                               'filing_date_lte': {'type': 'string',
                                                   'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                   'description': 'Filing date less than or equal '
                                                                  'to (YYYY-MM-DD)'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 1000,
                                         'default': 10,
                                         'description': 'Number of rows to return (default: 10, '
                                                        'max: 1000).'}},
                'required': []}}

GET_COMPANY_FACTS = {'name': 'fd_get_company_facts',
 'description': 'Get comprehensive company facts data for a stock ticker or CIK from Financial '
                'Datasets. Returns real-time information including market cap, number of '
                'employees, sector/industry classification, exchange listing, company location, '
                'website URL, SIC codes, weighted average shares, and historical events like '
                'ticker changes.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA'). Either ticker or cik is "
                                                         'required.'},
                               'cik': {'type': 'string',
                                       'description': 'The CIK (Central Index Key) identifier. '
                                                      'Either ticker or cik is required.'}},
                'required': []}}

GET_EARNINGS = {'name': 'fd_get_earnings',
 'description': 'Retrieves earnings data from SEC filings. Returns a flat list of `EarningsRecord` '
                'entries — same shape in either mode.\n'
                '  • COMPANY EARNINGS — pass a `ticker` to get the most recent SEC filings (8-K / '
                '10-Q / 10-K / 20-F) for that company. The same `report_period` may appear in two '
                'consecutive entries when an 8-K announcement and the matching 10-Q have both been '
                'filed; the 8-K comes first because it filed earlier. Sorted `(report_period DESC, '
                'filing_date ASC)`.\n'
                '  • EARNINGS FEED — omit `ticker` to get the real-time feed of the most recently '
                'filed earnings across all covered companies, sorted by `filing_date` descending '
                'and deduped by `(ticker, report_period)`.\n'
                'Each entry exposes `ticker`, `report_period`, `fiscal_period`, `currency`, '
                '`source_type`, `filing_date`, `filing_url`, `accession_number`, plus `quarterly` '
                'and/or `annual` financial blocks (revenue, EPS, surprise vs estimates, etc.).',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': 'Optional. The stock ticker symbol (e.g., '
                                                         "'AAPL', 'MSFT', 'TSLA') to fetch a "
                                                         "single company's most recent earnings. "
                                                         'Omit this parameter to instead fetch the '
                                                         'real-time Earnings Feed — the most '
                                                         'recently filed earnings across ALL '
                                                         'covered companies.'}},
                'required': []}}

GET_FILING_ITEMS = {'name': 'fd_get_filing_items',
 'description': "Retrieves specific sections (items) from a company's SEC filings (10-K, 10-Q, or "
                "8-K). Useful for extracting detailed information such as 'Business', 'Risk "
                "Factors', or 'Financial Statements and Supplementary Data'.",
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string', 'description': 'The ticker symbol.'},
                               'filing_type': {'type': 'string',
                                               'enum': ['10-K', '10-Q', '8-K'],
                                               'description': 'The type of filing.'},
                               'year': {'type': 'integer',
                                        'exclusiveMinimum': 0,
                                        'description': 'The year of the filing. Required for 10-K '
                                                       'and 10-Q filings.'},
                               'quarter': {'type': 'integer',
                                           'exclusiveMinimum': 0,
                                           'minimum': 1,
                                           'maximum': 4,
                                           'description': 'The quarter of the filing if 10-Q.'},
                               'accession_number': {'type': 'string',
                                                    'description': 'The accession number for the '
                                                                   'filing. Required for 8-K '
                                                                   'filings.'},
                               'item': {'type': 'array',
                                        'items': {'type': 'string',
                                                  'enum': ['Item-1',
                                                           'Item-1A',
                                                           'Item-1B',
                                                           'Item-2',
                                                           'Item-3',
                                                           'Item-4',
                                                           'Item-5',
                                                           'Item-6',
                                                           'Item-7',
                                                           'Item-7A',
                                                           'Item-8',
                                                           'Item-9',
                                                           'Item-9A',
                                                           'Item-9B',
                                                           'Item-10',
                                                           'Item-11',
                                                           'Item-12',
                                                           'Item-13',
                                                           'Item-14',
                                                           'Item-15',
                                                           'Item-16',
                                                           'Item-1.01',
                                                           'Item-1.02',
                                                           'Item-1.03',
                                                           'Item-1.04',
                                                           'Item-2.01',
                                                           'Item-2.02',
                                                           'Item-2.03',
                                                           'Item-2.04',
                                                           'Item-2.05',
                                                           'Item-2.06',
                                                           'Item-3.01',
                                                           'Item-3.02',
                                                           'Item-3.03',
                                                           'Item-4.01',
                                                           'Item-4.02',
                                                           'Item-5.01',
                                                           'Item-5.02',
                                                           'Item-5.03',
                                                           'Item-5.04',
                                                           'Item-5.05',
                                                           'Item-5.06',
                                                           'Item-5.07',
                                                           'Item-5.08',
                                                           'Item-6.01',
                                                           'Item-6.02',
                                                           'Item-6.03',
                                                           'Item-6.04',
                                                           'Item-6.05',
                                                           'Item-7.01',
                                                           'Item-8.01',
                                                           'Item-9.01']},
                                        'description': 'The item or items to get.'}},
                'required': ['ticker', 'filing_type']}}

LIST_FILING_ITEM_TYPES = {'name': 'fd_list_filing_item_types',
 'description': 'Provides a list of all available item names that can be extracted from 10-K, '
                '10-Q, and 8-K reports, grouped by filing type.',
 'parameters': {'type': 'object', 'properties': {}, 'required': []}}

GET_FILINGS = {'name': 'fd_get_filings',
 'description': 'Get SEC filings data for a stock ticker or CIK. Returns a list of filings, '
                'including the accession number, filing type, report date, and URLs to the filing '
                'documents.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA'). Either ticker or cik is "
                                                         'required.'},
                               'cik': {'type': 'string',
                                       'description': 'The CIK (Central Index Key) identifier. '
                                                      'Either ticker or cik is required.'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 1000,
                                         'default': 100,
                                         'description': 'Number of filings to retrieve (default: '
                                                        '100, max: 1000)'},
                               'filing_type': {'type': 'string',
                                               'description': 'Filter by specific filing type '
                                                              "(e.g., '10-K', '10-Q', '8-K', 'DEF "
                                                              "14A')"}},
                'required': []}}

GET_FINANCIAL_METRICS = {'name': 'fd_get_financial_metrics',
 'description': 'Retrieves historical financial metrics for a company, such as P/E ratio, revenue '
                'per share, and enterprise value, over a specified period. Useful for trend '
                'analysis and historical performance evaluation.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'period': {'type': 'string',
                                          'enum': ['annual', 'quarterly', 'ttm'],
                                          'default': 'ttm',
                                          'description': "The reporting period (default: 'ttm' for "
                                                         'trailing twelve months)'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 100,
                                         'default': 4,
                                         'description': 'Number of periods to retrieve (default: '
                                                        '4, max: 100)'},
                               'report_period_gte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'Start date filter in '
                                                                    'YYYY-MM-DD format '
                                                                    '(inclusive)'},
                               'report_period_lte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'End date filter in YYYY-MM-DD '
                                                                    'format (inclusive)'},
                               'report_period_gt': {'type': 'string',
                                                    'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                    'description': 'Start date filter in '
                                                                   'YYYY-MM-DD format (exclusive)'},
                               'report_period_lt': {'type': 'string',
                                                    'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                    'description': 'End date filter in YYYY-MM-DD '
                                                                   'format (exclusive)'},
                               'report_period': {'type': 'string',
                                                 'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                 'description': 'Exact report period date in '
                                                                'YYYY-MM-DD format'}},
                'required': ['ticker']}}

GET_FINANCIAL_METRICS_SNAPSHOT = {'name': 'fd_get_financial_metrics_snapshot',
 'description': 'Fetches a snapshot of the most current financial metrics for a company, including '
                'key indicators like market capitalization, P/E ratio, and dividend yield. Useful '
                "for a quick overview of a company's financial health.",
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"}},
                'required': ['ticker']}}

GET_BALANCE_SHEET = {'name': 'fd_get_balance_sheet',
 'description': "Retrieves a company's balance sheet, which provides a snapshot of its assets, "
                "liabilities, and shareholders' equity at a specific point in time. Essential for "
                "assessing a company's financial position.",
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'period': {'type': 'string',
                                          'enum': ['annual', 'quarterly', 'ttm'],
                                          'default': 'ttm',
                                          'description': "The reporting period (default: 'ttm' for "
                                                         'trailing twelve months)'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 100,
                                         'default': 4,
                                         'description': 'Number of periods to retrieve (default: '
                                                        '4, max: 100)'},
                               'report_period_gte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'Start date filter in '
                                                                    'YYYY-MM-DD format '
                                                                    '(inclusive)'},
                               'report_period_lte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'End date filter in YYYY-MM-DD '
                                                                    'format (inclusive)'},
                               'report_period_gt': {'type': 'string',
                                                    'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                    'description': 'Start date filter in '
                                                                   'YYYY-MM-DD format (exclusive)'},
                               'report_period_lt': {'type': 'string',
                                                    'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                    'description': 'End date filter in YYYY-MM-DD '
                                                                   'format (exclusive)'},
                               'report_period': {'type': 'string',
                                                 'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                 'description': 'Exact report period date in '
                                                                'YYYY-MM-DD format'},
                               'as_reported': {'type': 'boolean',
                                               'default': False,
                                               'description': 'When true, returns raw as-reported '
                                                              'line items exactly as they appear '
                                                              "in the company's filing, rather "
                                                              'than the standardized fields. Only '
                                                              "supports 'annual' or 'quarterly' "
                                                              "periods (a 'ttm' period is treated "
                                                              "as 'annual')."}},
                'required': ['ticker']}}

GET_INCOME_STATEMENT = {'name': 'fd_get_income_statement',
 'description': "Fetches a company's income statement, detailing its revenues, expenses, and net "
                "income over a reporting period. Useful for evaluating a company's profitability "
                'and operational efficiency.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'period': {'type': 'string',
                                          'enum': ['annual', 'quarterly', 'ttm'],
                                          'default': 'ttm',
                                          'description': "The reporting period (default: 'ttm' for "
                                                         'trailing twelve months)'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 100,
                                         'default': 4,
                                         'description': 'Number of periods to retrieve (default: '
                                                        '4, max: 100)'},
                               'report_period_gte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'Start date filter in '
                                                                    'YYYY-MM-DD format '
                                                                    '(inclusive)'},
                               'report_period_lte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'End date filter in YYYY-MM-DD '
                                                                    'format (inclusive)'},
                               'report_period_gt': {'type': 'string',
                                                    'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                    'description': 'Start date filter in '
                                                                   'YYYY-MM-DD format (exclusive)'},
                               'report_period_lt': {'type': 'string',
                                                    'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                    'description': 'End date filter in YYYY-MM-DD '
                                                                   'format (exclusive)'},
                               'report_period': {'type': 'string',
                                                 'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                 'description': 'Exact report period date in '
                                                                'YYYY-MM-DD format'},
                               'as_reported': {'type': 'boolean',
                                               'default': False,
                                               'description': 'When true, returns raw as-reported '
                                                              'line items exactly as they appear '
                                                              "in the company's filing, rather "
                                                              'than the standardized fields. Only '
                                                              "supports 'annual' or 'quarterly' "
                                                              "periods (a 'ttm' period is treated "
                                                              "as 'annual')."}},
                'required': ['ticker']}}

GET_CASH_FLOW_STATEMENT = {'name': 'fd_get_cash_flow_statement',
 'description': "Provides a company's cash flow statement, showing how cash is generated and used "
                'across operating, investing, and financing activities. Key for understanding a '
                "company's liquidity and solvency.",
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'period': {'type': 'string',
                                          'enum': ['annual', 'quarterly', 'ttm'],
                                          'default': 'ttm',
                                          'description': "The reporting period (default: 'ttm' for "
                                                         'trailing twelve months)'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 100,
                                         'default': 4,
                                         'description': 'Number of periods to retrieve (default: '
                                                        '4, max: 100)'},
                               'report_period_gte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'Start date filter in '
                                                                    'YYYY-MM-DD format '
                                                                    '(inclusive)'},
                               'report_period_lte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'End date filter in YYYY-MM-DD '
                                                                    'format (inclusive)'},
                               'report_period_gt': {'type': 'string',
                                                    'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                    'description': 'Start date filter in '
                                                                   'YYYY-MM-DD format (exclusive)'},
                               'report_period_lt': {'type': 'string',
                                                    'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                    'description': 'End date filter in YYYY-MM-DD '
                                                                   'format (exclusive)'},
                               'report_period': {'type': 'string',
                                                 'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                 'description': 'Exact report period date in '
                                                                'YYYY-MM-DD format'},
                               'as_reported': {'type': 'boolean',
                                               'default': False,
                                               'description': 'When true, returns raw as-reported '
                                                              'line items exactly as they appear '
                                                              "in the company's filing, rather "
                                                              'than the standardized fields. Only '
                                                              "supports 'annual' or 'quarterly' "
                                                              "periods (a 'ttm' period is treated "
                                                              "as 'annual')."}},
                'required': ['ticker']}}

GET_INDEX_FUND = {'name': 'fd_get_index_fund',
 'description': "Get an ETF or index fund's holdings and each position's weight (percent of net "
                'assets) for a fund ticker (e.g. SPY), sourced from SEC fund-holdings filings. '
                "Returns the fund's latest filing by default, or the composition as of a past "
                'date. Response includes a fund header (as-of period, total net assets, coverage '
                'counts) and the holdings sorted by weight descending.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The fund ticker symbol (e.g., 'SPY', "
                                                         "'QQQ', 'VTI'). Required."},
                               'as_of': {'type': 'string',
                                         'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                         'description': 'Return the fund composition in effect on '
                                                        'or before this date (YYYY-MM-DD). '
                                                        'Defaults to the latest filing.'},
                               'asset_class': {'type': 'string',
                                               'enum': ['equity', 'bond'],
                                               'description': 'Filter holdings by instrument type. '
                                                              'Omit for all holdings.'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 1000,
                                         'default': 50,
                                         'description': 'Number of holdings to return (default: '
                                                        '50, max: 1000).'},
                               'offset': {'type': 'integer',
                                          'minimum': 0,
                                          'default': 0,
                                          'description': 'Number of holdings to skip, for '
                                                         'pagination (default: 0).'}},
                'required': ['ticker']}}

GET_INSIDER_OWNERSHIP = {'name': 'fd_get_insider_ownership',
 'description': 'Retrieves insider ownership statements for a company: what officers, directors, '
                'and 10% owners actually HOLD (common shares, options, RSUs), sourced from SEC '
                "Form 3 (an insider's initial statement of ownership) and Form 5 (the annual "
                'statement). Complements fd_get_insider_trades, which covers the buys and sells in '
                'between: trades are the events, ownership statements are the state. Positions are '
                'returned as reported per filing, newest first.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'name': {'type': 'string',
                                        'description': 'Filter by insider name (case-insensitive '
                                                       "contains, e.g. 'cook')."},
                               'form_type': {'type': 'string',
                                             'enum': ['3', '3/A', '5', '5/A'],
                                             'description': 'Filter by SEC form type: 3 for '
                                                            'initial ownership statements (what a '
                                                            'new insider owned on day one), 5 for '
                                                            'annual statements, or their '
                                                            'amendments.'},
                               'filing_date': {'type': 'string',
                                               'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                               'description': 'Exact filing date filter in '
                                                              'YYYY-MM-DD format'},
                               'filing_date_gte': {'type': 'string',
                                                   'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                   'description': 'Filing date greater than or '
                                                                  'equal to (YYYY-MM-DD)'},
                               'filing_date_lte': {'type': 'string',
                                                   'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                   'description': 'Filing date less than or equal '
                                                                  'to (YYYY-MM-DD)'},
                               'filing_date_gt': {'type': 'string',
                                                  'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                  'description': 'Filing date strictly greater '
                                                                 'than (YYYY-MM-DD)'},
                               'filing_date_lt': {'type': 'string',
                                                  'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                  'description': 'Filing date strictly less than '
                                                                 '(YYYY-MM-DD)'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 1000,
                                         'default': 10,
                                         'description': 'Number of ownership rows to retrieve '
                                                        '(default: 10, max: 1000)'}},
                'required': ['ticker']}}

GET_INSIDER_TRADES = {'name': 'fd_get_insider_trades',
 'description': 'Retrieves insider trading transactions for a company, including purchases, sales, '
                'and other transactions by company officers, directors, and major shareholders. '
                'Useful for tracking insider sentiment and ownership changes.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'name': {'type': 'string',
                                        'description': "Filter by insider name (e.g., 'Timothy D "
                                                       "Cook')."},
                               'filing_date': {'type': 'string',
                                               'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                               'description': 'Exact filing date filter in '
                                                              'YYYY-MM-DD format'},
                               'filing_date_gte': {'type': 'string',
                                                   'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                   'description': 'Filing date greater than or '
                                                                  'equal to (YYYY-MM-DD)'},
                               'filing_date_lte': {'type': 'string',
                                                   'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                   'description': 'Filing date less than or equal '
                                                                  'to (YYYY-MM-DD)'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 5000,
                                         'default': 100,
                                         'description': 'Number of insider trades to retrieve '
                                                        '(default: 100, max: 5000)'}},
                'required': ['ticker']}}

GET_INSTITUTIONAL_INVESTORS = {'name': 'fd_get_institutional_investors',
 'description': 'Lists institutional investors (SEC 13F filers) with their CIK and most recent '
                'reported name. Optionally filter by case-insensitive name prefix. Use this to '
                'discover the filer_cik to pass to fd_get_institutional_holdings.',
 'parameters': {'type': 'object',
                'properties': {'name': {'type': 'string',
                                        'description': 'Optional case-insensitive name prefix to '
                                                       "filter the filer list (e.g. 'Berkshire'). "
                                                       'Use this tool to discover the filer_cik to '
                                                       'pass to fd_get_institutional_holdings.'}},
                'required': []}}

GET_INSTITUTIONAL_HOLDINGS = {'name': 'fd_get_institutional_holdings',
 'description': 'Retrieves SEC 13F institutional holdings sourced directly from EDGAR. Query by '
                'filer_cik (what positions a filer holds) OR by ticker (which institutional filers '
                'hold this security) — exactly one is required. When no report_period filter is '
                'supplied, returns the latest available quarter for the filer or ticker. '
                'Ticker-mode rows include filer_cik and filer_name per position; filer-mode rows '
                'omit those (the filer is already implied by the query).',
 'parameters': {'type': 'object',
                'properties': {'filer_cik': {'type': 'string',
                                             'description': 'Zero-padded 10-digit SEC CIK of the '
                                                            'institutional filer (e.g. '
                                                            "'0001067983' for Berkshire Hathaway). "
                                                            'Provide exactly one of filer_cik or '
                                                            'ticker. Use '
                                                            'fd_get_institutional_investors to '
                                                            'look up CIKs by name.'},
                               'ticker': {'type': 'string',
                                          'description': 'Stock ticker of the held security (e.g. '
                                                         "'AAPL'). Returns the list of "
                                                         'institutional filers holding that '
                                                         'security. Provide exactly one of '
                                                         'filer_cik or ticker.'},
                               'report_period': {'type': 'string',
                                                 'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                 'description': 'Exact 13F report period '
                                                                '(quarter-end date) in YYYY-MM-DD '
                                                                'format.'},
                               'report_period_gte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'Report period greater than or '
                                                                    'equal to (YYYY-MM-DD).'},
                               'report_period_lte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'Report period less than or '
                                                                    'equal to (YYYY-MM-DD).'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 200,
                                         'default': 10,
                                         'description': 'Number of holdings to return (default: '
                                                        '10, max: 200).'}},
                'required': []}}

GET_INTEREST_RATES = {'name': 'fd_get_interest_rates',
 'description': 'Retrieves the latest policy interest rates from major central banks (e.g., FED, '
                "ECB, BOE, BOJ). Returns a snapshot of each bank's current rate — no parameters "
                "required. Prefer fd_get_macro_data with dataset='interest_rates', which also "
                'serves rate history.',
 'parameters': {'type': 'object', 'properties': {}, 'required': []}}

GET_KPI_GUIDANCE = {'name': 'fd_get_kpi_guidance',
 'description': 'Retrieves forward-looking KPI guidance items issued by company management in '
                'earnings releases and SEC filings. Filter by ticker, period (quarterly/annual), '
                'metric name, and date range.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'period': {'type': 'string',
                                          'enum': ['quarterly', 'annual'],
                                          'default': 'quarterly',
                                          'description': 'The reporting period (default: '
                                                         "'quarterly')"},
                               'metric_name': {'type': 'string',
                                               'description': 'Optional filter to a specific '
                                                              'guidance metric name (snake_case, '
                                                              "e.g., 'revenue', 'gross_margin', "
                                                              "'operating_expenses'; "
                                                              'case-insensitive)'},
                               'report_period_gte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'Start date filter in '
                                                                    'YYYY-MM-DD format '
                                                                    '(inclusive)'},
                               'report_period_lte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'End date filter in YYYY-MM-DD '
                                                                    'format (inclusive)'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 50,
                                         'default': 4,
                                         'description': 'Number of records to retrieve (default: '
                                                        '4, max: 50)'}},
                'required': ['ticker']}}

GET_KPI_METRICS = {'name': 'fd_get_kpi_metrics',
 'description': 'Retrieves historical KPI taxonomy metrics extracted from SEC filings for a '
                'company (e.g., subscriber counts, ARPU, units sold). Filter by ticker, period '
                '(quarterly/annual), metric name, and date range.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'period': {'type': 'string',
                                          'enum': ['quarterly', 'annual'],
                                          'default': 'quarterly',
                                          'description': 'The reporting period (default: '
                                                         "'quarterly')"},
                               'metric_name': {'type': 'string',
                                               'description': 'Optional filter to a specific KPI '
                                                              "metric name (e.g., 'iPhone units "
                                                              "sold')"},
                               'report_period_gte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'Start date filter in '
                                                                    'YYYY-MM-DD format '
                                                                    '(inclusive)'},
                               'report_period_lte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'End date filter in YYYY-MM-DD '
                                                                    'format (inclusive)'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 50,
                                         'default': 4,
                                         'description': 'Number of records to retrieve (default: '
                                                        '4, max: 50)'}},
                'required': ['ticker']}}

GET_KPI_NON_GAAP = {'name': 'fd_get_kpi_non_gaap',
 'description': 'Retrieves non-GAAP KPIs reported by a company (e.g., Adjusted EBITDA, Free Cash '
                'Flow as defined by the company). Filter by ticker, period (quarterly/annual), '
                'metric name, and date range.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'period': {'type': 'string',
                                          'enum': ['quarterly', 'annual'],
                                          'default': 'quarterly',
                                          'description': 'The reporting period (default: '
                                                         "'quarterly')"},
                               'metric_name': {'type': 'string',
                                               'description': 'Optional filter to a specific '
                                                              'non-GAAP metric name (e.g., '
                                                              "'Adjusted EBITDA', 'Free Cash "
                                                              "Flow')"},
                               'report_period_gte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'Start date filter in '
                                                                    'YYYY-MM-DD format '
                                                                    '(inclusive)'},
                               'report_period_lte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'End date filter in YYYY-MM-DD '
                                                                    'format (inclusive)'},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 50,
                                         'default': 4,
                                         'description': 'Number of records to retrieve (default: '
                                                        '4, max: 50)'}},
                'required': ['ticker']}}

GET_MACRO_DATA = {'name': 'fd_get_macro_data',
 'description': "Retrieves macroeconomic datasets. dataset='yield_curve' returns the daily US "
                'Treasury par yield curve: one object per business day with the keys date, '
                '1_month, 1_5_month, 2_month, 3_month, 4_month, 6_month, 1_year, 2_year, 3_year, '
                '5_year, 7_year, 10_year, 20_year, 30_year, values in percent. A tenor is null '
                'when it was not published that day (for example the 30-year from 2002 to 2006); '
                'null is not zero. Omit both dates to get the latest curve as a single object. '
                'Give start_date and/or end_date to get history as an array, newest first (default '
                "window: the trailing year). dataset='interest_rates' returns central bank policy "
                "rates: omit both dates for every major bank's current rate as an array, or give "
                "dates plus a bank code (e.g. bank='FED') for that bank's rate history. "
                "dataset='inflation' returns US CPI: omit both dates for the latest month of all "
                "twelve series, or give dates plus series (e.g. series='cpi_all_sa') for that "
                "series' history. Each row has date (the reference month, first day), value "
                '(index, 1982-84=100), change_1m_pct and change_12m_pct (percent, 1 decimal; null '
                'when the comparison month was not published, e.g. October 2025). The headline '
                'inflation rate is change_12m_pct of cpi_all_nsa. Useful for the 10-year yield, '
                'the 2s10s spread, policy rates, discount rates, and real returns.',
 'parameters': {'type': 'object',
                'properties': {'dataset': {'type': 'string',
                                           'enum': ['yield_curve', 'interest_rates', 'inflation'],
                                           'description': 'Which macro dataset to return. '
                                                          "'yield_curve': the daily US Treasury "
                                                          'par yield curve, one object per '
                                                          'business day with one key per tenor. '
                                                          "'interest_rates': central bank policy "
                                                          "rates. 'inflation': monthly US CPI, "
                                                          'twelve series.'},
                               'start_date': {'type': 'string',
                                              'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                              'description': 'First date in YYYY-MM-DD format '
                                                             '(inclusive). Give a start_date or '
                                                             'end_date to get history; omit both '
                                                             'dates to get the latest values.'},
                               'end_date': {'type': 'string',
                                            'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                            'description': 'Last date in YYYY-MM-DD format '
                                                           '(inclusive, default: today).'},
                               'bank': {'type': 'string',
                                        'description': "Central bank code, e.g. 'FED', 'ECB', "
                                                       "'BOE', 'BOJ'. Required for interest_rates "
                                                       'history (with dates); not used by other '
                                                       'datasets or by the latest-values call.'},
                               'series': {'type': 'string',
                                          'description': "Series id for dataset='inflation': "
                                                         'cpi_all_sa (headline), cpi_core_sa '
                                                         '(core), cpi_food_sa, cpi_energy_sa, '
                                                         'cpi_shelter_sa, '
                                                         'cpi_services_less_energy_sa, each also '
                                                         'as _nsa (not seasonally adjusted). '
                                                         'Required for inflation history (with '
                                                         'dates); optional filter for the latest '
                                                         'values; not used by other datasets.'}},
                'required': ['dataset']}}

GET_NEWS = {'name': 'fd_get_news',
 'description': 'Fetches recent news articles for a specific company or the broad market. Pass a '
                'ticker for company-specific news. Call with no arguments for the latest '
                'market-moving news, covering AI, macro, rates, earnings, geopolitics, war, '
                'energy, crypto, IPOs, housing, and other market-wide topics. Also useful when '
                'trying to explain broad price moves — omit the ticker to check for market-wide '
                'catalysts.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT'). Omit for broad market news."},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 10,
                                         'default': 5,
                                         'description': 'Number of news articles to retrieve '
                                                        '(default: 5, max: 10)'}},
                'required': []}}

GET_SEGMENTED_FINANCIALS = {'name': 'fd_get_segmented_financials',
 'description': 'Retrieves segment breakdowns from all three financial statement types (income '
                'statement, balance sheet, cash flow) in a single call. Returns revenue, operating '
                'income, and depreciation by product/segment; assets, goodwill, and long-lived '
                'assets by segment; and capital expenditure by segment. Essential for '
                'sum-of-the-parts valuation and segment-level analysis.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'period': {'type': 'string',
                                          'enum': ['annual', 'quarterly'],
                                          'default': 'annual',
                                          'description': 'The reporting period (default: '
                                                         "'annual')"},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 100,
                                         'default': 4,
                                         'description': 'Number of periods to retrieve (default: '
                                                        '4, max: 100)'},
                               'report_period_gte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'Start date filter in '
                                                                    'YYYY-MM-DD format '
                                                                    '(inclusive)'},
                               'report_period_lte': {'type': 'string',
                                                     'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                     'description': 'End date filter in YYYY-MM-DD '
                                                                    'format (inclusive)'},
                               'report_period_gt': {'type': 'string',
                                                    'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                    'description': 'Start date filter in '
                                                                   'YYYY-MM-DD format (exclusive)'},
                               'report_period_lt': {'type': 'string',
                                                    'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                    'description': 'End date filter in YYYY-MM-DD '
                                                                   'format (exclusive)'},
                               'report_period': {'type': 'string',
                                                 'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                                 'description': 'Exact report period date in '
                                                                'YYYY-MM-DD format'}},
                'required': ['ticker']}}

GET_STOCK_PRICE = {'name': 'fd_get_stock_price',
 'description': 'Fetches the most recent price snapshot for a specific stock, including the latest '
                'price, trading volume, and other open, high, low, and close price data.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"}},
                'required': ['ticker']}}

GET_STOCK_PRICES = {'name': 'fd_get_stock_prices',
 'description': 'Retrieves historical price data for a stock over a specified date range, '
                'including open, high, low, close prices, and volume.',
 'parameters': {'type': 'object',
                'properties': {'ticker': {'type': 'string',
                                          'description': "The stock ticker symbol (e.g., 'AAPL', "
                                                         "'MSFT', 'TSLA')"},
                               'interval': {'type': 'string',
                                            'enum': ['second',
                                                     'minute',
                                                     'day',
                                                     'week',
                                                     'month',
                                                     'year'],
                                            'default': 'day',
                                            'description': 'The time interval for price data '
                                                           "(default: 'day')"},
                               'interval_multiplier': {'type': 'integer',
                                                       'exclusiveMinimum': 0,
                                                       'default': 1,
                                                       'description': 'Multiplier for the interval '
                                                                      '(default: 1)'},
                               'start_date': {'type': 'string',
                                              'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                              'description': 'Start date in YYYY-MM-DD format '
                                                             '(default: 1 year before end_date)'},
                               'end_date': {'type': 'string',
                                            'pattern': '^\\d{4}-\\d{2}-\\d{2}$',
                                            'description': 'End date in YYYY-MM-DD format '
                                                           '(default: today in Eastern time)'}},
                'required': ['ticker']}}

SCREEN_STOCKS = {'name': 'fd_screen_stocks',
 'description': 'Screens and filters stocks by financial metrics, valuation ratios, and company '
                'attributes. Combine multiple filter conditions to find stocks matching your '
                'investment criteria (e.g., revenue > $1B and P/E ratio < 20). Use '
                'fd_list_stock_screener_filters first to see all available fields and operators.',
 'parameters': {'type': 'object',
                'properties': {'filters': {'type': 'array',
                                           'items': {'type': 'object',
                                                     'properties': {'field': {'type': 'string',
                                                                              'description': 'The '
                                                                                             'financial '
                                                                                             'metric '
                                                                                             'or '
                                                                                             'company '
                                                                                             'attribute '
                                                                                             'to '
                                                                                             'filter '
                                                                                             'on '
                                                                                             '(e.g., '
                                                                                             "'revenue', "
                                                                                             "'net_income', "
                                                                                             "'pe_ratio', "
                                                                                             "'sector', "
                                                                                             "'industry')"},
                                                                    'operator': {'type': 'string',
                                                                                 'enum': ['gt',
                                                                                          'lt',
                                                                                          'gte',
                                                                                          'lte',
                                                                                          'eq',
                                                                                          'in'],
                                                                                 'description': 'The '
                                                                                                'comparison '
                                                                                                'operator. '
                                                                                                'Use '
                                                                                                "'gt', "
                                                                                                "'lt', "
                                                                                                "'gte', "
                                                                                                "'lte', "
                                                                                                "'eq' "
                                                                                                'for '
                                                                                                'numeric '
                                                                                                'fields. '
                                                                                                'Use '
                                                                                                "'eq' "
                                                                                                'or '
                                                                                                "'in' "
                                                                                                'for '
                                                                                                'sector/industry.'},
                                                                    'value': {'anyOf': [{'type': 'number'},
                                                                                        {'type': 'string'},
                                                                                        {'type': 'array',
                                                                                         'items': {'type': ['number',
                                                                                                            'string']}}],
                                                                              'description': 'The '
                                                                                             'value '
                                                                                             'to '
                                                                                             'compare '
                                                                                             'against. '
                                                                                             'Use '
                                                                                             'numbers '
                                                                                             'for '
                                                                                             'financial '
                                                                                             'metrics, '
                                                                                             'strings '
                                                                                             'for '
                                                                                             'sector/industry, '
                                                                                             'or '
                                                                                             'arrays '
                                                                                             'for '
                                                                                             'the '
                                                                                             "'in' "
                                                                                             'operator.'}},
                                                     'required': ['field', 'operator', 'value'],
                                                     'additionalProperties': False},
                                           'minItems': 1,
                                           'description': 'Array of filter conditions. At least '
                                                          'one filter is required. Use '
                                                          'fd_list_stock_screener_filters to see '
                                                          'all available fields and operators.'},
                               'currency': {'type': 'string',
                                            'default': 'USD',
                                            'description': 'The currency for financial data '
                                                           "(default: 'USD')"},
                               'limit': {'type': 'integer',
                                         'exclusiveMinimum': 0,
                                         'maximum': 100,
                                         'default': 10,
                                         'description': 'Maximum number of results to return '
                                                        '(default: 10, max: 100)'}},
                'required': ['filters']}}

LIST_STOCK_SCREENER_FILTERS = {'name': 'fd_list_stock_screener_filters',
 'description': 'Retrieves all available filter fields and operators for the stock screener, '
                'grouped by category (income statement, balance sheet, cash flow statement, '
                'financial metrics, and company attributes like sector and industry). Use this to '
                'discover which fields and operators you can use with the fd_screen_stocks tool.',
 'parameters': {'type': 'object', 'properties': {}, 'required': []}}

ALL_SCHEMAS = [
    GET_BENEFICIAL_OWNERS,
    GET_BENEFICIAL_OWNERSHIP,
    GET_COMPANY_FACTS,
    GET_EARNINGS,
    GET_FILING_ITEMS,
    LIST_FILING_ITEM_TYPES,
    GET_FILINGS,
    GET_FINANCIAL_METRICS,
    GET_FINANCIAL_METRICS_SNAPSHOT,
    GET_BALANCE_SHEET,
    GET_INCOME_STATEMENT,
    GET_CASH_FLOW_STATEMENT,
    GET_INDEX_FUND,
    GET_INSIDER_OWNERSHIP,
    GET_INSIDER_TRADES,
    GET_INSTITUTIONAL_INVESTORS,
    GET_INSTITUTIONAL_HOLDINGS,
    GET_INTEREST_RATES,
    GET_KPI_GUIDANCE,
    GET_KPI_METRICS,
    GET_KPI_NON_GAAP,
    GET_MACRO_DATA,
    GET_NEWS,
    GET_SEGMENTED_FINANCIALS,
    GET_STOCK_PRICE,
    GET_STOCK_PRICES,
    SCREEN_STOCKS,
    LIST_STOCK_SCREENER_FILTERS,
]

BY_NAME = {schema["name"]: schema for schema in ALL_SCHEMAS}
