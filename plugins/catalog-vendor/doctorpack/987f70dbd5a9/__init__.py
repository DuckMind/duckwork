"""Directory-plugin shim for Duckwork.

This lets the repository work both as:
- a drop-in ~/.duckwork/plugins/doctorpack directory, and
- a pip package exposing duckwork_agent.plugins entry point.
"""

# Choose the import context before importing so internal import failures are
# preserved, even if another copy of duckwork_doctorpack is installed.
if __package__:
    from .duckwork_doctorpack import register
else:  # Direct module loading, including pytest collection of this shim.
    from duckwork_doctorpack import register

__all__ = ["register"]
