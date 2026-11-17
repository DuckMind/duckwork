"""Duckwork loads this directory as a plugin package; register() lives in the importable core."""
try:
    from .duckwork_office.plugin import register
except ImportError:
    from duckwork_office.plugin import register  # type: ignore[no-redef]
