"""Set or remove ONE key in the ``.env`` of ``DUCKWORK_HOME`` through Duckwork's own writer.

Run as ``python env_set.py KEY VALUE`` or ``python env_set.py KEY --remove`` with ``DUCKWORK_HOME`` pointing at the
store. Using ``duckwork_cli.config`` keeps quoting, BOM handling, atomic replace and file mode identical to what
``duckwork config`` would do; nothing is printed.
"""
import sys

from compat import set_env

key, value = sys.argv[1], sys.argv[2]
set_env(key, value)
