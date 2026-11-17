"""Bounded read-only frontend inspection. Never execute or import project code."""
import itertools
import os
from pathlib import Path
import re
import stat
from html.parser import HTMLParser

_EXTENSIONS = {".html", ".htm", ".css", ".scss", ".sass", ".less", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
_EXCLUDED = {"node_modules", "vendor", "dist", "build", "coverage", "out", "target", "bower_components", "__pycache__", "venv", "env", "secrets", "credentials"}
_SECRET = re.compile(r"(?:^|[._-])(?:secrets?|credentials?|tokens?|passwords?|private[-_]?keys?)(?:[._-]|$)", re.I)
_FILE_LIMIT = 512 * 1024
_TOTAL_LIMIT = 8 * 1024 * 1024
_ENTRY_LIMIT = 5000
_DIR_LIMIT = 128
_TOKEN = re.compile(r"(?<![\w-])(--[\w-]+)\s*:\s*([^;{}\n]+)")


def _finding(path, line, rule, evidence, recovery, method="heuristic"):
    return {"path": path, "line": line, "rule": rule, "severity": "advisory", "evidence": evidence[:240], "recovery": recovery, "method": method}


class _HTMLChecks(HTMLParser):
    def __init__(self, path, findings):
        super().__init__(convert_charrefs=True)
        self.path, self.findings = path, findings

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        rule = recovery = None
        if tag == "img" and "alt" not in attrs:
            rule, recovery = "image-alt", "Supply meaningful alt text, or alt=\"\" for a confirmed decorative image."
        if tag == "a" and (attrs.get("href") or "").strip() in ("", "#"):
            rule, recovery = "placeholder-link", "Use a real destination, or a button for a local action; test keyboard and Back behavior."
        if rule:
            self.findings.append(_finding(self.path, self.getpos()[0], rule, self.get_starttag_text(), recovery, "html-parser"))

    handle_startendtag = handle_starttag


def _inspect_text(path, text, tokens, findings):
    for match in _TOKEN.finditer(text):
        tokens.append({"name": match[1], "value": match[2].strip(), "path": path, "line": text.count("\n", 0, match.start()) + 1, "method": "heuristic"})
    if Path(path).suffix.lower() in {".html", ".htm"}:
        _HTMLChecks(path, findings).feed(text)
    else:
        for match in re.finditer(r"<img\b[^>]*>", text, re.I):
            if not re.search(r"\balt\s*=", match[0], re.I):
                findings.append(_finding(path, text.count("\n", 0, match.start()) + 1, "image-alt", match[0], "Verify rendered image semantics; supply meaningful alt or an explicit decorative alternative."))
    for match in re.finditer(r"\boutline\s*:\s*(?:none|0)(?:\s*[;}])", text, re.I):
        findings.append(_finding(path, text.count("\n", 0, match.start()) + 1, "focus-outline", match[0], "Verify an equally visible replacement focus indicator; do not remove focus without one."))


def inspect_project(root, max_files=120):
    """Inspect allowlisted files through no-follow descriptors with explicit budgets."""
    if isinstance(max_files, bool) or not isinstance(max_files, int) or not 1 <= max_files <= 500:
        return {"ok": False, "error": "max_files must be an integer in 1..500"}
    if not isinstance(root, (str, os.PathLike)) or not str(root).strip():
        return {"ok": False, "error": "root must be an existing local directory path"}
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        return {"ok": False, "error": "Safe inspection requires no-follow, directory-relative file access on this platform"}
    path = Path(os.path.abspath(os.fspath(root)))
    inventory, tokens, findings, skipped = [], [], [], []
    entries_seen = directories_seen = bytes_read = 0
    budget_hit = False

    def skip(relative, reason):
        skipped.append({"path": relative, "reason": reason})

    def walk(fd, relative=""):
        nonlocal entries_seen, directories_seen, bytes_read, budget_hit
        if directories_seen >= _DIR_LIMIT:
            budget_hit = True
            skip(relative or ".", "directory budget")
            return
        directories_seen += 1
        try:
            with os.scandir(fd) as scan:
                batch = list(itertools.islice(scan, _ENTRY_LIMIT - entries_seen + 1))
            if len(batch) > _ENTRY_LIMIT - entries_seen:
                batch = batch[:_ENTRY_LIMIT - entries_seen]
                budget_hit = True
                skip(relative or ".", "entry budget")
            entries_seen += len(batch)
            for entry in sorted(batch, key=lambda e: e.name):
                rel = f"{relative}/{entry.name}" if relative else entry.name
                name = entry.name.lower()
                if name.startswith(".") or name in _EXCLUDED or _SECRET.search(name):
                    skip(rel, "hidden, secret, vendor or build path")
                    continue
                try:
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        skip(rel, "symlink")
                    elif stat.S_ISDIR(info.st_mode):
                        child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                        try:
                            walk(child, rel)
                        finally:
                            os.close(child)
                    elif not stat.S_ISREG(info.st_mode):
                        skip(rel, "not a regular file")
                    elif Path(name).suffix not in _EXTENSIONS:
                        skip(rel, "unsupported extension")
                    elif len(inventory) >= max_files:
                        budget_hit = True
                        skip(rel, "file count budget")
                    elif info.st_size > _FILE_LIMIT:
                        skip(rel, "file exceeds 512 KiB")
                    elif bytes_read + info.st_size > _TOTAL_LIMIT:
                        budget_hit = True
                        skip(rel, "total byte budget")
                    else:
                        file_fd = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                        try:
                            actual = os.fstat(file_fd)
                            if not stat.S_ISREG(actual.st_mode) or actual.st_size > _FILE_LIMIT:
                                skip(rel, "file changed or exceeds size budget")
                                continue
                            remaining = min(_FILE_LIMIT, _TOTAL_LIMIT - bytes_read)
                            chunks, size = [], 0
                            while size <= remaining:
                                chunk = os.read(file_fd, min(65536, remaining + 1 - size))
                                if not chunk:
                                    break
                                chunks.append(chunk)
                                size += len(chunk)
                            data = b"".join(chunks)
                        finally:
                            os.close(file_fd)
                        if len(data) > remaining:
                            budget_hit = True
                            skip(rel, "file grew beyond byte budget")
                            continue
                        bytes_read += len(data)
                        if b"\0" in data:
                            skip(rel, "binary content")
                            continue
                        try:
                            text = data.decode("utf-8")
                        except UnicodeDecodeError:
                            skip(rel, "unsupported encoding; requires UTF-8")
                            continue
                        inventory.append({"path": rel, "bytes": len(data), "extension": Path(name).suffix})
                        _inspect_text(rel, text, tokens, findings)
                except OSError as exc:
                    skip(rel, f"unreadable or changed: {type(exc).__name__}")
        except OSError as exc:
            skip(relative or ".", f"directory unavailable: {type(exc).__name__}")

    # Open every ancestor without following symlinks, including a raced root component.
    fd = None
    try:
        fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        for component in path.parts[1:]:
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        walk(fd)
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": f"root must be readable and contain no symlink components ({type(exc).__name__})"}
    finally:
        if fd is not None:
            os.close(fd)
    return {"ok": True, "inventory": inventory, "tokens": tokens, "findings": findings, "skipped": skipped,
            "coverage": {"partial": bool(skipped) or budget_hit, "budget_hit": budget_hit,
                         "entries_seen": entries_seen, "directories_seen": directories_seen, "bytes_read": bytes_read,
                         "files_read": len(inventory), "max_files": max_files,
                         "limits": {"file_bytes": _FILE_LIMIT, "total_bytes": _TOTAL_LIMIT, "entries": _ENTRY_LIMIT, "directories": _DIR_LIMIT},
                         "limitations": ["Static advisory checks only; no project code, routes or styles are executed.", "JSX/TSX, framework markup and CSS tokens are heuristic; comments and strings may match.", "No cascade, visual quality, computed contrast, task success or WCAG conformance is established.", "Only allowlisted UTF-8 frontend files are inspected; exclusions and budget truncation are not a clean pass."]}}
