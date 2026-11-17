"""Duckwork plugin entry point.

Install by cloning this repository into ``~/.duckwork/plugins/duckwork-wincred`` (or with
``duckwork plugins install``), then enable the source and map the variables you want:

    duckwork plugins enable duckwork-wincred
    duckwork config set secrets.wincred.enabled true

Credentials themselves are read from the current user's Windows Credential Manager at
startup. See README.md for how to store them.
"""


def register(ctx):
    from .duckwork_wincred.source import WinCredSource

    ctx.register_secret_source(WinCredSource())
