"""Duckwork directory-plugin entry point.

Duckwork loads a Git-installed plugin directly from the repository root.  Keep
this shim relative so it always uses the scanner shipped in the same checkout
instead of an unrelated globally installed package.
"""

if __package__:
    from .src.duckwork_plugin_guard.duckwork_plugin import register
else:  # Imported directly by repository tooling such as pytest collection.
    from duckwork_plugin_guard.duckwork_plugin import register

__all__ = ["register"]
