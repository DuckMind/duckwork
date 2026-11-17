"""Schemas for the Brave Search Duckwork plugin."""

BRAVE_WEB_SEARCH = {
    "name": "brave_web_search",
    "description": (
        "Search the live web with Brave Search API and return fresh ranked results. "
        "Use this for current facts, recent pages, or when you need search-engine results."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query to send to Brave Search.",
            },
            "count": {
                "type": "integer",
                "description": "Number of results to return. Range 1-20. Default 10.",
                "minimum": 1,
                "maximum": 20,
            },
            "country": {
                "type": "string",
                "description": "Optional country code, e.g. 'us' or 'in'.",
            },
            "search_lang": {
                "type": "string",
                "description": "Optional result language code, e.g. 'en'.",
            },
            "freshness": {
                "type": "string",
                "description": "Optional freshness window supported by Brave, e.g. 'pd', 'pw', 'pm', or 'py'.",
            },
            "safesearch": {
                "type": "string",
                "description": "SafeSearch mode: 'off', 'moderate', or 'strict'. Default 'moderate'.",
                "enum": ["off", "moderate", "strict"],
            },
        },
        "required": ["query"],
    },
}
