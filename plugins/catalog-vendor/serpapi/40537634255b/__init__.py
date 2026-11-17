"""Duckwork directory-plugin entry point for Git installations."""

from __future__ import annotations


def register(ctx) -> None:
    """Register the implementation shipped in this checkout."""
    from .src.serpapi_duckwork_plugin import register as register_plugin

    register_plugin(ctx)
