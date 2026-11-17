"""Component B — the Duckwork opponent controller.

Turns one seat's observation into one validated action via a real, isolated Duckwork
`AIAgent` (zero tools, no memory, no context files, no persistence). See
`docs/CONTRACT.md` (## Duckwork agent runtime (verified)) for the verified API
surface this module relies on, and `docs/ARCHITECTURE.md` §4 for the spec.

Public surface: `DuckworkSeatRunner`, `FakeSeatRunner`, `DecisionRequest`,
`DecisionResult`, `SeatAgentConfig`, `models.list_options`/`models.resolve`.
"""

from .types import Action, DecisionRequest, DecisionResult, SeatAgentConfig
from .fake import FakeSeatRunner
from .runner import DuckworkSeatRunner

__all__ = [
    "Action",
    "DecisionRequest",
    "DecisionResult",
    "SeatAgentConfig",
    "FakeSeatRunner",
    "DuckworkSeatRunner",
]
