"""Agent Analytics Duckwork dashboard plugin.

The dashboard extension is discovered from dashboard/manifest.json. The
standalone plugin entry point is intentionally a no-op so `duckwork plugins
install ... --enable` can manage this dashboard-only plugin cleanly.
"""


def register(ctx):
    """Register no agent tools; dashboard assets are loaded by Duckwork Web."""
    return None
