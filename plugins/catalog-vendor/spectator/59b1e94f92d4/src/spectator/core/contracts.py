"""Harness-neutral contracts for Spectator sessions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

CAP_LIVE_STREAM = "live_stream"
CAP_SUMMARY_ENTRIES = "summary_entries"
CAP_BRANCH_QUERY = "branch_query"
CAP_SUGGESTION_INJECTION = "suggestion_injection"

REQUIRED_VIEW_CAPABILITIES = (
    CAP_LIVE_STREAM,
    CAP_SUMMARY_ENTRIES,
    CAP_BRANCH_QUERY,
)

KNOWN_HARNESSES = frozenset(
    {
        "claude-code",
        "codex",
        "duckwork",
        "pi",
        "opencode",
        "commandcode",
        "generic",
    }
)


class SessionNotFoundError(LookupError):
    """Raised when no adapter owns the requested session."""


class AdapterConflictError(RuntimeError):
    """Raised when two adapters attempt to own one session."""


class BranchQueryError(RuntimeError):
    """Raised when a branch snapshot cannot be queried safely."""


@dataclass(frozen=True, slots=True)
class SessionDescriptor:
    session_id: str
    owner_label: str
    harness: str
    repository_root: Path
    branch: str
    head_sha: str
    capabilities: tuple[str, ...] = REQUIRED_VIEW_CAPABILITIES

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id is required")
        if not self.owner_label.strip():
            raise ValueError("owner_label is required")
        if not self.harness.strip():
            raise ValueError("harness is required")
        if not self.branch.strip():
            raise ValueError("branch is required")
        if len(self.head_sha) != 40 or any(c not in "0123456789abcdefABCDEF" for c in self.head_sha):
            raise ValueError("head_sha must be a full 40-character Git commit")
        root = self.repository_root.expanduser().resolve()
        object.__setattr__(self, "repository_root", root)
        object.__setattr__(self, "harness", self.harness.strip().lower())
        object.__setattr__(self, "capabilities", tuple(dict.fromkeys(self.capabilities)))


@dataclass(frozen=True, slots=True)
class EventInput:
    source_id: str
    type: str
    summary: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class SessionEvent:
    cursor: int
    type: str
    summary: Mapping[str, object]
    timestamp: str


@dataclass(frozen=True, slots=True)
class StreamPage:
    events: tuple[SessionEvent, ...]
    cursor: int
    reset: bool = False
    oldest_cursor: int | None = None


@dataclass(frozen=True, slots=True)
class SummaryEntry:
    entry_id: str
    cursor: int
    title: str
    body: str
    kind: str
    timestamp: str


@dataclass(frozen=True, slots=True)
class SummaryPage:
    entries: tuple[SummaryEntry, ...]
    cursor: int
    reset: bool = False
    oldest_cursor: int | None = None


@dataclass(frozen=True, slots=True)
class CodeMatch:
    path: str
    line: int
    snippet: str


@dataclass(frozen=True, slots=True)
class BranchQueryResult:
    query: str
    branch: str
    head_sha: str
    matches: tuple[CodeMatch, ...] = field(default_factory=tuple)
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class IngestResult:
    accepted: int
    duplicates: int
    cursor: int


@runtime_checkable
class SessionAdapter(Protocol):
    """Small contract every harness integration must satisfy."""

    @property
    def descriptor(self) -> SessionDescriptor: ...

    def read_events(self, *, after: int = 0, limit: int = 100) -> StreamPage: ...

    def current_cursor(self) -> int: ...

    def query_branch(self, query: str, *, limit: int = 20) -> BranchQueryResult: ...


@runtime_checkable
class WritableSessionAdapter(SessionAdapter, Protocol):
    """Portable bridge extension for adapters that accept neutral events."""

    def ingest(self, events: tuple[EventInput, ...]) -> IngestResult: ...
