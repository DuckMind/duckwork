"""YAML-backed named source and destination rules."""
from __future__ import annotations

import string
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALLOWED_TEMPLATES = {"date", "ts", "year", "month", "day"}
VALID_OPERATIONS = {"push", "pull", "ls", "rm"}


def load_rules(path: str | Path) -> dict[str, dict[str, str | None]]:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyYAML is required to use S3 backup rules; install the 'yaml' package"
        ) from exc
    rules_path = Path(path).expanduser()
    try:
        with rules_path.open("r", encoding="utf-8") as stream:
            raw = yaml.safe_load(stream)
    except FileNotFoundError as exc:
        raise RuntimeError(f"S3 backup rules file not found: {rules_path}") from exc
    except OSError as exc:
        raise RuntimeError(f"Unable to read S3 backup rules file: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Unable to parse S3 backup rules file: {exc}") from exc
    if isinstance(raw, dict) and isinstance(raw.get("rules"), dict):
        raw = raw["rules"]
    if not isinstance(raw, dict):
        raise ValueError("S3 backup rules must be a top-level YAML mapping")

    validated: dict[str, dict[str, str | None]] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("S3 backup rule names must be non-empty strings")
        if not isinstance(value, dict):
            raise ValueError(f"S3 backup rule '{name}' must be a mapping")
        prefix = value.get("prefix")
        source = value.get("source")
        if not isinstance(prefix, str) or not prefix:
            raise ValueError(f"S3 backup rule '{name}' requires a string 'prefix'")
        if source is not None and not isinstance(source, str):
            raise ValueError(f"S3 backup rule '{name}' has a non-string 'source'")
        _check_safe(prefix, name, "prefix")
        if source is not None:
            _check_safe(source, name, "source")
        validated[name] = {"prefix": prefix, "source": source}
    return validated


def _check_safe(value: str, rule_name: str, field: str) -> None:
    """Refuse absolute or path-traversal prefixes/sources in rules."""
    if value.startswith("/"):
        raise ValueError(f"S3 backup rule '{rule_name}' {field} must be relative, not absolute")
    if ".." in value.split("/"):
        raise ValueError(f"S3 backup rule '{rule_name}' {field} must not contain '..'")


def _validate_template(value: str, rule_name: str, field: str) -> None:
    try:
        for _, field_name, format_spec, conversion in string.Formatter().parse(value):
            if field_name is None:
                continue
            if field_name not in ALLOWED_TEMPLATES:
                raise ValueError(
                    f"S3 backup rule '{rule_name}' has unknown template '{{{field_name}}}' in {field}"
                )
            if format_spec or conversion:
                raise ValueError(
                    f"S3 backup rule '{rule_name}' uses unsupported formatting in {field}"
                )
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"S3 backup rule '{rule_name}' has an invalid template in {field}: {exc}") from exc


def _render(value: str, now: datetime) -> str:
    now = (now if now.tzinfo else now.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    values = {
        "date": now.strftime("%Y-%m-%d"),
        "ts": now.isoformat(),
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
    }
    try:
        return value.format_map(values)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"Unable to render S3 backup rule template: {exc}") from exc


def resolve(
    name: str | dict[str, Any],
    op: str,
    path: str | Path | None = None,
    now: datetime | None = None,
) -> dict[str, str | None]:
    # Accept the older internal ``resolve(loaded_rules, name, op)`` shape as
    # a compatibility seam; normal callers use resolve(name, op, path, now).
    if isinstance(name, dict):
        loaded = name
        actual_name = op
        actual_op = path
        if not isinstance(actual_op, str):
            raise ValueError("S3 backup rule operation is required")
        name = actual_name
        op = actual_op
        path = None
    else:
        loaded = None
    if op not in VALID_OPERATIONS:
        raise ValueError(f"Unsupported S3 backup rule operation: {op}")
    if not isinstance(name, str) or not name:
        raise ValueError("S3 backup rule name must be a non-empty string")
    if path is None:
        from config import load_config

        path = load_config().rules_path
    rules = loaded if loaded is not None else load_rules(path)
    if name not in rules:
        raise KeyError(f"S3 backup rule not found: {name}")
    rule = rules[name]
    timestamp = now or datetime.now(timezone.utc)
    source = rule["source"]
    return {
        "local": os.path.expanduser(_render(source, timestamp)) if source is not None else None,
        "remote": _render(rule["prefix"], timestamp),
    }
