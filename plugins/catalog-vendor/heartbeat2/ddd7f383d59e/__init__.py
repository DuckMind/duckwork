# Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained.
"""Duckwork loader entry point. Importing this file does no registration work."""


def register(ctx):
    from .heartbeat2.registration import register as register_plugin
    return register_plugin(ctx)
