"""Duckwork plugin entry point. Clone this repository into ~/.duckwork/plugins/."""


def register(ctx):
    from .duckwork_cloudflare_sandbox.provider import CloudflareSandboxProvider

    ctx.register_terminal_environment_provider(CloudflareSandboxProvider())
