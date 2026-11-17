"""Closed JSON input schemas for the four Duckwork tools."""
from __future__ import annotations

TOOLSET = "s3"
_PATH = {"type": "string", "minLength": 1}
_RULE = {"type": "string", "minLength": 1}


def _schema(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "additionalProperties": False}


PUSH_SCHEMA = _schema({
    "src": _PATH, "dst": _PATH, "local": _PATH, "remote": _PATH,
    "rule": _RULE, "force": {"type": "boolean", "default": False},
})
PULL_SCHEMA = _schema({
    "src": _PATH, "dst": _PATH, "local": _PATH, "remote": _PATH, "rule": _RULE,
})
LS_SCHEMA = _schema({"prefix": _PATH, "rule": _RULE})
RM_SCHEMA = _schema({
    "key": _PATH, "prefix": _PATH, "rule": _RULE,
    "recursive": {"type": "boolean", "default": False},
    "confirm": {"type": "boolean", "default": False},
})

S3_BACKUP_PUSH_SCHEMA = PUSH_SCHEMA
S3_BACKUP_PULL_SCHEMA = PULL_SCHEMA
S3_BACKUP_LS_SCHEMA = LS_SCHEMA
S3_BACKUP_RM_SCHEMA = RM_SCHEMA
