"""Tool schemas — what the LLM sees."""

COMMAND_TRAY_LIST = {
    "name": "command_tray_list",
    "description": (
        "List shell commands this Duckwork agent ran in the current session via "
        "the terminal tool (success and failure). Use when the user asks what "
        "commands were run or wants to reuse one. Does not execute commands."
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

COMMAND_TRAY_CLEAR = {
    "name": "command_tray_clear",
    "description": (
        "Clear the session command tray. Use when the user wants a fresh "
        "command list for a new topic."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
