"""Stable Duckwork identity for AgentChat SDK and raw registration traffic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._version import __version__

if TYPE_CHECKING:
    from agentchatme import AgentChatClientIdentity

DUCKWORK_CLIENT_HEADERS: dict[str, str] = {
    "X-AgentChat-Client": "duckwork",
    "X-AgentChat-Client-Version": __version__,
}


def duckwork_client_identity() -> AgentChatClientIdentity:
    """Construct lazily so CLI diagnostics can still report a missing SDK."""
    from agentchatme import AgentChatClientIdentity

    return AgentChatClientIdentity(name="duckwork", version=__version__)
