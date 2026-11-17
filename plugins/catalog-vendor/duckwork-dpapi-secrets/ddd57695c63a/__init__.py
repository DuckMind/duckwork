"""Duckwork plugin entry point.

Install by cloning this repository into ``~/.duckwork/plugins/duckwork-dpapi-secrets`` (or
with ``duckwork plugins install``), create the store, then enable the source and map the
variables you want:

    python -m duckwork_dpapi_secrets set OPENAI_API_KEY
    duckwork plugins enable duckwork-dpapi-secrets
    duckwork config set secrets.dpapi.enabled true

The store is one DPAPI-encrypted blob readable only by the Windows user that wrote it.
See README.md for the config layout.
"""


def register(ctx):
    from .duckwork_dpapi_secrets.source import DpapiSecretsSource

    ctx.register_secret_source(DpapiSecretsSource())
