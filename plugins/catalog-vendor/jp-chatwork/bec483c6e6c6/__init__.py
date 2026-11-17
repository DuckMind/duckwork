"""Chatwork platform plugin for Duckwork Agent.

Kept import-light: Duckwork imports the adapter (and httpx) only when the
gateway, cron or `duckwork send` first asks for the Chatwork platform.
"""


def register(ctx) -> None:
    if __package__:
        from .adapter import register as _register
    else:  # flat import only when loaded as a top-level module (pytest rootdir)
        from adapter import register as _register  # type: ignore
    _register(ctx)


__all__ = ["register"]
