"""JSON-returning Duckwork tool handlers for S3 backup operations."""
from __future__ import annotations

import importlib.util
import json
import os
from typing import Any

try:
    from . import config, rules, storage
except ImportError:  # top-level import when run as a script (tests)
    import config
    import rules
    import storage

TOOLSET = "s3"


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _error(operation: str, exc: Exception | str) -> str:
    detail = (
        {"type": type(exc).__name__, "message": str(exc)}
        if isinstance(exc, Exception)
        else {"type": "OperationError", "message": exc}
    )
    return _json({"ok": False, "operation": operation, "error": detail})


def _storage_result(operation: str, result: tuple[bool, dict[str, Any]]) -> str:
    ok, payload = result
    if ok:
        return _json({"ok": True, "operation": operation, **payload})
    return _json({
        "ok": False,
        "operation": operation,
        "error": payload.get("error", {"type": "OperationError", "message": "operation failed"}),
    })


def _rule_values(args: dict[str, Any], operation: str) -> dict[str, str | None]:
    name = args.get("rule")
    if not name:
        return {"local": None, "remote": None}
    return rules.resolve(name, operation, config.load_config().rules_path)


def _first(args: dict[str, Any], *names: str) -> Any:
    for name in names:
        if args.get(name) is not None:
            return args[name]
    return None


def handle_push(args: dict, **kwargs) -> str:
    try:
        values = _rule_values(args, "push")
        local = _first(args, "src", "local") or values["local"]
        remote = _first(args, "dst", "remote") or values["remote"]
        if not local or not remote:
            raise ValueError("push requires a local source and remote destination, or a rule supplying both")
        bucket = config.load_config().bucket
        if not bucket:
            raise RuntimeError("S3_BACKUP_BUCKET is required for S3 backup operations")
        return _storage_result("push", storage.push(local, remote, bucket, bool(args.get("force", False))))
    except Exception as exc:
        return _error("push", exc)


def handle_pull(args: dict, **kwargs) -> str:
    try:
        values = _rule_values(args, "pull")
        remote = _first(args, "src", "remote") or values["remote"]
        local = _first(args, "dst", "local") or values["local"]
        if not remote or not local:
            raise ValueError("pull requires a remote source and local destination, or a rule supplying both")
        bucket = config.load_config().bucket
        if not bucket:
            raise RuntimeError("S3_BACKUP_BUCKET is required for S3 backup operations")
        return _storage_result("pull", storage.pull(remote, local, bucket))
    except Exception as exc:
        return _error("pull", exc)


def handle_ls(args: dict, **kwargs) -> str:
    try:
        values = _rule_values(args, "ls")
        prefix = args.get("prefix") or values["remote"]
        if not prefix:
            raise ValueError("ls requires a prefix or a rule supplying one")
        bucket = config.load_config().bucket
        if not bucket:
            raise RuntimeError("S3_BACKUP_BUCKET is required for S3 backup operations")
        return _storage_result("ls", storage.ls(prefix, bucket))
    except Exception as exc:
        return _error("ls", exc)


def handle_rm(args: dict, **kwargs) -> str:
    try:
        values = _rule_values(args, "rm")
        key = args.get("key")
        prefix = args.get("prefix")
        if key and prefix:
            raise ValueError("rm accepts exactly one of key or prefix")
        if not key and not prefix:
            prefix = values["remote"]
        if not key and not prefix:
            raise ValueError("rm requires a key, prefix, or rule supplying one")
        if not args.get("confirm", False):
            return _error("rm", "Deletion requires confirm=true")
        recursive = bool(args.get("recursive", False))
        if prefix and not recursive:
            return _error("rm", "Deleting a prefix requires recursive=true")
        bucket = config.load_config().bucket
        if not bucket:
            raise RuntimeError("S3_BACKUP_BUCKET is required for S3 backup operations")
        return _storage_result("rm", storage.rm(key or prefix, bucket, True, recursive))
    except Exception as exc:
        return _error("rm", exc)


def available() -> bool:
    try:
        return importlib.util.find_spec("boto3") is not None and bool(os.environ.get("S3_BACKUP_BUCKET"))
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


HANDLERS = {
    "s3_backup_push": handle_push,
    "s3_backup_pull": handle_pull,
    "s3_backup_ls": handle_ls,
    "s3_backup_rm": handle_rm,
    "s3-push": handle_push,
    "s3-pull": handle_pull,
    "s3-ls": handle_ls,
    "s3-rm": handle_rm,
}
