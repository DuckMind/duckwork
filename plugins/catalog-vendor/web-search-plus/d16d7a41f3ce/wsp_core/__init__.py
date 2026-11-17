"""Web Search Plus engine.

Host-neutral core shared by the Duckwork plugin (this repository's root
``__init__.py``) and other hosts. Modules import each other relatively, so the
package works under any parent name (``duckwork_plugins.<slug>.wsp_core``,
``wsp_core``). Host-specific behaviour (tool registration, setup commands,
result formatting) stays in the host.
"""
