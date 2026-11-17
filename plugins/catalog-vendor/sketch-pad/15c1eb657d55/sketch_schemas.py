"""Tool schemas — what the LLM sees."""

SKETCH_PAD_LAST = {
    "name": "sketch_pad_last",
    "description": (
        "Return the filesystem path of the last Sketch Pad drawing. The PNG "
        "is under DUCKWORK_HOME/images (vision-readable). Prefer the image "
        "already attached to the user message. If you must look again, call "
        "vision_analyze with image_url set to this path. Never start an HTTP "
        "server and never fetch localhost."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
