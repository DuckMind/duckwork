"""Jina Reader backend for Duckwork' web_search and web_extract tools."""


def register(ctx):
    from .provider import JinaWebSearchProvider

    ctx.register_web_search_provider(JinaWebSearchProvider())
