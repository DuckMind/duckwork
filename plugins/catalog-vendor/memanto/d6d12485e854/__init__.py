"""Memanto memory-agent provider for the Duckwork agent.

Install the directory plugin with the bundled console script::

    duckwork-memanto-install

Then point Duckwork at it::

    duckwork config set memory.provider memanto
"""

from .provider import MemantoMemoryProvider, register

__all__ = ["MemantoMemoryProvider", "register"]
__version__ = "0.1.1"
