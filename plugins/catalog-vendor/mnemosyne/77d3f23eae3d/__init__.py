"""Duckwork plugin-catalog entry point for Mnemosyne.

This directory is what the Duckwork catalog installs. It carries no
implementation of its own: ``pyproject.toml`` declares the
``mnemosyne-duckwork`` package, which Duckwork installs into its venv and
re-applies after every ``duckwork update`` (duckwork-agent#113851). This module
only re-exports that package's registration hooks so the directory is
loadable and ``plugins/memory`` discovery can find the provider.

``kind: exclusive`` in ``plugin.yaml`` keeps Duckwork from importing this
module eagerly in every process; the memory subsystem imports it only when
``memory.provider`` names ``mnemosyne``.
"""

from mnemosyne_duckwork import register, register_memory_provider  # noqa: F401

__all__ = ["register", "register_memory_provider"]
