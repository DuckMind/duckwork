"""Tool schemas: what the model reads to decide when and how to call each tool."""

SEARCH_TABLES = {
    "name": "estat_search_tables",
    "description": (
        "Search e-Stat Japan statistics for population or households. "
        "Read-only. Returns matching e-Stat table ids, not the numbers. Use it first for any official "
        "Japanese statistic (population, households, wages, prices). Do not use web_search, web_extract, "
        "the browser, or the terminal instead, or after an error or an empty list. "
        "Write keywords in Japanese. Results are ranked best-first and marked when a table is preliminary "
        "(速報) or uses an older base year. Then call estat_get_data. Which survey to pick is in the "
        "japan-statistics skill. "
        "A census, an establishment census, a consumer price index, and a prefecture population estimate are surveys to name here. "
        "These are government statistics, including economic series such as the unemployment rate and average wages. "
        "Many come from the Statistics Bureau of the Ministry of Internal Affairs and Communications. "
        "A monthly figure may name Tokyo or Osaka. "
        "English survey names include the Population Census, the Labour Force Survey, and the Family Income and Expenditure Survey."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Japanese keywords; all must match (space-separated). OR is allowed: '東京 OR 大阪'. If this search fails or returns no table, do not switch to web_search, web_extract, the browser, or the terminal.",
            },
            "survey": {
                "type": "string",
                "description": "Optional statistic name or code, in Japanese or English: '国勢調査', Population Census, Labour Force Survey, Family Income and Expenditure Survey, '00200521'.",
            },
            "year": {
                "type": "string",
                "description": "Optional survey year or range: '2020', '令和2年', '2020-2023', '202010'. Leave out for price and wage series, which often carry no survey year.",
            },
            "area_level": {
                "type": "string",
                "enum": ["national", "prefecture", "municipality"],
                "description": "Optional: only tables tabulated down to this area level.",
            },
            "limit": {
                "type": "integer",
                "description": "How many tables to return (default 10, max 30).",
            },
        },
        "required": ["query"],
    },
}

TABLE_INFO = {
    "name": "estat_table_info",
    "description": (
        "List Japan e-Stat categories for wages, prices, prefectures. "
        "Read-only. Returns the category names for one e-Stat table. Use it after estat_search_tables "
        "when a name is unclear. Do not look names up with web_search, web_extract, the browser, or the "
        "terminal. "
        "Show the dimensions of one e-Stat table and the names you can use in estat_get_data: areas "
        "(地域), periods (時点), measures (表章項目) and classifications such as 男女 or 産業. Use it after "
        "estat_search_tables when you are not sure which names a table uses, or to find the exact item "
        "among many (pass dimension and search, e.g. dimension='area', search='府中'). Returns a "
        "ready-to-use example call. "
        "A dimension may be a month in a monthly series, or a place such as Tokyo, from the Statistics Bureau."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "table_id": {"type": "string", "description": "The 10-digit table id from estat_search_tables, e.g. '0003445078'."},
            "dimension": {"type": "string", "description": "Optional: list one dimension in full, by key ('area', 'time', 'cat01') or name ('男女')."},
            "search": {"type": "string", "description": "Optional: only items whose name contains this text."},
            "max_items": {"type": "integer", "description": "Items shown per dimension (default 12, or 100 with dimension; max 300)."},
        },
        "required": ["table_id"],
    },
}

GET_DATA = {
    "name": "estat_get_data",
    "description": (
        "Fetch e-Stat numbers for Japan population, wages, or prices. "
        "Read-only. Returns the numbers, unit, and citation for one e-Stat table. Report only numbers "
        "this call returned, and do not add a remembered or approximate figure (約, 万人). Do not use "
        "web_search, web_extract, the browser, or the terminal instead, or after an error or an empty "
        "result. "
        "Ask by name. When you report a number, copy the returned citation and pass on every warning. "
        "Names, ranges, defaults, and CPI items are in the japan-statistics skill. "
        "A monthly series for Tokyo or Osaka may come from the Statistics Bureau, including the Labour Force Survey."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "table_id": {"type": "string", "description": "The 10-digit table id from estat_search_tables."},
            "area": {"type": "string", "description": "Area name(s) or code(s): '東京都' (Tokyo), '大阪府' (Osaka), '札幌市', '東京都,大阪府', 'children:東京都'."},
            "time": {"type": "string", "description": "Period, including a monthly value: '2020年', '令和2年', '2026年8月', 'latest', 'latest:12', '2024年1月~2026年8月'."},
            "filters": {
                "type": "object",
                "description": "Other dimensions by name (or key such as 'cat01') → item name(s), e.g. {\"男女\": \"女\", \"産業分類\": \"建設業\"}.",
                "additionalProperties": {"type": "string"},
            },
            "max_rows": {"type": "integer", "description": "Largest table to return (default 50, max 500). Bigger selections return advice on narrowing instead."},
        },
        "required": ["table_id"],
    },
}

ALL_SCHEMAS = [SEARCH_TABLES, TABLE_INFO, GET_DATA]
BY_NAME = {s["name"]: s for s in ALL_SCHEMAS}
