"""Directory-plugin entry point for Duckwork Agent."""

try:
    from .duckwork_deepgram_voice import register
except ImportError:  # Loaded directly by test/build tooling rather than Duckwork.
    from duckwork_deepgram_voice import register

__all__ = ["register"]
