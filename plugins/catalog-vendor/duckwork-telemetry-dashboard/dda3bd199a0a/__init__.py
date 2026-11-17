"""Duckwork Telemetry Dashboard — standalone dashboard plugin.

The dashboard extension is discovered from dashboard/manifest.json. The
standalone plugin entry point is intentionally a no-op so `duckwork plugins
install ... --enable` can manage this dashboard-only plugin cleanly.
"""


def register(ctx):
    """Register no agent tools; the dashboard tab is loaded by the Duckwork dashboard."""
    return None
