# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""duckwork-vcc-engine: a Duckwork context engine that compacts without calling a model.

Enable with ``context.engine: vcc`` in config.yaml. See README.md.
"""

__version__ = "0.4.1"


def register(ctx) -> None:
    # Imported here so loading the package stays cheap and side-effect free.
    from .vcc.engine import VccEngine

    ctx.register_context_engine(VccEngine())
