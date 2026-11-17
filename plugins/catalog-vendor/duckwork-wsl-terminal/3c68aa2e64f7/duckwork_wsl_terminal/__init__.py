"""WSL distro (``wsl``) terminal backend for Duckwork Agent.

Deliberately import-free: :mod:`duckwork_wsl_terminal.config` and :mod:`duckwork_wsl_terminal.wsl`
are pure stdlib and are unit-tested without a Duckwork checkout, while
:mod:`duckwork_wsl_terminal.provider` and :mod:`duckwork_wsl_terminal.environment` import Duckwork
and are only loadable inside a running Duckwork. Importing them here would make the stdlib
layer untestable on its own.
"""
