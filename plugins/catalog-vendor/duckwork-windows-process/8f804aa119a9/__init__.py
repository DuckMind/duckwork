"""Duckwork plugin entry point.

Install by cloning this directory into ``~/.duckwork/plugins/duckwork-windows-process``
(or ``duckwork plugins install``), then enable it:

    duckwork plugins enable duckwork-windows-process

The plugin registers one read-only tool, ``win_process_table``, over the Windows process
table. See README.md for the filters and the output shape.
"""


def register(ctx):
    from .duckwork_windows_process import schemas, tools

    ctx.register_tool(
        name="win_process_table",
        toolset="windows_process",
        schema=schemas.PROCESS_TABLE,
        handler=tools.win_process_table,
    )
