"""Tool schemas — what the LLM sees."""

SOURCE_TRAY_LIST = {
    "name": "source_tray_list",
    "description": (
        "List URLs this Duckwork agent opened in the current session via web_search, "
        "web_extract, or browser_navigate. Use when the user asks for sources, "
        "citations, or 'what did you just read'. Does not search the web itself."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "markdown": {
                "type": "boolean",
                "description": "If true, also include a markdown bullet list.",
                "default": True,
            }
        },
        "required": [],
    },
}

SOURCE_TRAY_CLEAR = {
    "name": "source_tray_clear",
    "description": (
        "Clear the session source tray. Use when the user wants a fresh citation "
        "list for a new topic."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
