"""Tool schemas — what the LLM sees."""

DONE_BELL_STATUS = {
    "name": "done_bell_status",
    "description": (
        "Show Done Bell state: muted or not, whether Duckwork is waiting for "
        "approval, and recent turn-finished events. Does not send chat."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "markdown": {
                "type": "boolean",
                "description": "If true, also include a markdown summary.",
                "default": True,
            },
            "mute": {
                "type": "boolean",
                "description": "If set, mute (true) or unmute (false) the bell.",
            },
        },
        "required": [],
    },
}
