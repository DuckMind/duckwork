"""Safe read-only query of one exact Git commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

from spectator.core.contracts import BranchQueryError, BranchQueryResult, CodeMatch
from spectator.feed.engine import privacy_mask

_EXCLUDED_PATHS = (
    ":(top,exclude,glob)**/.env",
    ":(top,exclude,glob)**/.env.*",
    ":(top,exclude,glob)**/.npmrc",
    ":(top,exclude,glob)**/.pypirc",
    ":(top,exclude,glob)**/.netrc",
    ":(top,exclude,glob)**/.git-credentials",
    ":(top,exclude,glob)**/*.pem",
    ":(top,exclude,glob)**/*.key",
    ":(top,exclude,glob)**/*.p12",
    ":(top,exclude,glob)**/*.pfx",
    ":(top,exclude,glob)**/*.jks",
    ":(top,exclude,glob)**/id_rsa*",
    ":(top,exclude,glob)**/id_ed25519*",
    ":(top,exclude,glob)**/credentials.json",
    ":(top,exclude,glob)**/auth.json",
    ":(top,exclude,glob)**/service-account*.json",
)


class GitBranchQuery:
    """Search committed code without reading untracked or out-of-root files."""

    def __init__(self, repository_root: Path, branch: str, head_sha: str) -> None:
        self.repository_root = Path(repository_root).expanduser().resolve()
        self.branch = branch
        self.head_sha = head_sha.lower()
        self._validate_snapshot()

    def _git(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repository_root), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BranchQueryError(f"Git query unavailable: {exc}") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or "Git command failed"
            raise BranchQueryError(detail)
        return result.stdout.strip()

    def _validate_snapshot(self) -> None:
        if not self.repository_root.is_dir():
            raise BranchQueryError("repository_root is not a directory")
        actual_root = Path(self._git("rev-parse", "--show-toplevel")).resolve()
        if actual_root != self.repository_root:
            raise BranchQueryError("repository_root must be the Git worktree root")
        resolved_head = self._git("rev-parse", "--verify", f"{self.head_sha}^{{commit}}").lower()
        if resolved_head != self.head_sha:
            raise BranchQueryError("head_sha does not resolve to the requested commit")
        resolved_branch = self._git("rev-parse", "--verify", f"refs/heads/{self.branch}").lower()
        if resolved_branch != self.head_sha:
            raise BranchQueryError("branch and head_sha must identify the same snapshot")

    def query(self, query: str, *, limit: int = 20) -> BranchQueryResult:
        query = query.strip()
        if not query:
            raise ValueError("query must not be blank")
        if len(query) > 200:
            raise ValueError("query must be at most 200 characters")
        if any(char in query for char in ("\x00", "\n", "\r")):
            raise ValueError("query must be one line")
        limit = max(1, min(int(limit), 100))

        command = [
            "git",
            "-C",
            str(self.repository_root),
            "grep",
            "-z",
            "-n",
            "-I",
            "-F",
            "-e",
            query,
            self.head_sha,
            "--",
            ":(top,glob)**",
            *_EXCLUDED_PATHS,
        ]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise BranchQueryError(f"Git query unavailable: {exc}") from exc

        matches: list[CodeMatch] = []
        truncated = False
        assert process.stdout is not None
        try:
            while True:
                raw = process.stdout.readline()
                if not raw:
                    break
                parts = raw.rstrip(b"\r\n").split(b"\x00", 2)
                if len(parts) != 3:
                    continue
                raw_path, raw_line, raw_snippet = parts
                path = raw_path.decode("utf-8", errors="replace")
                prefix = f"{self.head_sha}:"
                path = path.removeprefix(prefix)
                try:
                    line = int(raw_line)
                except ValueError:
                    continue
                snippet = privacy_mask(
                    raw_snippet.decode("utf-8", errors="replace").strip()
                )
                if len(matches) >= limit:
                    truncated = True
                    process.terminate()
                    break
                matches.append(CodeMatch(path=path, line=line, snippet=snippet[:500]))
        finally:
            if process.poll() is None:
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)

        stderr = b""
        if process.stderr is not None:
            stderr = process.stderr.read()
        if process.returncode not in (0, 1, -15):
            detail = stderr.decode("utf-8", errors="replace").strip() or "Git grep failed"
            raise BranchQueryError(detail)

        return BranchQueryResult(
            query=query,
            branch=self.branch,
            head_sha=self.head_sha,
            matches=tuple(matches),
            truncated=truncated,
        )
