# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""lumberroom as Duckwork Agent's memory provider.

Duckwork picks this directory out by the text register_memory_provider in this file, before it
imports anything, so the call below has to stay spelled out here.
"""


def __getattr__(name: str):
    # Lazy, so importing this file carries no relative import: pytest imports the repository root's
    # __init__.py on its own, with no parent package, and a module-level one fails there.
    if name == "__version__":
        from ._version import __version__
        return __version__
    raise AttributeError(name)


def register(ctx) -> None:
    # Imported here so `import lumberroom_duckwork` stays cheap for the entry-point scan.
    from .provider import LumberroomProvider

    ctx.register_memory_provider(LumberroomProvider())
