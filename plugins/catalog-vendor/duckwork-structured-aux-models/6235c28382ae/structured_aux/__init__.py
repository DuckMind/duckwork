"""Decision-backed auxiliary routing for Duckwork Agent.

See ``README.md`` for the operator setup and the repository's agent instructions for the
Duckwork seams this plugin depends on.
"""

from . import compression, config, contracts, decisions, privacy, shim

__all__ = ["compression", "config", "contracts", "decisions", "privacy", "shim"]
