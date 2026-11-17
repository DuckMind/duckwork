"""Tool schemas — what the LLM sees."""

FILE_TRAY_LIST = {
    "name": "file_tray_list",
    "description": (
        "List file paths this Duckwork agent touched in the current session via "
        "read_file, write_file, or patch. Use when the user asks which files "
        "were opened or edited. Does not read or write files itself."
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

FILE_TRAY_CLEAR = {
    "name": "file_tray_clear",
    "description": (
        "Clear the session file tray. Use when the user wants a fresh path "
        "list for a new topic."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
