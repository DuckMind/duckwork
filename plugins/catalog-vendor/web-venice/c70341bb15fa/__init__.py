from .provider import VeniceWebSearchProvider


def register(ctx) -> None:
    """Plugin entry point — registers Venice as a web search/extract backend."""
    ctx.register_web_search_provider(VeniceWebSearchProvider())
