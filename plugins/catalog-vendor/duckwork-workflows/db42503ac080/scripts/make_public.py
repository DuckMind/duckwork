#!/usr/bin/env python3
"""Build a publishable tree from git ls-files, refusing to emit private strings.

Copies every tracked file (via `git -C <repo> ls-files`) EXCEPT:
  - docs/PUBLISH-SCRUB.md            (the audit itself quotes private strings)
  - .git/  __pycache__  tests/home*  *.log
(.github/, .gitignore, examples/ and scripts/.scrub-guards ship: CI runs this
same audit in the public repo and needs the allow-list.)
Then audits the staged copy with the scrub pattern; any hit not allow-listed
in scripts/.scrub-guards (file / file:LINE / regex:PATTERN) exits 1 printing
file:line of every offender. Stdlib only.
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import shutil
import subprocess
import sys
from pathlib import Path

GIT = "/usr/bin/git"
PATTERN = re.compile(r"192\.168|\bhaus\b|callindor|gaidin|rhuidean|jacob|\bfordex\b", re.I)
SCRUB_LIST_FILE = "scripts/scrub-list.txt"


def load_scrub_list(repo: Path) -> re.Pattern:
    """Core-10 contract: the peer-agreed scrub-grep categories (hostnames, LAN IPs,
    Discord snowflakes, estate/internal vocab, model aliases) live in the committed
    scripts/scrub-list.txt (one case-insensitive regex per line; '' and '#' ignored)
    and are MERGED with the built-in pattern above — never replacing it. An absent
    file = built-in only (pre-Core-10 trees keep auditing exactly as before); a line
    that fails to compile is fatal, never silently skipped."""
    pats = [PATTERN.pattern]
    f = repo / SCRUB_LIST_FILE
    if f.exists():
        for raw in f.read_text(encoding="utf-8").splitlines():
            entry = raw.strip()
            if not entry or entry.startswith("#"):
                continue
            try:
                re.compile(entry, re.I)
            except re.error as e:
                print(f"FATAL: {SCRUB_LIST_FILE}:{raw[:60]!r} does not compile: {e}",
                      file=sys.stderr)
                raise SystemExit(2)
            pats.append(entry)
    return re.compile("|".join(f"(?:{p})" for p in pats), re.I)


EXCLUDE_DIRS = {".git", "__pycache__"}
EXCLUDE_PATTERNS = ["docs/PUBLISH-SCRUB.md",
                    "*/__pycache__/*", "__pycache__/*",
                    "tests/home*", "*.log", "*/.git", "*/.git/*"]
# Committee wf166 + wf166c A1 (P1, twice reopened): the known-text suffix set
# must cover every text shape the repo actually ships. A NUL-prepend must not
# buy immunity for a known suffix, and a shipped text extension missing from
# this set is a whole-file blind spot — .yml (the shipped .github/workflows/
# ci.yml) and .txt (mac-source.txt) both exported forbidden lines with "0 scrub
# hits" under the old set. New text file types join here, never the skip path.
AUDIT_SUFFIXES = {".py", ".js", ".mjs", ".md", ".json", ".yaml", ".yml", ".txt", ".sig"}


def excluded(rel: str) -> bool:
    parts = Path(rel).parts
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    return any(fnmatch.fnmatch(rel, pat) for pat in EXCLUDE_PATTERNS)


def load_guards(repo: Path) -> tuple[set[str], set[str], list[re.Pattern]]:
    files, lines, regexes = set(), set(), []
    text = (repo / "scripts" / ".scrub-guards").read_text(encoding="utf-8")
    for raw in text.splitlines():
        entry = raw.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.startswith("regex:"):
            regexes.append(re.compile(entry[len("regex:"):], re.I))
        elif ":" in entry:
            files_part, line_no = entry.rsplit(":", 1)
            lines.add((files_part, int(line_no)))
        else:
            files.add(entry)
    return files, lines, regexes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="destination directory for the publishable tree")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    target = Path(args.target).resolve()
    if target.exists() and any(target.iterdir()):
        print(f"refusing: target exists and is not empty: {target}", file=sys.stderr)
        return 1

    listed = subprocess.run([GIT, "-C", str(repo), "ls-files"],
                            capture_output=True, text=True, check=True).stdout.splitlines()
    copied = [rel for rel in listed if not excluded(rel)]

    # Audit BEFORE copying: a non-guard hit in any copied file is fatal.
    # The audit pattern is the built-in PATTERN MERGED with the committed
    # scripts/scrub-list.txt (Core-10 contract with the peer estate).
    audit = load_scrub_list(repo)
    guard_files, guard_lines, guard_regexes = load_guards(repo)
    offences: list[str] = []
    for rel in copied:
        # The suffix allowlist must never create a blind spot: a shipped
        # extensionless text file (tests/fake-b1 — observed carrying forbidden
        # vocabulary while the audit reported 0 hits) is exactly what the audit
        # exists to catch. Text-ness is decided by content (null-byte sniff,
        # the git heuristic), not by file name.
        p = repo / rel
        raw = p.read_bytes()
        if p.suffix:
            if p.suffix not in AUDIT_SUFFIXES:
                continue
            # Committee wf166 A1 (P1): a known-text suffix must NEVER earn
            # immunity from the null-byte sniff. Prepending one NUL to
            # README.md used to flip the whole file to the binary skip —
            # forbidden lines after the NUL exported green (0 hits) while the
            # exported bytes still decoded and rendered. Known suffixes are
            # ALWAYS audited (errors=replace makes the NUL inert); the sniff
            # skips only the newly-admitted extensionless candidates.
        elif b"\0" in raw[:8192]:
            continue                                   # extensionless binary: nothing to scrub
        text = raw.decode("utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if audit.search(line):
                if rel in guard_files or (rel, i) in guard_lines:
                    continue
                if any(rx.search(line) for rx in guard_regexes):
                    continue
                offences.append(f"{repo / rel}:{i}: {line.strip()[:120]}")
    if offences:
        print("SCRUB FAILED — non-guard private-string hits in copied files:", file=sys.stderr)
        for o in offences:
            print(o, file=sys.stderr)
        return 1

    target.mkdir(parents=True, exist_ok=True)
    for rel in copied:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / rel, dst)
    print(f"OK: {len(copied)} files published to {target} (0 scrub hits)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
