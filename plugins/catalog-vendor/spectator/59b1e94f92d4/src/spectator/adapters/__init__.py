"""Harness adapter implementations.

The core imports only the adapter protocol. Harness-specific code belongs here.
"""

from spectator.adapters.stored import StoredSessionAdapter

__all__ = ["StoredSessionAdapter"]
