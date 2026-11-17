"""LLMSlim context engine for Duckwork Agent.

The engine ships in the ``llmslim`` package, which Duckwork installs from PyPI as
this plugin's Python dependency. Select it with ``context.engine: llmslim`` in
config.yaml.
"""

from llmslim.integrations.duckwork import LLMSlimContextEngine, register

__all__ = ["LLMSlimContextEngine", "register"]
