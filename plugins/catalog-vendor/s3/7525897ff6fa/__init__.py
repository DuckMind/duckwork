"""Duckwork plugin entry point for s3.

Thin shim: Duckwork loads ``<plugin-dir>/__init__.py``; the real
logic lives in the :mod:`s3_backup` package, so we re-export
:func:`register` (and :func:`register_cli`, used by the CLI
setup path) from here.
"""

try:
    # Duckwork loads directory plugins as a synthetic package, so use a
    # package-relative import to reach the bundled implementation.
    from .s3_backup import register
    from .s3_backup.cli import register as register_cli
except ImportError:
    # Keep direct imports from a checkout working for scripts and tests.
    from s3_backup import register
    from s3_backup.cli import register as register_cli

__all__ = ["register", "register_cli"]
