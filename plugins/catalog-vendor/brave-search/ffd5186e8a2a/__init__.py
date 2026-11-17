"""Brave Search Duckwork plugin."""

from . import schemas, tools


TOOLSET_NAME = "brave-search"


def register(ctx):
    ctx.register_tool(
        name="brave_web_search",
        toolset=TOOLSET_NAME,
        schema=schemas.BRAVE_WEB_SEARCH,
        handler=tools.brave_web_search,
        check_fn=tools.check_brave_api_key,
        requires_env=["BRAVE_API_KEY"],
        description="Search the web with Brave Search API.",
        emoji="🦁",
    )
