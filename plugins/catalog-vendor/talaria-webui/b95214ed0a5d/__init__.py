"""Optional Duckwork plugin. Runs inside Duckwork, independently of Talaria's server."""

from .bridge import register

__all__ = ["register"]
