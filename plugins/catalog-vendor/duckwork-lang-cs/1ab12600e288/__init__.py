"""Czech (cs) language pack for Duckwork Agent.

The catalogs in ``locales/`` are registered from ``provides_locales`` in ``plugin.yaml`` — this
module registers nothing itself. It exists so that installs that go through a git checkout
(the Desktop "Install from Git" flow) accept a pack whose payload is text-only.
"""


def register(ctx) -> None:  # noqa: ARG001 - manifest-driven pack: nothing to register
    """No-op: the loader picks up locales/ from the manifest."""
