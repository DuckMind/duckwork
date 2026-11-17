"""Nextcloud Talk bot adapter for Duckwork (webhook bot mode).

See ``adapter.py`` for the implementation and ``docs/bot-design.md`` for
the design notes. This re-export lets the repo-root dispatcher
(``register(ctx)`` at the repo root) do ``from .bot import adapter`` without
caring about this module's own internals, and lets ``bot/`` be deployed
standalone as its own plugin (copy this directory's contents to
``~/.duckwork/plugins/nctalk_bot/`` if you only want the webhook-bot
connector).
"""

from .adapter import register

__all__ = ["register"]
