# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Load the bundled Little Canary adapter as a Duckwork directory plugin."""

# Pytest also imports a repository-root __init__.py as a top-level module.
# Duckwork gives this file a namespaced package name; keep both import paths valid.
if __package__:
    from .little_canary.duckwork_agent_plugin import register
else:
    from little_canary.duckwork_agent_plugin import register

__all__ = ["register"]
