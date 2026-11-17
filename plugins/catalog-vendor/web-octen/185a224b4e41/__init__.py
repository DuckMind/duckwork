"""Octen backend for Duckwork' existing web tools."""


def register(ctx):
    from .provider import OctenWebSearchProvider

    ctx.register_web_search_provider(OctenWebSearchProvider())
