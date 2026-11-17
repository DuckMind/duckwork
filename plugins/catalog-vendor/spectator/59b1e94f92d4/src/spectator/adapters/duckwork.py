"""Duckwork-native metadata discovery behind the neutral adapter contract."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from spectator.adapters.native_host import native_context_configured
from spectator.core.contracts import (
    CAP_SUGGESTION_INJECTION,
    REQUIRED_VIEW_CAPABILITIES,
    SessionDescriptor,
)


def _git(repository_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def discover_duckwork_descriptor(state_db_path: Path, session_id: str) -> SessionDescriptor | None:
    """Resolve one Duckwork session without importing Duckwork internals.

    Older Duckwork databases may not carry Git metadata. In that case this
    returns ``None`` and the portable bridge remains available.
    """
    if not session_id or not Path(state_db_path).is_file():
        return None
    uri = f"file:{Path(state_db_path)}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=2.0)
        conn.row_factory = sqlite3.Row
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
            required = {"id", "cwd", "git_branch", "git_repo_root"}
            if not required.issubset(columns):
                return None
            has_display_name = "display_name" in columns
            has_profile_name = "profile_name" in columns
            if has_display_name and has_profile_name:
                sql = (
                    "SELECT cwd, git_branch, git_repo_root, display_name, profile_name "
                    "FROM sessions WHERE id = ?"
                )
            elif has_display_name:
                sql = (
                    "SELECT cwd, git_branch, git_repo_root, display_name "
                    "FROM sessions WHERE id = ?"
                )
            elif has_profile_name:
                sql = (
                    "SELECT cwd, git_branch, git_repo_root, profile_name "
                    "FROM sessions WHERE id = ?"
                )
            else:
                sql = "SELECT cwd, git_branch, git_repo_root FROM sessions WHERE id = ?"
            row = conn.execute(sql, (session_id,)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if row is None:
        return None

    repository_root = Path(row["git_repo_root"] or row["cwd"] or "").expanduser().resolve()
    if not repository_root.is_dir():
        return None
    branch = str(row["git_branch"] or "").strip()
    if not branch:
        branch = _git(repository_root, "branch", "--show-current")
    if not branch:
        return None
    head_sha = _git(repository_root, "rev-parse", "--verify", f"refs/heads/{branch}").lower()
    if len(head_sha) != 40:
        return None

    owner_label = ""
    row_keys = set(row.keys())
    for name in ("display_name", "profile_name"):
        if name in row_keys and row[name]:
            owner_label = str(row[name]).strip()
            if owner_label:
                break
    if not owner_label:
        owner_label = "Shared session"

    try:
        capabilities = REQUIRED_VIEW_CAPABILITIES
        if native_context_configured():
            capabilities = (*capabilities, CAP_SUGGESTION_INJECTION)
        return SessionDescriptor(
            session_id=session_id,
            owner_label=owner_label,
            harness="duckwork",
            repository_root=repository_root,
            branch=branch,
            head_sha=head_sha,
            capabilities=capabilities,
        )
    except ValueError:
        return None
