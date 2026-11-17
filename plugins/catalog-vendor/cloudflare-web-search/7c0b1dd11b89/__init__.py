"""Cloudflare Web Search backend for Duckwork Agent."""


def register(ctx):
    from .provider import CloudflareWebSearchProvider

    ctx.register_web_search_provider(CloudflareWebSearchProvider(ctx))
