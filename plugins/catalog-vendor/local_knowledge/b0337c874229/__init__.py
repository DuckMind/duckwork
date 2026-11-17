"""Duckwork plugin entry point for local_knowledge."""

if __package__:  # Duckwork loads plugin roots as package modules.
    from .duckwork_local_knowledge.plugin import register
else:  # Pytest may import this file as a top-level module.
    from duckwork_local_knowledge.plugin import register

__all__ = ["register"]
