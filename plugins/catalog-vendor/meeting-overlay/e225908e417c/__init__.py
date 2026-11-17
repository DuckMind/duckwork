"""meeting-overlay — native desktop pane for the meeting-mode copilot."""


def register(ctx):
    """No-op — the plugin is a desktop pane, not an agent-extension plugin.

    The catalog's capability probe imports this module and calls ``register(ctx)``;
    meeting-overlay registers no tools/hooks/middleware. Its surface is the desktop
    pane plus the FastAPI router in ``dashboard/plugin_api.py``.
    """