"""Command-hook bridge for Claude Code, Codex, OpenCode, Pi and peers."""

from __future__ import annotations

import argparse
import http.client
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from spectator.bridge.hooks import map_hook_payload
from spectator.config import DEFAULT_SECRET_PATH

_MAX_STDIN_BYTES = 1_048_576


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Git metadata unavailable")
    return result.stdout.strip()


def _read_secret(path: Path) -> str:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise RuntimeError("host secret permissions must be 0600")
    secret = path.read_bytes()
    if len(secret) != 32:
        raise RuntimeError("host secret must be exactly 32 bytes")
    return secret.hex()


def _send_json(url: str, token: str, method: str, body: dict[str, Any]) -> dict[str, Any]:
    parsed_url = urlsplit(url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise RuntimeError("Spectator bridge URL must use http or https")
    if parsed_url.username or parsed_url.password or parsed_url.fragment:
        raise RuntimeError("Spectator bridge URL must not contain credentials or fragments")

    encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
    target = parsed_url.path or "/"
    if parsed_url.query:
        target = f"{target}?{parsed_url.query}"
    connection_type = (
        http.client.HTTPSConnection
        if parsed_url.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_type(parsed_url.hostname, parsed_url.port, timeout=5)
    try:
        connection.request(
            method,
            target,
            body=encoded,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Content-Length": str(len(encoded)),
            },
        )
        response = connection.getresponse()
        raw = response.read(1_048_577)
        if len(raw) > 1_048_576:
            raise RuntimeError("Spectator bridge response exceeded 1 MiB")
        if not 200 <= response.status < 300:
            detail = raw[:4096].decode("utf-8", errors="replace")
            raise RuntimeError(f"Spectator bridge HTTP {response.status}: {detail}")
    except (OSError, http.client.HTTPException) as exc:
        raise RuntimeError(f"Spectator bridge unavailable: {exc}") from exc
    finally:
        connection.close()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Spectator bridge returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise TypeError("Spectator bridge returned an invalid response")
    return parsed


def _with_occurrence(payload: dict[str, Any]) -> dict[str, Any]:
    """Add a local-only occurrence marker for hook events lacking stable IDs."""
    enriched = dict(payload)
    transcript = payload.get("transcript_path")
    if isinstance(transcript, str) and transcript:
        try:
            metadata = Path(transcript).stat()
            enriched["_spectator_occurrence"] = {
                "size": metadata.st_size,
                "mtime_ns": metadata.st_mtime_ns,
            }
            return enriched
        except OSError:
            pass
    enriched["_spectator_occurrence"] = {"time_ns": time.time_ns(), "pid": os.getpid()}
    return enriched


def forward_hook(
    harness: str,
    payload: dict[str, Any],
    *,
    base_url: str,
    secret_path: Path,
    owner_label: str,
) -> dict[str, int]:
    session_id, cwd_text, events = map_hook_payload(harness, _with_occurrence(payload))
    cwd = Path(cwd_text).expanduser().resolve()
    repository_root = Path(_git(cwd, "rev-parse", "--show-toplevel")).resolve()
    branch = _git(repository_root, "branch", "--show-current")
    head_sha = _git(repository_root, "rev-parse", "HEAD").lower()
    if not branch:
        raise RuntimeError("detached HEAD sessions are not shareable")

    token = _read_secret(Path(secret_path))
    base = base_url.rstrip("/") + "/api/plugins/spectator"
    _send_json(
        base + "/bridge/session",
        token,
        "PUT",
        {
            "session_id": session_id,
            "owner_label": owner_label,
            "harness": harness,
            "repository_root": str(repository_root),
            "branch": branch,
            "head_sha": head_sha,
        },
    )
    if not events:
        return {"accepted": 0, "duplicates": 0, "cursor": 0}
    response = _send_json(
        base + "/bridge/events",
        token,
        "POST",
        {
            "session_id": session_id,
            "events": [
                {
                    "source_id": event.source_id,
                    "type": event.type,
                    "summary": dict(event.summary),
                }
                for event in events
            ],
        },
    )
    return {
        "accepted": int(response.get("accepted", 0)),
        "duplicates": int(response.get("duplicates", 0)),
        "cursor": int(response.get("cursor", 0)),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spectator-hook",
        description="Forward one coding-harness lifecycle hook to Spectator Mode.",
    )
    parser.add_argument("--harness", required=True)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SPECTATOR_BASE_URL", "http://127.0.0.1:8788"),
    )
    parser.add_argument(
        "--secret-path",
        type=Path,
        default=Path(os.environ.get("SPECTATOR_HOST_SECRET", str(DEFAULT_SECRET_PATH))),
    )
    parser.add_argument(
        "--owner-label",
        default=os.environ.get("SPECTATOR_OWNER_LABEL", "Shared session"),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return a non-zero status when forwarding fails",
    )
    parser.add_argument("--report", action="store_true", help="print a small success receipt")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    raw = sys.stdin.buffer.read(_MAX_STDIN_BYTES + 1)
    if len(raw) > _MAX_STDIN_BYTES:
        print("spectator-hook: payload exceeds 1 MiB", file=sys.stderr)
        return 2 if args.strict else 0
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be a JSON object")
        receipt = forward_hook(
            args.harness,
            payload,
            base_url=args.base_url,
            secret_path=args.secret_path,
            owner_label=args.owner_label,
        )
    except Exception as exc:
        print(f"spectator-hook: {exc}", file=sys.stderr)
        return 2 if args.strict else 0
    if args.report:
        print(json.dumps(receipt, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
