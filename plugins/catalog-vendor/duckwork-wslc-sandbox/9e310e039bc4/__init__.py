"""Duckwork plugin entry point.

Install by cloning this repository into ``~/.duckwork/plugins/duckwork-wslc-sandbox`` (or with
``duckwork plugins install``), then select the backend:

    duckwork plugins enable duckwork-wslc-sandbox
    duckwork config set terminal.backend wslc
"""


def register(ctx):
    from .duckwork_wslc_sandbox.provider import WslcProvider

    ctx.register_terminal_environment_provider(WslcProvider())
