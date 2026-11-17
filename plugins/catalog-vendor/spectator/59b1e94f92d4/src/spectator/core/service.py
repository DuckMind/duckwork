"""Harness-neutral application service used by HTTP, desktop and future UIs."""

from __future__ import annotations

from spectator.core.contracts import (
    BranchQueryResult,
    StreamPage,
    SummaryPage,
)
from spectator.core.registry import AdapterRegistry
from spectator.core.summary import project_summary


class SpectatorService:
    def __init__(self, registry: AdapterRegistry) -> None:
        self.registry = registry

    def stream(self, session_id: str, *, after: int = 0, limit: int = 100) -> StreamPage:
        return self.registry.get(session_id).read_events(after=after, limit=limit)

    def summaries(self, session_id: str, *, after: int = 0, limit: int = 100) -> SummaryPage:
        page = self.stream(session_id, after=after, limit=limit)
        entries = tuple(project_summary(session_id, event) for event in page.events)
        return SummaryPage(
            entries=entries,
            cursor=page.cursor,
            reset=page.reset,
            oldest_cursor=page.oldest_cursor,
        )

    def query_code(self, session_id: str, query: str, *, limit: int = 20) -> BranchQueryResult:
        return self.registry.get(session_id).query_branch(query, limit=limit)
