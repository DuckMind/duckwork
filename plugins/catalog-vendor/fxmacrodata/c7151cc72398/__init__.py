"""Native Duckwork directory-plugin entry point."""


def register(ctx):
    from .duckwork_fxmacrodata import register as register_plugin

    return register_plugin(ctx)


__all__ = ["register"]
