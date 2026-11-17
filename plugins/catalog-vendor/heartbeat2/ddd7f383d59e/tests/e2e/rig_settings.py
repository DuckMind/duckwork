# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Config-only seam, importable without the pinned Duckwork test helpers."""


def replace_plugin_settings(config, settings):
    if settings is not None:
        config['plugins']['entries']['heartbeat2']['settings'] = dict(settings)
    return config
