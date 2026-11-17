"""Duckwork plugin entry point.

Install by cloning this repository into ``~/.duckwork/plugins/duckwork-wsl-terminal`` (or with
``duckwork plugins install``), then select the backend:

    duckwork plugins enable duckwork-wsl-terminal
    duckwork config set terminal.backend wsl
"""


def register(ctx):
    from .duckwork_wsl_terminal.provider import WslProvider

    ctx.register_terminal_environment_provider(WslProvider())
