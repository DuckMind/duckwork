"""Auto git sync for worktrees Duckwork touches. Hooks only — no tools."""

from .sync import register

__all__ = ["register"]
