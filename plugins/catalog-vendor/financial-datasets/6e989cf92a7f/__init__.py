"""Financial Datasets plugin for Duckwork Agent.

Registers one tool per Financial Datasets API dataset: company financials,
stock prices, SEC filings, insider and institutional ownership, KPIs, news,
macro data, and a stock screener. Every tool is read-only.
"""

from . import client, schemas, tools


def register(ctx):
    """Register every schema with its handler under the `financial_datasets` toolset."""
    for schema in schemas.ALL_SCHEMAS:
        ctx.register_tool(
            name=schema["name"],
            toolset="financial_datasets",
            schema=schema,
            handler=tools.HANDLERS[schema["name"]],
            requires_env=[client.API_KEY_ENV],
            emoji="📈",
        )
