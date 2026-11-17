"""duckwork-lang-he: Hebrew language pack for Duckwork.

The pack is text-only. ``provides_locales`` in ``plugin.yaml`` makes the plugin
loader register ``locales/`` before this module is touched, so ``register``
does nothing. The file exists only because Desktop's "Install from Git" check
looks for ``__init__.py`` next to ``plugin.yaml`` and rejects manifest-only
language packs (Fordex/duckwork-agent#138118).
"""


def register(ctx):  # noqa: ARG001 - the loader registers locales/ from the manifest
    return None
