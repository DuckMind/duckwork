"""Client-attribution contract shared by every Duckwork network path."""

from pathlib import Path

from agentchatme_duckwork._version import __version__
from agentchatme_duckwork.client_identity import (
    DUCKWORK_CLIENT_HEADERS,
    duckwork_client_identity,
)


def test_duckwork_identity_name_and_version() -> None:
    identity = duckwork_client_identity()

    assert identity.name == "duckwork"
    assert identity.version == __version__
    assert {
        "X-AgentChat-Client": "duckwork",
        "X-AgentChat-Client-Version": __version__,
    } == DUCKWORK_CLIENT_HEADERS


def test_plugin_manifests_match_release() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in ("plugin.yaml", "agentchatme_duckwork/plugin.yaml"):
        manifest = (root / relative).read_text(encoding="utf-8")
        assert f"version: {__version__}" in manifest
        assert "agentchatme>=1.0.3211,<2" in manifest
