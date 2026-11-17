"""Stored neutral adapter used by native and portable harness bridges."""

from __future__ import annotations

import json

from spectator.code.query import GitBranchQuery
from spectator.core.contracts import (
    BranchQueryResult,
    EventInput,
    IngestResult,
    SessionDescriptor,
    SessionEvent,
    StreamPage,
)
from spectator.feed.engine import FeedEngine


class StoredSessionAdapter:
    def __init__(self, descriptor: SessionDescriptor, feed: FeedEngine) -> None:
        self._descriptor = descriptor
        self._feed = feed
        self._code = GitBranchQuery(
            descriptor.repository_root,
            descriptor.branch,
            descriptor.head_sha,
        )

    @property
    def descriptor(self) -> SessionDescriptor:
        return self._descriptor

    def read_events(self, *, after: int = 0, limit: int = 100) -> StreamPage:
        result = self._feed.query(since=max(0, after), limit=limit)
        events: list[SessionEvent] = []
        for row in result["events"]:
            try:
                summary = json.loads(row["summary"])
            except (TypeError, json.JSONDecodeError):
                summary = {"note": "[redacted]"}
            if not isinstance(summary, dict):
                summary = {"note": "[redacted]"}
            events.append(
                SessionEvent(
                    cursor=int(row["seq"]),
                    type=str(row["type"]),
                    summary=summary,
                    timestamp=str(row["timestamp"]),
                )
            )
        cursor = events[-1].cursor if events else max(0, after)
        return StreamPage(
            events=tuple(events),
            cursor=cursor,
            reset=bool(result.get("reset")),
            oldest_cursor=result.get("oldest_seq"),
        )

    def current_cursor(self) -> int:
        return self._feed.latest_seq()

    def ingest(self, events: tuple[EventInput, ...]) -> IngestResult:
        accepted = 0
        duplicates = 0
        for event in events:
            _, created = self._feed.append_external(
                source_id=event.source_id,
                event_type=event.type,
                summary=dict(event.summary),
            )
            if created:
                accepted += 1
            else:
                duplicates += 1
        return IngestResult(
            accepted=accepted,
            duplicates=duplicates,
            cursor=self._feed.latest_seq(),
        )

    def query_branch(self, query: str, *, limit: int = 20) -> BranchQueryResult:
        return self._code.query(query, limit=limit)
