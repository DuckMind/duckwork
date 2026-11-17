"""WSL Containers (``wslc``) terminal backend for Duckwork Agent.

Deliberately import-free: :mod:`duckwork_wslc_sandbox.wslc` is pure stdlib and is unit-tested
without a Duckwork checkout, while :mod:`duckwork_wslc_sandbox.provider` and
:mod:`duckwork_wslc_sandbox.environment` import Duckwork and are only loadable inside a running
Duckwork. Importing them here would make the stdlib layer untestable on its own.
"""
