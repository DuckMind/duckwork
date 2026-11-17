"""Duckwork entry-point adapter for wheel installations."""

from __future__ import annotations

from typing import Any

from spectator.adapters.native_host import configure_native_context


def register(ctx: Any) -> None:
    configure_native_context(ctx)
