"""Slim Duckwork directory-plugin entry point.

Duckwork scans only this runtime tree when the repository is installed through
its ``/src`` subdirectory.  The implementation remains in the packaged
``duckwork_plugin_guard`` module.
"""

from .duckwork_plugin_guard.duckwork_plugin import register

__all__ = ["register"]
