"""session-ref — desktop-only plugin; no agent-side code needed.

The @session reference is intentionally NOT expanded server-side: the agent
resolves the reference with its session-search tool. This module exists so the
package is a valid unified Duckwork plugin (plugin.yaml + desktop/plugin.js);
it registers nothing.
"""


def register(ctx):
    pass