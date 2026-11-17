"""Boto3-backed storage with overwrite and restore-path safety."""
from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

try:
    from .config import Config, load_config
except ImportError:  # top-level import when run as a script (tests)
    from config import Config, load_config


def _make_client(cfg: Config) -> Any:
    try:
        import boto3
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "boto3 is required for S3 backup operations; install the 'boto3' package"
        ) from exc
    cfg.require_storage()
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint,
        region_name=cfg.region,
        aws_access_key_id=cfg.access_key,
        aws_secret_access_key=cfg.secret_key,
    )


def _client_for_bucket(bucket: str, cfg: Config | None = None) -> tuple[Any, Config]:
    if not isinstance(bucket, str) or not bucket:
        raise ValueError("S3 backup bucket must be a non-empty string")
    cfg = cfg or load_config()
    if cfg.bucket != bucket:
        cfg = replace(cfg, bucket=bucket)
    return _make_client(cfg), cfg


def _safe_error(exc: Exception, cfg: Config | None = None) -> dict[str, str]:
    message = str(exc)
    if cfg:
        for secret in (cfg.access_key, cfg.secret_key):
            if secret:
                message = message.replace(secret, "[redacted]")
    return {"type": type(exc).__name__, "message": message or "S3 operation failed"}


def _list_objects(client: Any, bucket: str, prefix: str) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        response = client.list_objects_v2(**kwargs)
        for item in response.get("Contents", []) or []:
            if isinstance(item, dict) and isinstance(item.get("Key"), str):
                objects.append(item)
        if not response.get("IsTruncated"):
            return objects
        next_token = response.get("NextContinuationToken")
        if not next_token or next_token == token:
            raise RuntimeError("S3 listing was truncated without a continuation token")
        token = next_token


def _object_exists(client: Any, bucket: str, key: str) -> bool:
    return any(item.get("Key") == key for item in _list_objects(client, bucket, key))


def _local_files(local: str) -> tuple[Path, list[tuple[Path, str]]]:
    root = Path(local).expanduser()
    if root.is_file():
        return root, [(root, root.name)]
    if not root.is_dir():
        raise FileNotFoundError(f"Local source does not exist or is not a file/directory: {local}")
    files: list[tuple[Path, str]] = []
    for path, _, names in os.walk(root, followlinks=False):
        for name in sorted(names):
            candidate = Path(path) / name
            if candidate.is_file():
                files.append((candidate, candidate.relative_to(root).as_posix()))
    files.sort(key=lambda item: item[1])
    return root, files


def _join_key(prefix: str, relative: str) -> str:
    prefix = prefix.rstrip("/")
    return f"{prefix}/{relative}" if prefix else relative


def push(local: str, remote: str, bucket: str, force: bool = False, cfg: Config | None = None) -> tuple[bool, dict[str, Any]]:
    cfg: Config | None = None
    try:
        if not isinstance(remote, str) or not remote:
            raise ValueError("S3 backup remote destination must be a non-empty string")
        root, files = _local_files(local)
        client, cfg = _client_for_bucket(bucket, cfg)
        is_file = root.is_file()
        report: dict[str, Any] = {"files": 0, "bytes": 0, "skipped": 0, "failed": []}
        for path, relative in files:
            key = remote if is_file else _join_key(remote, relative)
            try:
                if not force and _object_exists(client, bucket, key):
                    report["skipped"] += 1
                    continue
                with path.open("rb") as stream:
                    kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key, "Body": stream}
                    if not force:
                        kwargs["IfNoneMatch"] = "*"
                    try:
                        client.put_object(**kwargs)
                    except Exception:
                        # Some S3-compatible stores reject the conditional, or a
                        # mock client does not expose it. Re-check existence and
                        # never replace a new object before the compatibility call.
                        if not force and _object_exists(client, bucket, key):
                            report["skipped"] += 1
                            continue
                        client.put_object(Bucket=bucket, Key=key, Body=stream)
                report["files"] += 1
                report["bytes"] += path.stat().st_size
            except Exception as exc:
                report["failed"].append({"key": key, "error": _safe_error(exc, cfg)})
        report["ok"] = not report["failed"]
        return report["ok"], report
    except Exception as exc:
        return False, {"error": _safe_error(exc, cfg)}


def _restore_path(target: str, key: str, relative: str) -> Path:
    if os.path.isabs(key) or os.path.isabs(relative):
        raise ValueError(f"Refusing unsafe absolute S3 object key: {key}")
    parts = relative.split("/")
    if any(part in ("..", "") for part in parts):
        raise ValueError(f"Refusing unsafe S3 object key: {key}")
    target_abs = os.path.abspath(Path(target).expanduser())
    target_real = os.path.realpath(target_abs)
    output = os.path.abspath(os.path.join(target_abs, *parts))
    output_real = os.path.realpath(output)
    try:
        contained = os.path.commonpath((target_real, output_real)) == target_real
        parent_contained = os.path.commonpath(
            (target_real, os.path.realpath(os.path.dirname(output)))
        ) == target_real
    except ValueError:
        contained = parent_contained = False
    if not contained or not parent_contained:
        raise ValueError(f"Refusing S3 object key outside restore directory: {key}")
    return Path(output)


def _read_body_to_file(body: Any, destination: Path) -> int:
    written = 0
    with destination.open("wb") as stream:
        if isinstance(body, (bytes, bytearray)):
            stream.write(body)
            return len(body)
        while True:
            chunk = body.read(1024 * 1024)
            if not chunk:
                return written
            stream.write(chunk)
            written += len(chunk)


def pull(remote: str, local: str, bucket: str, cfg: Config | None = None) -> tuple[bool, dict[str, Any]]:
    cfg: Config | None = None
    try:
        if not isinstance(remote, str) or not remote:
            raise ValueError("S3 backup remote source must be a non-empty string")
        client, cfg = _client_for_bucket(bucket, cfg)
        listed = _list_objects(client, bucket, remote)
        exact = any(item.get("Key") == remote for item in listed)
        selected = [item for item in listed if not exact or item.get("Key") == remote]
        prefix = remote.rstrip("/") + "/"
        destinations: list[tuple[dict[str, Any], Path]] = []
        for item in selected:
            key = item["Key"]
            relative = os.path.basename(key) if exact else key[len(prefix) :]
            destinations.append((item, _restore_path(local, key, relative)))
        report: dict[str, Any] = {"files": 0, "bytes": 0}
        for item, destination in destinations:
            destination.parent.mkdir(parents=True, exist_ok=True)
            response = client.get_object(Bucket=bucket, Key=item["Key"])
            report["bytes"] += _read_body_to_file(response["Body"], destination)
            report["files"] += 1
        return True, report
    except Exception as exc:
        return False, {"error": _safe_error(exc, cfg)}


def ls(prefix: str, bucket: str, cfg: Config | None = None) -> tuple[bool, dict[str, Any]]:
    cfg: Config | None = None
    try:
        if not isinstance(prefix, str) or not prefix:
            raise ValueError("S3 backup prefix must be a non-empty string")
        client, cfg = _client_for_bucket(bucket, cfg)
        objects = []
        for item in _list_objects(client, bucket, prefix):
            metadata: dict[str, Any] = {"key": item["Key"]}
            if "Size" in item:
                metadata["size"] = item["Size"]
            if "LastModified" in item:
                value = item["LastModified"]
                metadata["last_modified"] = value.isoformat() if hasattr(value, "isoformat") else str(value)
            objects.append(metadata)
        return True, {"keys": [item["key"] for item in objects], "objects": objects}
    except Exception as exc:
        return False, {"error": _safe_error(exc, cfg)}


def rm(key: str, bucket: str, confirm: bool, recursive: bool = False, cfg: Config | None = None) -> tuple[bool, dict[str, Any]]:
    if not confirm:
        return False, {"error": {"type": "ConfirmationError", "message": "Deletion requires confirm=true"}}
    cfg: Config | None = None
    try:
        if not isinstance(key, str) or not key:
            raise ValueError("S3 backup key or prefix must be a non-empty string")
        client, cfg = _client_for_bucket(bucket, cfg)
        if not recursive:
            matching = _list_objects(client, bucket, key)
            if any(item.get("Key") != key for item in matching):
                return False, {"error": {"type": "SafetyError", "message": "Deleting a prefix requires recursive=true"}}
            client.delete_object(Bucket=bucket, Key=key)
            return True, {"files": 1, "deleted": 1}
        objects = _list_objects(client, bucket, key)
        deleted = 0
        for item in objects:
            client.delete_object(Bucket=bucket, Key=item["Key"])
            deleted += 1
        return True, {"files": deleted, "deleted": deleted}
    except Exception as exc:
        return False, {"error": _safe_error(exc, cfg)}
