"""FeedEngine package — structured event summaries and privacy masking."""

from spectator.feed.engine import (
    MAX_SUMMARY_CHARS,
    FeedEngine,
    MessageSummary,
    StatusChangeSummary,
    ToolCallSummary,
    ToolResultSummary,
    mask_summary,
    privacy_mask,
)
from spectator.feed.poller import TranscriptPoller

__all__ = [
    "MAX_SUMMARY_CHARS",
    "FeedEngine",
    "MessageSummary",
    "StatusChangeSummary",
    "ToolCallSummary",
    "ToolResultSummary",
    "TranscriptPoller",
    "mask_summary",
    "privacy_mask",
]