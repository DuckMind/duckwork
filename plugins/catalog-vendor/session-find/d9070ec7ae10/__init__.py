"""Session Find has no agent-side capabilities.

The plugin ships one backend route (`dashboard/plugin_api.py`, which answers from
this gateway's own session database and from a session-find service when one is
running) and, in the other half, a Desktop window. This module exists so the
agent plugin loader can import the package without registering anything.
"""


def register(ctx) -> None:  # noqa: ARG001 - intentionally registers nothing
    return None
