"""OrqueHelx: subagents across subscriptions on Duckwork."""


def register(ctx):
    from .delegate import register as register_plugin
    register_plugin(ctx)
