"""Directory-plugin entry point for Duckwork Agent."""

try:
    from .duckwork_speechify import register
except ImportError:  # imported directly by tests or build tools, not by Duckwork
    from duckwork_speechify import register

__all__ = ["register"]
