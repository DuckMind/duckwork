"""Tool schemas — what the LLM sees."""

PROMPT_TRAY_LIST = {
    "name": "prompt_tray_list",
    "description": (
        "List the user's saved Prompt Tray snippets (title + body). Use when "
        "they ask which prompts they saved, or to reuse one. Does not send chat."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "markdown": {
                "type": "boolean",
                "description": "If true, also include a markdown list.",
                "default": True,
            }
        },
        "required": [],
    },
}
