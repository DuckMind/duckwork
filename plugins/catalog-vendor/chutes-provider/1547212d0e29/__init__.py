"""Directory-plugin entry point for the Chutes Duckwork provider."""

from .duckwork_chutes_provider import chutes, register


register()

__all__ = ("chutes", "register")
