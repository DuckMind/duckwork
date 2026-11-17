#!/usr/bin/env python3
"""Catalog local scripts and agent skills as ARD entries.

Scans directories (default: ./scripts) for .py/.sh scripts (module
docstrings, argparse flags) and SKILL.md agent skills (YAML frontmatter),
and generates ARD catalog entries so an agent can discover and invoke
local tools through a registry search.

Output: ai-catalog.json (the ARD static manifest format) in the current
directory, or wherever --output points.

Usage:
    python3 -m ard_kit.catalogize
    python3 -m ard_kit.catalogize --dir /path/to/scripts
    ard-catalogize --dir scripts --dir tools --host example.com   # installed

Stdlib only. See README.md for how this plugs into the ARD spec:
https://agenticresourcediscovery.org/
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import sys
import tempfile
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ARD entry type for local CLI tools (media type is free-form per the spec;
# registries route consumers by it)
ENTRY_TYPE = "application/vnd.ard-kit.script+json"

# Slug segments end up inside URLs clients build naively (?identifier=<urn>),
# so keep them in a URL-safe set instead of %-escaping (which parse_qs would
# decode back and break sidecar lookups).
_SLUG_SAFE = re.compile(r"[^A-Za-z0-9._-]")

# Files/dirs to skip
SKIP_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        "node_modules",
        ".venv",
        "venv",
        ".tox",
        ".nox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "site-packages",
        ".cache",
        "vendor",
        "tests",
        ".archive",
    }
)
SKIP_PREFIXES = ("test_", "_test_", "__")
SKIP_SUFFIXES = ("_test.py", "_upgrade_candidate_status.py")


def _shorten(text: str) -> str:
    """Short description = first sentence/line, capped at 120 chars."""
    if not text:
        return ""
    first_line = text.split("\n")[0].strip()
    # ponytail: cut at a real sentence boundary only. An em-dash is an
    # appositive, not a cut point: the station convention "<file>.py — <desc>"
    # puts discovery vocabulary AFTER the em-dash, so cutting there collapsed
    # 307 entries to "<file>.py." (kept the name, dropped the description).
    # ":\n" is dead (first_line has no newline) but harmless; ". " is the one
    # live boundary. Ceiling: naive splitter, won't handle abbrevs/semicolons.
    for sep in (". ", ":\n"):
        idx = first_line.find(sep)
        if 10 < idx < 120:
            first_line = first_line[:idx].strip() + "."
            break
    return first_line[:120]


def _join_block(style: str, block: list[str]) -> str:
    joiner = "\n" if style and style[0] == "|" else " "
    return joiner.join(b for b in block if b).strip()


def _frontmatter(text: str) -> dict[str, str]:
    """Top-level scalar keys from YAML frontmatter.

    Handles single-line scalars, folded/literal blocks (>, |) and indented
    continuations. ponytail: subset YAML — anchors, flow collections, list
    values and multiline quoted scalars need a real parser; not seen in
    skill frontmatter in the wild.
    """
    first, _, rest = text.partition("\n")
    if first.strip() != "---":
        return {}
    end = rest.find("\n---")
    if end == -1:
        return {}
    fm: dict[str, str] = {}
    key: str | None = None
    style = " "
    block: list[str] = []
    for line in rest[:end].split("\n"):
        if (
            line
            and line[0] not in " \t"
            and not line.startswith("#")
            and ":" in line
        ):
            if key is not None:
                fm[key] = _join_block(style, block)
            new_key, _, value = line.partition(":")
            key, value = new_key.strip(), value.strip()
            if value and value[0] in ">|":  # folded/literal block scalar
                style, block = value, []
            else:
                # Quotes come off only as a matching outer pair. A character
                # class tore a lone trailing quote off values like
                # 'profile="urn:air:agent-skills"', and the mangled string
                # went into the catalog, where nothing could match it again.
                if (
                    len(value) >= 2
                    and value[0] == value[-1]
                    and value[0] in "\"'"
                ):
                    value = value[1:-1]
                style, block = " ", [value] if value else []
        elif key is not None and line.strip() and not line.startswith("#"):
            # top-level comments are YAML comments, not block content;
            # indented "#"-lines stay (can't tell content from comment).
            block.append(line.strip())
    if key is not None:
        fm[key] = _join_block(style, block)
    return fm


def _shell_docstring(text: str) -> str:
    """Leading contiguous comment block after the shebang."""
    doc: list[str] = []
    for line in text.split("\n"):
        if line.startswith("#!"):
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            doc.append(stripped.lstrip("#").strip())
        elif stripped:
            break  # first non-comment line ends the header
    return "\n".join(doc).strip()


def _extract_docstring(filepath: Path) -> tuple[str, str]:
    """Extract module docstring and first-paragraph description.

    Returns (full_docstring, short_description) or ("", "") if none.
    """
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", ""

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return "", ""

    docstring = ast.get_docstring(tree) or ""
    return docstring, _shorten(docstring)


def _extract_keywords(docstring: str, filepath: Path) -> list[str]:
    """Extract searchable keywords from docstring and filename."""
    keywords: list[str] = []
    name = filepath.stem

    # From filename: split on underscores
    keywords.extend(w for w in name.replace("-", "_").split("_") if len(w) > 2)

    # From docstring: pick out domain terms (capitalized words, tech terms)
    if docstring:
        # Look for "Usage:", "Notes:", section headers. A header counts only at
        # a line start or after a sentence end: folded YAML blocks join lines
        # with " ", so an unanchored match let the first "release notes: ..."
        # in prose hijack the Notes: capture and tag the sentence tail.
        for pattern in (
            r"(?:^|[.;]\s+)\s*Usage:\s*(.+)",
            r"(?:^|[.;]\s+)\s*Notes:\s*(.+)",
            r"(?:^|[.;]\s+)\s*Design goals:\s*(.+)",
            r"(?:^|[.;]\s+)\s*Summary:\s*(.+)",
        ):
            m = re.search(pattern, docstring, re.MULTILINE | re.IGNORECASE)
            if not m:
                continue
            for word in m.group(1).split():
                # Usage: lines carry example paths, and `scripts/gate.py` or
                # `draft.md` would spend a tag slot on `scripts` and `draft`.
                # An interior dot means a path or an extension; a trailing one
                # is the sentence the header ended with, so `rewrite.` stays.
                if "/" in word or "\\" in word or re.search(r"\.\S", word):
                    continue
                tok = word.strip(",:;()[]<>.")
                if len(tok) > 3:
                    keywords.append(tok)

        # Extract tech terms (words mentioning tools/protocols)
        tech_patterns = [
            r"\b(MCP|REST|API|Docker|SOCKS|proxy|cron|gateway|dashboard|"
            r"telegram|discord|signal|curl|httpx|playwright|selenium|burp|"
            r"nmap|CVE)\b",
        ]
        for pat in tech_patterns:
            matches = re.findall(pat, docstring, re.IGNORECASE)
            keywords.extend(m.lower() for m in matches)

    # Deduplicate, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for k in keywords:
        kl = k.lower()
        if kl not in seen and len(kl) > 2:
            seen.add(kl)
            unique.append(kl)

    return unique[:15]


def interpreter(*, windows: bool | None = None) -> str:
    """The Python command that runs a script on the cataloguing machine.

    Windows installs ship python.exe/py.exe and no python3, so a literal
    "python3" baked into metadata.invoke made most of a catalog dead on
    arrival there. `windows` is a test seam; os.name decides at runtime.
    """
    nt = os.name == "nt" if windows is None else windows
    return "python" if nt else "python3"


def _posix_path_error(flag: str, raw: str, *, nt: bool | None = None) -> str | None:
    """Complaint for a POSIX absolute path in a CLI flag, or None."""
    is_nt = os.name == "nt" if nt is None else nt
    # "//host/share" is UNC and real on win32. A single leading slash is a
    # POSIX root, which pathlib reports as *not* absolute there - so it
    # silently resolves under the system drive instead of failing.
    if not is_nt or not raw.startswith("/") or raw.startswith("//"):
        return None
    unc = "\\\\wsl.localhost\\<distro>" + raw.replace("/", "\\")
    return (
        f"--{flag} {raw!r} is a POSIX path; Windows Python resolves it to "
        f"{os.path.abspath(raw)} instead of failing. Pass a Windows path "
        f"(D:\\project\\...) or, for a file inside WSL, the UNC form {unc} "
        "(wsl -l -q lists distros)."
    )


def guard_posix_paths(flags: dict[str, Any], *, nt: bool | None = None) -> str | None:
    """First POSIX-path complaint across {flag: value | [values]}, or None.

    Every ard-kit CLI takes a path flag and resolves it with pathlib, so the
    Windows trap is shared - and so is the guard. Callers print the result and
    exit non-zero instead of creating a C:\\home\\... tree.
    """
    is_nt = os.name == "nt" if nt is None else nt
    if not is_nt:
        return None
    for flag, value in flags.items():
        for raw in value if isinstance(value, (list, tuple)) else [value]:
            if isinstance(raw, str):
                error = _posix_path_error(flag, raw, nt=True)
                if error:
                    return error
    return None


def _extract_argparse_args(filepath: Path) -> list[dict[str, Any]]:
    """Best-effort CLI argument list from add_argument() calls (static only).

    Feeds the /inspect invoke schema: [{name, kind, help}]. Literal keyword
    args only — variables and concatenations are skipped, so the schema is
    conservative rather than wrong.
    """
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (OSError, SyntaxError):
        return []
    # One option, one row. ast.walk also descends into subparser setup, so a
    # script declaring --config twice used to mint two rows for one flag, and
    # an agent building a command line from the schema passed it twice. First
    # non-empty help wins; insertion order is preserved.
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Attribute)
            or node.func.attr != "add_argument"
        ):
            continue
        names = [
            a.value
            for a in node.args
            if isinstance(a, ast.Constant) and isinstance(a.value, str)
        ]
        if not names:
            continue
        help_text = ""
        for kw in node.keywords:
            if kw.arg == "help" and isinstance(kw.value, ast.Constant):
                help_text = str(kw.value.value)
        name = names[0]
        kind = "positional" if not name.startswith("-") else "option"
        help_text = textwrap.dedent(help_text).strip()[:200]
        prior = rows.get((name, kind))
        if prior is None:
            rows[(name, kind)] = {"name": name, "kind": kind, "help": help_text}
        elif help_text and not prior["help"]:
            prior["help"] = help_text
    return list(rows.values())


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically: unique tmp in the same dir, then os.replace."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def _display_path(path: Path, workspace: Path) -> str:
    """Relative display when possible; absolute --dir may live outside."""
    return str(path.relative_to(workspace)) if path.is_relative_to(workspace) else str(path)


def _should_skip(filepath: Path) -> bool:
    """Return True if file should be excluded from catalog."""
    name = filepath.name
    if name.startswith(SKIP_PREFIXES):
        return True
    if any(name.endswith(suffix) for suffix in SKIP_SUFFIXES):
        return True
    if name == "__init__.py":
        return True
    if filepath.stat().st_size < 100:
        return True
    return False


def _declared_segment(name: str) -> str:
    """Reduce a publisher-declared name to the one segment it actually is.

    The npm .bin/ rule from MR !20, lifted out of the package.json lane
    because it was never a package.json rule: every lane joins a declared
    name onto a path before _make_identifier sees it, so a name carrying a
    separator becomes catalog structure - a server named "team/notes"
    mints urn:air:host:mcp:cfg:team:notes, and "@org/x" mints the same
    smeared _org:x shape !20 fixed for npm. Returns "" for a name that is
    only separators or dots; the caller skips that declaration rather than
    mint "top", a ".." segment, or - for "." - a ValueError out of
    Path.with_suffix that would kill the whole scan.

    "/"-only splitting is deliberate POSIX semantics, not an oversight: on
    POSIX a backslash inside a declared name is an ordinary character, so the
    name stays one honest segment; also splitting on backslash would mint a
    shorter, wrong tail - a new lie replacing the old one. A Windows-separator
    gate, if ever needed, is a separate concern. [F1]
    """
    flat = name.rstrip("/").rsplit("/", 1)[-1]
    return "" if flat in {"", ".", ".."} else flat


def _make_identifier(
    filepath: Path, root: Path, domain: str, namespace: str = "script",
    keep_suffix: bool = False,
) -> str:
    """Generate a stable URN identifier from file path.

    ARD v0.91 Appendix C form: urn:air:<publisher>:<namespace>:<name>.
    keep_suffix keeps the extension (".sh") so foo.py and foo.sh in one
    directory don't collide into one identifier.

    The argument is a path and every part of it becomes a ":" segment, so
    a caller holding a publisher-declared name (a bin key, an mcpServers
    key) must pass it through _declared_segment before joining. The slug
    regex cannot defend that door: it never sees a separator, only the
    parts the path already split into. An absolute declared name is worse
    than smeared - "/etc/passwd" makes relative_to() fail, the fallback
    drops the drive part, and the URN claims a location outside the root.
    """
    try:
        rel = filepath.relative_to(root)
    except ValueError:
        rel = Path(*filepath.parts[1:])  # absolute outside root: drop the drive/root part
    # URL-safe segments so identifiers survive raw query-string interpolation.
    # Empty parts (path == root itself) fall back to a fixed segment.
    slug = ":".join(
        _SLUG_SAFE.sub("_", p) for p in (rel if keep_suffix else rel.with_suffix("")).parts
    ) or "top"
    return f"urn:air:{domain}:{namespace}:{slug}"


def _skipped(filepath: Path) -> bool:
    """Shared scan filter: not a file, excluded dir, or name/size skip."""
    return (
        not filepath.is_file()
        # a symlink inside the scan root must not drag external content
        # (paths/descriptions) into the public catalog
        or filepath.is_symlink()
        # rglob matches directories named like the pattern too.
        or any(part in SKIP_DIRS for part in filepath.parts)
        or _should_skip(filepath)
    )


def _queries(primary: str, extras: list[str], fallback: str) -> list[str]:
    """Build the 2-5 representativeQueries the spec schema wants.

    Lead with the natural description phrase (what an agent actually asks),
    pad with keywords so token search still hits, and split the file or skill
    name when a resource offers nothing else. Returns [] if even that leaves
    a single phrase — the caller then omits the field instead of shipping a
    list the schema rejects.
    """
    name_words = fallback.replace("-", " ").replace("_", " ").replace(".", " ").split()
    out: list[str] = []
    for candidate in [primary, *extras, *name_words]:
        candidate = candidate.strip()
        if candidate and candidate not in out:
            out.append(candidate)
        if len(out) == 5:
            break
    return out if len(out) >= 2 else []


def _script_entry(
    filepath: Path,
    root: Path,
    domain: str,
    short_desc: str,
    keywords: list[str],
    docstring: str,
    interpreter: str,
    keep_suffix: bool = False,
) -> dict[str, Any]:
    """Entry dict shared by .py and .sh scripts."""
    rel = filepath.relative_to(root) if filepath.is_relative_to(root) else filepath
    rq = _queries(short_desc, keywords[:4], filepath.stem)
    return {
        "@context": "https://agenticresourcediscovery.org/context/v1",
        "identifier": _make_identifier(filepath, root, domain, keep_suffix=keep_suffix),
        "displayName": filepath.stem,
        "description": short_desc,
        "type": ENTRY_TYPE,
        # Spec 3.4: exactly one of url/data — keep url, invoke lives in metadata.
        "url": f"file://{filepath}",
        "tags": keywords[:10],
        "aliases": [filepath.stem],
        **({"representativeQueries": rq} if len(rq) >= 2 else {}),
        "metadata": {
            "keywords": ", ".join(keywords),
            # Forward slashes in the path: the catalog is read by agents whose
            # shell may be Git Bash, where a backslash escapes the next
            # character. cmd.exe accepts forward slashes too, so this loses
            # nothing on Windows and stops lying everywhere else.
            "invoke": f"{interpreter} {shlex.quote(rel.as_posix())}",
            "path": str(rel),
            "workspace": str(root),
            "docstring": docstring[:500] if docstring else "",
        },
    }


# pyproject.toml fields readable without a TOML parser: tomllib is 3.11+ and
# the supported floor is 3.10. Values are single-line basic strings, possibly
# followed by a comment - the shape every real manifest uses for these fields.
_TOML_KEY = re.compile(r'^\s*([A-Za-z0-9_.-]+)\s*=\s*"([^"]*)"\s*(?:#.*)?$')


def _toml_tables(text: str) -> dict[str, dict[str, str]]:
    """Single-line string keys grouped by table, from a subset of TOML.

    ponytail: subset TOML, same posture as the frontmatter reader - skip what
    we cannot read instead of guessing. Multi-line, literal and dotted-key
    values are ignored; entry-point tables never use them.
    """
    tables: dict[str, dict[str, str]] = {}
    current = ""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("["):
            # tolerate a trailing comment on the header; an array-of-tables
            # header lands in a junk table nobody looks up
            name, sep, _ = stripped[1:].partition("]")
            if sep:
                current = name.strip()
                tables.setdefault(current, {})
                continue
        m = _TOML_KEY.match(line)
        if m and current:
            tables[current][m.group(1)] = m.group(2)
    return tables


def catalog_project(
    manifest: Path,
    root: Path,
    domain: str = "localhost",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Catalog the console commands declared in a pyproject.toml.

    [project.scripts] is what a packaged repo actually publishes: the names
    that land on PATH and that the README tells people to run. A file scan
    cannot see them - the module behind a command imports as `-m pkg.mod` and
    fails when run by path - and the description, name and version are
    already written down, so nothing has to be authored twice.
    """
    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        # This lane had no guard at all. _toml_tables cannot raise - it is
        # line-based and returns whatever it recognized - so the read is the
        # only failure point here, and OSError is what it raises.
        print(f"ard-catalogize: skipping {manifest}: {exc}", file=sys.stderr)
        return [], {}
    tables = _toml_tables(text)
    commands = tables.get("project.scripts", {})
    if not commands:
        return [], {}
    project = tables.get("project", {})
    dist = project.get("name") or root.name
    summary = _shorten(project.get("description", ""))
    version = project.get("version", "")
    rel = manifest.relative_to(root) if manifest.is_relative_to(root) else manifest

    entries: list[dict[str, Any]] = []
    schemas: dict[str, Any] = {}
    for command, target in sorted(commands.items()):
        # Same guard as the mcp lane: _TOML_KEY's charset admits "." / ".."
        # keys, so a [project.scripts] name is not slug-safe on charset alone.
        command = _declared_segment(command)
        if not command:
            continue
        # Resolve the entry-point module to mine argparse flags. src-layout is
        # as common as a flat package; an unresolvable target simply means no
        # arguments, never a failed scan.
        module = target.partition(":")[0].replace(".", "/")
        source = next(
            (
                p
                for p in (root / f"{module}.py", root / "src" / f"{module}.py")
                if p.is_file() and not p.is_symlink()
            ),
            None,
        )
        docstring, doc_short = _extract_docstring(source) if source else ("", "")
        desc = summary or doc_short or f"{command} command from {dist}."
        keywords = _extract_keywords(docstring or summary, Path(command))
        # keep_suffix: a command named like "ard.mcp" must not lose a segment
        identifier = _make_identifier(
            root / command, root, domain, "cli", keep_suffix=True
        )
        rq = _queries(desc, keywords[:4], command)
        entries.append({
            "@context": "https://agenticresourcediscovery.org/context/v1",
            "identifier": identifier,
            "displayName": command,
            "description": desc,
            "type": ENTRY_TYPE,
            # An installed command has no file of its own: point at the
            # declaration that puts it on PATH.
            "url": f"file://{manifest}",
            "tags": keywords[:10],
            "aliases": [command] if command == dist else [command, dist],
            **({"representativeQueries": rq} if len(rq) >= 2 else {}),
            "metadata": {
                "keywords": ", ".join(keywords),
                "invoke": command,
                "path": str(rel),
                "workspace": str(root),
                "docstring": (docstring or project.get("description", ""))[:500],
                "entryPoint": target,
                "distribution": dist,
                **({"version": version} if version else {}),
            },
        })
        schemas.setdefault(identifier, {
            "invoke": command,
            "description": desc,
            "arguments": _extract_argparse_args(source) if source else [],
        })
    return entries, schemas


def _package_json_entries(
    manifest: Path,
    root: Path,
    domain: str = "localhost",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Catalog the console commands declared in a package.json bin field.

    npm semantics, verified against the live npm CLI on two majors (11.11.0
    and 10.8.2 - the contract is version-stable): bin as a string commands
    the package itself - the command name comes from package ``name`` with
    the ``@scope/`` prefix stripped; as an object, each command is the name
    npm links the key as into ``.bin/``, which is the key with its directory
    part dropped, and a later key wins a basename collision. arguments stay
    empty: a JS CLI has no
    argparse to mine, and pulling flags out of commander/yargs is the same
    scope creep as a subset JSON parser. Declared-but-missing bin files are
    declared, not validated - that is the publisher's problem.
    """
    try:
        data = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError) as exc:
        # Both halves of that line can raise and only one was caught:
        # json.JSONDecodeError is a ValueError subclass, OSError is not. So
        # an unreadable manifest - permissions, or a race with the is_file()
        # gate in main() - left here as a traceback that killed the whole
        # scan, including the scripts already collected, instead of skipping
        # one workspace. Same tuple the .mcp.json lane has caught since it
        # shipped.
        print(f"ard-catalogize: skipping {manifest}: {exc}", file=sys.stderr)
        return [], {}
    if not isinstance(data, dict):
        return [], {}
    name = data.get("name")
    dist = name if isinstance(name, str) and name else root.name
    description = data.get("description", "")
    if not isinstance(description, str):
        description = ""
    summary = _shorten(description)
    version = data.get("version", "")
    if not isinstance(version, str):
        version = ""
    bin_field = data.get("bin")
    if isinstance(bin_field, str) and bin_field:
        # Scope resolution happens here, before any path joining: the
        # command arrives at _make_identifier already unscoped, never
        # cleaned by the slug regex after the fact.
        unscoped = _declared_segment(dist)
        commands = [(unscoped, bin_field)] if unscoped else []
    elif isinstance(bin_field, dict):
        # npm links .bin/<key> only after dropping the directory part of the
        # key, so the key is not the command name. Verified against the live
        # npm CLI (11.11.0 / node 24.14.1): {"@org/tool": ...} installs as
        # `tool`, {"deep/sub/dir": ...} as `dir`, {"trail//": ...} as
        # `trail`, {"@org/": ...} as `@org` (kept, not dropped), and a later
        # key wins a basename collision. Cataloging the raw key instead
        # smeared the scope across two slug segments
        # (urn:air:host:cli:_org:tool) - a URN the conformance regex accepts
        # and no installed command answers to. Sorted, because declaration
        # order is the publisher's whim and the rest of the catalog is
        # deterministic.
        linked: dict[str, str] = {}
        for k, v in bin_field.items():
            if not (isinstance(k, str) and isinstance(v, str) and v):
                continue
            name = _declared_segment(k)
            if name:
                linked[name] = v
        commands = sorted(linked.items())
    else:
        return [], {}
    rel = manifest.relative_to(root) if manifest.is_relative_to(root) else manifest

    entries: list[dict[str, Any]] = []
    schemas: dict[str, Any] = {}
    for command, target in commands:
        desc = summary or f"{command} command from {dist}."
        keywords = _extract_keywords(summary, Path(command))
        # keep_suffix: a command named like "my.tool" must not lose a segment
        identifier = _make_identifier(
            root / command, root, domain, "cli", keep_suffix=True
        )
        rq = _queries(desc, keywords[:4], command)
        entries.append({
            "@context": "https://agenticresourcediscovery.org/context/v1",
            "identifier": identifier,
            "displayName": command,
            "description": desc,
            "type": ENTRY_TYPE,
            # An installed command has no file of its own: point at the
            # declaration that puts it on PATH.
            "url": f"file://{manifest}",
            "tags": keywords[:10],
            # The package name aliases the command only when the package
            # ships exactly one: with several bins, `multi` was an alias of
            # every command it declares, so one alias resolved to four
            # different identifiers.
            "aliases": (
                [command]
                if command == dist or len(commands) > 1
                else [command, dist]
            ),
            **({"representativeQueries": rq} if len(rq) >= 2 else {}),
            "metadata": {
                "keywords": ", ".join(keywords),
                "invoke": command,
                "path": str(rel),
                "workspace": str(root),
                "docstring": description[:500],
                "entryPoint": target,
                "distribution": dist,
                **({"version": version} if version else {}),
            },
        })
        schemas.setdefault(identifier, {
            "invoke": command,
            "description": desc,
            # No argparse to mine in JS; an empty argument list is a legal
            # schema (same shape as an unresolvable pyproject entry point).
            "arguments": [],
        })
    return entries, schemas


# A card carries only what a manifest holds: the server's name and its
# transport. The prose saying what the server DOES is declared beside the
# manifest, never inside it - .mcp.json is written by hosts and may carry
# secrets in env, the sidecar is a file this package owns the shape of.
_MCP_PROSE_SUFFIX = ".ard.json"


def _mcp_prose(filepath: Path) -> dict[str, Any]:
    """Declared card prose from <manifest>.ard.json: {server: {description,...}}.

    Fail-soft like every reader here - a missing, unreadable or misshapen
    sidecar yields {} and the cards keep their generated description. Prose is
    optional by definition, so it must never abort the scan that carries it.
    """
    sidecar = filepath.with_suffix(_MCP_PROSE_SUFFIX)
    if not sidecar.is_file() or sidecar.is_symlink():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ard-catalogize: skipping {sidecar}: {exc}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        # Same guard as the manifest: a top-level list would raise
        # AttributeError on .get() below, outside any except tuple.
        print(
            f"ard-catalogize: skipping {sidecar}: top level is not an object",
            file=sys.stderr,
        )
        return {}
    return data


def _prose_text(value: Any) -> str:
    """A declared description, capped like a docstring; "" when not a string.

    Not str(): a dict or a list in the sidecar would otherwise be serialized
    into the one field the scorer reads at weight 2.0. Not _shorten() either -
    that caps at 120 and cuts at the first sentence, and a card's description
    is the only capability text the card has.
    """
    return value.strip()[:500] if isinstance(value, str) else ""


def _prose_list(value: Any) -> list[str]:
    """Declared tags/aliases: strings only, stripped, non-empty."""
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()]


def _catalog_mcp_file(
    filepath: Path, root: Path, domain: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Catalog one .mcp.json client config: one entry per mcpServers key.

    env values are deliberately not cataloged — .mcp.json may carry secrets
    there. Shared by the rglob lane in catalog_directory and the root-manifest
    lane in main(): a repo-root .mcp.json sits above every scan_dir, so the
    rglob never reaches it and its servers would otherwise go undiscoverable.

    A sibling `<manifest>.ard.json` may declare prose per server name
    (description / tags / aliases), which replaces the generated description
    and feeds tags, aliases, keywords and representativeQueries with it.
    """
    entries: list[dict[str, Any]] = []
    schemas: dict[str, Any] = {}
    try:
        data = json.loads(
            filepath.read_text(encoding="utf-8", errors="replace")
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ard-catalogize: skipping {filepath}: {exc}", file=sys.stderr)
        return entries, schemas
    # Top level may be a list/scalar: .get() would raise AttributeError,
    # which is not in the except tuple, and kill the whole scan.
    servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
    if not isinstance(servers, dict):
        return entries, schemas
    prose = _mcp_prose(filepath)
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            continue
        # Arbitrary JSON keys: a declared name can reach the path join
        # carrying separators, or be a bare "." / "..", so reduce it to one
        # honest segment or skip. The pyproject door runs the same guard -
        # _TOML_KEY's charset also admits "." and "..", so neither lane's
        # keys are slug-safe on charset alone.
        flat = _declared_segment(name)
        if not flat:
            print(
                f"ard-catalogize: skipping {filepath}: "
                f"unusable server name {name!r}",
                file=sys.stderr,
            )
            continue
        mcp_args = cfg.get("args")
        # An http-only server has no command, and shlex.quote("") is "''" —
        # quoted, joined and stripped it survives as a two-character invoke
        # that shadows the url in `cmd or server_url`. Skip the empty part
        # instead of quoting it.
        command = str(cfg.get("command", "")).strip()
        cmd = " ".join(
            shlex.quote(p)
            for p in ([command] if command else [])
            + [
                str(a)
                # guard: a string args value would char-iterate
                for a in (mcp_args if isinstance(mcp_args, list) else [])
            ]
        ).strip()
        server_url = str(cfg.get("url", "")).strip()
        # Declared prose wins; without it the card keeps the generated pointer
        # text and stays findable only by the server's own name.
        declared = prose.get(name)
        declared = declared if isinstance(declared, dict) else {}
        extra = _prose_list(declared.get("tags"))
        desc = _prose_text(declared.get("description")) or (
            f"MCP server {name} ({'http' if server_url else 'stdio'})."
        )
        # flat, not name: the identifier is the only field that turns
        # a separator into structure. displayName, aliases and tags
        # keep what the publisher wrote.
        identifier = _make_identifier(
            filepath.parent / f"{flat}.mcp", root, domain, "mcp"
        )
        invoke = cmd or server_url
        entries.append({
            "@context": "https://agenticresourcediscovery.org/context/v1",
            "identifier": identifier,
            "displayName": name,
            "description": desc,
            "type": "application/mcp-server-card+json",
            "url": server_url or f"file://{filepath}",
            "tags": list(dict.fromkeys(
                ["mcp", *(t.lower() for t in extra),
                 *name.lower().replace("-", " ").split()]
            ))[:10],
            "aliases": list(dict.fromkeys(
                [name, *_prose_list(declared.get("aliases"))]
            )),
            "representativeQueries": _queries(
                desc, [name, f"mcp {name}", *extra], name
            ),
            "metadata": {
                "keywords": ", ".join(dict.fromkeys(["mcp", name, *extra])),
                "invoke": invoke,
                # A client config can declare a server and switch it off. The
                # card stays in the catalog - an agent that discovers it can
                # ask its host to mount it, or run the invoke itself - but it
                # must not read as callable right now. Metadata, not
                # description: description feeds the search text, and a
                # capability query has no business matching on "disabled".
                "disabled": bool(cfg.get("disabled", False)),
                "path": str(filepath),
                "workspace": str(root),
                "docstring": "",
            },
        })
        schemas.setdefault(identifier, {
            "invoke": invoke,
            "description": desc,
            "arguments": [],
        })
    # A sidecar is hand-maintained, so its likeliest failure is a key matching
    # no server: ignored silently, the card keeps its pointer text and the
    # operator reads the enrichment as landed. Say so.
    for key in prose:
        if key not in servers:
            print(
                f"ard-catalogize: {filepath.with_suffix(_MCP_PROSE_SUFFIX)}: "
                f"prose for unknown server {key!r}",
                file=sys.stderr,
            )
    return entries, schemas


def catalog_directory(
    scan_dir: Path,
    root: Path,
    domain: str = "localhost",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Scan a directory for .py/.sh scripts and SKILL.md agent skills.

    Returns (entries, inspect_schemas) — the schemas feed the registry's
    /inspect endpoint via a sidecar file (spec metadata stays scalar-only).
    Skills and shell scripts have no argparse to mine, so their schema is
    the bare invoke command.
    """
    entries: list[dict[str, Any]] = []
    schemas: dict[str, Any] = {}
    # Resolved once per scan: the interpreter name belongs to the machine
    # building the catalog, so a Windows-built catalog says `python`.
    py = interpreter()

    if not scan_dir.is_dir():
        return entries, schemas

    # Python scripts: AST docstrings + literal argparse flags.
    for filepath in sorted(scan_dir.rglob("*.py")):
        if _skipped(filepath):
            continue

        docstring, short_desc = _extract_docstring(filepath)
        if not short_desc:
            # No docstring — generate from filename
            short_desc = filepath.stem.replace("_", " ").replace("-", " ").capitalize()

        keywords = _extract_keywords(docstring, filepath)
        entry = _script_entry(
            filepath, root, domain, short_desc, keywords, docstring, py
        )
        entries.append(entry)
        schemas.setdefault(entry["identifier"], {
            "invoke": entry["metadata"]["invoke"],
            "description": short_desc,
            "arguments": _extract_argparse_args(filepath),
        })

    # Shell scripts: leading comment block after the shebang as docstring.
    for filepath in sorted(scan_dir.rglob("*.sh")):
        if _skipped(filepath):
            continue

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            # _skipped() tested is_file()/stat() a moment ago, both of which
            # succeed on a file the eventual read is denied - the same race
            # the SKILL.md lane below guards. One unreadable script must skip,
            # not abort the whole ingestion run.
            print(f"ard-catalogize: skipping {filepath}: {exc}", file=sys.stderr)
            continue
        docstring = _shell_docstring(text)
        short_desc = _shorten(docstring) or filepath.stem.replace(
            "_", " "
        ).replace("-", " ").capitalize()
        entry = _script_entry(
            filepath, root, domain, short_desc,
            _extract_keywords(docstring, filepath), docstring, "bash",
            keep_suffix=True,  # foo.sh vs foo.py: distinct identifiers
        )
        entries.append(entry)
        schemas.setdefault(entry["identifier"], {
            "invoke": entry["metadata"]["invoke"],
            "description": short_desc,
            "arguments": [],
        })

    # MCP servers: .mcp.json client configs (Cursor/Claude/Qoder shape),
    # one entry per mcpServers key. Repo-root .mcp.json is read in main() —
    # it sits above every scan_dir, so this rglob never reaches it.
    for filepath in sorted(scan_dir.rglob(".mcp.json")):
        # Not _skipped(): the 100-byte junk floor is for scripts — a real
        # one-server client config is routinely ~70 bytes. JSON parsing plus
        # the mcpServers lookup is the validity filter here.
        if (
            not filepath.is_file()
            or filepath.is_symlink()
            or any(part in SKIP_DIRS for part in filepath.parts)
        ):
            continue
        mcp_entries, mcp_schemas = _catalog_mcp_file(filepath, root, domain)
        entries.extend(mcp_entries)
        for ident, schema in mcp_schemas.items():
            schemas.setdefault(ident, schema)

    # Agent skills: SKILL.md frontmatter; "invoked" by reading the file.
    for filepath in sorted(scan_dir.rglob("SKILL.md")):
        if _skipped(filepath):
            continue

        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            # _skipped() tested is_file() a moment ago, which is exactly the
            # race an unreadable skill wins.
            print(f"ard-catalogize: skipping {filepath}: {exc}", file=sys.stderr)
            continue
        fm = _frontmatter(text)
        skill_dir = filepath.parent
        name = fm.get("name") or skill_dir.name
        desc_full = fm.get("description", "")
        desc = _shorten(desc_full) or name.replace("-", " ").capitalize()
        keywords = _extract_keywords(desc_full, skill_dir)
        rel = (
            skill_dir.relative_to(root)
            if skill_dir.is_relative_to(root)
            else skill_dir
        )
        identifier = _make_identifier(skill_dir, root, domain, "skill")
        rq = _queries(desc, keywords[:4], name)
        aliases = [name] if name == skill_dir.name else [name, skill_dir.name]
        entries.append({
            "@context": "https://agenticresourcediscovery.org/context/v1",
            "identifier": identifier,
            "displayName": name,
            "description": desc,
            "type": 'text/markdown; profile="urn:air:agent-skills"',
            "url": f"file://{filepath}",
            "tags": keywords[:10],
            "aliases": aliases,
            **({"representativeQueries": rq} if len(rq) >= 2 else {}),
            "metadata": {
                "keywords": ", ".join(keywords),
                "invoke": f"cat {shlex.quote((rel / 'SKILL.md').as_posix())}",
                "path": str(rel / "SKILL.md"),
                "workspace": str(root),
                "docstring": desc_full[:500],
            },
        })
        schemas.setdefault(identifier, {
            "invoke": f"cat {shlex.quote((rel / 'SKILL.md').as_posix())}",
            "description": desc,
            "arguments": [],
        })

    return entries, schemas


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Catalog local Python scripts as ARD entries for agent discovery.",
    )
    parser.add_argument(
        "--dir",
        action="append",
        dest="dirs",
        default=None,
        help="Directory to scan (can be repeated). Default: scripts/",
    )
    parser.add_argument(
        "--output",
        default="ai-catalog.json",
        help="Output file. Default: ./ai-catalog.json",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Workspace root for relative paths. Default: current directory.",
    )
    parser.add_argument(
        "--host",
        dest="domain",
        default="localhost",
        help="Host identity for the catalog (did:web:<host>). Default: localhost.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress stdout output.",
    )
    args = parser.parse_args()

    # A POSIX path in any flag resolves under the system drive on Windows
    # instead of failing, and --output then mkdir()s a tree nobody asked for.
    path_error = guard_posix_paths(
        {"output": args.output, "workspace": args.workspace, "dir": args.dirs}
    )
    if path_error:
        print(f"ERROR: {path_error}", file=sys.stderr)
        return 1

    # Determine workspace root
    workspace = Path(args.workspace).resolve() if args.workspace else Path.cwd()
    if not workspace.exists():
        print(f"ERROR: workspace root does not exist: {workspace}", file=sys.stderr)
        return 1

    # Default scan dirs
    raw_dirs = [Path(d) for d in (args.dirs or ["scripts"])]
    scan_dirs = [d if d.is_absolute() else workspace / d for d in raw_dirs]
    scan_dirs = [d for d in scan_dirs if d.is_dir()]

    # Declared console entry points. A packaged repo can legitimately have no
    # scripts/ directory and still publish three commands, so the manifest is
    # read before the scan-dir check rather than after it.
    manifest = workspace / "pyproject.toml"
    project_entries: list[dict[str, Any]] = []
    project_schemas: dict[str, Any] = {}
    pkg_manifest = workspace / "package.json"
    if manifest.is_file() and not manifest.is_symlink():
        project_entries, project_schemas = catalog_project(
            manifest, workspace, args.domain
        )
        if pkg_manifest.is_file() and not pkg_manifest.is_symlink():
            # Issue #3, second tail: the elif below means pyproject wins on
            # a hybrid workspace - the right call - but a package.json with
            # a bin field would lose its commands with no output anywhere.
            try:
                pkg_data = json.loads(
                    pkg_manifest.read_text(encoding="utf-8", errors="replace")
                )
            except (OSError, ValueError):
                pkg_data = None
            bin_field = pkg_data.get("bin") if isinstance(pkg_data, dict) else None
            if bin_field:
                print(
                    f"ard-catalogize: {pkg_manifest}: bin ignored, "
                    f"pyproject.toml commands win",
                    file=sys.stderr,
                )
    elif pkg_manifest.is_file() and not pkg_manifest.is_symlink():
        # JS twin of the pyproject manifest, same posture: read before the
        # scan-dir check. pyproject wins when a workspace ships both.
        project_entries, project_schemas = _package_json_entries(
            pkg_manifest, workspace, args.domain
        )

    # Root .mcp.json. A client config lives at the workspace root, above
    # every scan_dir, so the rglob lane in catalog_directory never reaches
    # it and the servers it declares stay invisible to the very agent that
    # asks the catalog "what can do X". Same posture as the manifests: read
    # before the scan-dir check, appended to the tail.
    root_mcp = workspace / ".mcp.json"
    mcp_entries: list[dict[str, Any]] = []
    mcp_schemas: dict[str, Any] = {}
    if root_mcp.is_file() and not root_mcp.is_symlink():
        mcp_entries, mcp_schemas = _catalog_mcp_file(
            root_mcp, workspace, args.domain
        )

    if not scan_dirs and not project_entries and not mcp_entries:
        print(f"ERROR: no scan directories found under {workspace}", file=sys.stderr)
        return 1

    # Collect entries from all directories
    all_entries: list[dict[str, Any]] = []
    all_schemas: dict[str, Any] = {}
    for scan_dir in scan_dirs:
        entries, schemas = catalog_directory(scan_dir, workspace, args.domain)
        all_entries.extend(entries)
        # First-wins to match the entry dedupe below: the sidecar is written
        # from all_schemas, the catalog from deduped, so a twice-minted URN
        # must keep the same winner on both sides or the invoke assert trips.
        for ident, schema in schemas.items():
            all_schemas.setdefault(ident, schema)

    # Appended, not prepended: existing catalogs keep their entry order, so a
    # re-catalogize diff on a live station is a pure append.
    all_entries.extend(project_entries)
    for ident, schema in project_schemas.items():
        all_schemas.setdefault(ident, schema)
    all_entries.extend(mcp_entries)
    for ident, schema in mcp_schemas.items():
        all_schemas.setdefault(ident, schema)

    # Deduplicate by identifier. First wins, unchanged - but say so: two
    # sources that slug to one URN ("my tool.py" and "my_tool.py" both
    # become scripts:my_tool) used to lose one entry with no output
    # anywhere, and the summary below prints the post-dedupe count, so
    # nothing downstream could notice the drop.
    seen: dict[str, dict[str, Any]] = {}
    deduped: list[dict[str, Any]] = []
    for entry in all_entries:
        ident = entry["identifier"]
        if ident in seen:
            print(
                f"ard-catalogize: duplicate {ident}: keeping "
                f"{seen[ident].get('url', '?')}, dropping "
                f"{entry.get('url', '?')}",
                file=sys.stderr,
            )
            continue
        seen[ident] = entry
        deduped.append(entry)

    # The sidecar is what an agent reads before building a command line, and
    # every invoke in it is relative. Carry the workspace beside it so the
    # command is runnable from any cwd. One pass covers every lane.
    for schema in all_schemas.values():
        schema.setdefault("workspace", str(workspace))

    # Whole-output invariant gate (two contracts, one pass). The catalog is
    # written from deduped (first-wins) and the sidecar from all_schemas, so:
    #  (1) no minted URN may carry an empty/"."/".." section - a declared name
    #      like ".." is dropped at its door, never minted; and
    #  (2) every entry's sidecar schema must carry the same invoke as the entry.
    # Covers lanes that do not exist yet. Fail-closed: neither file is written.
    for entry in deduped:
        ident = entry["identifier"]
        for section in ident.split(":"):
            assert section not in {"", ".", ".."}, (
                f"identifier {ident} carries a bare {section!r} segment"
            )
        schema = all_schemas.get(ident)
        assert schema is not None, f"sidecar missing schema for {ident}"
        assert schema["invoke"] == entry["metadata"]["invoke"], (
            f"sidecar/entry invoke divergence for {ident}: "
            f"sidecar={schema['invoke']!r} entry={entry['metadata']['invoke']!r}"
        )

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = workspace / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write catalog — spec schema allows only specVersion/host/entries at the
    # top level; bookkeeping goes to stderr. Atomic swap so a registry reading
    # the file concurrently never sees a partial write; unique tmp name so
    # concurrent catalogize runs don't steal each other's temp file.
    catalog = {
        "specVersion": "1.0",
        "host": {
            "displayName": "Local Scripts",
            "identifier": f"did:web:{args.domain}",
        },
        "entries": deduped,
    }

    _atomic_write_json(output_path, catalog)

    # Invoke-schema sidecar for the registry's GET /inspect endpoint.
    _atomic_write_json(output_path.with_suffix(".inspect.json"), all_schemas)

    if not args.quiet:
        print(f"Cataloged {len(deduped)} entries from {len(scan_dirs)} directories")
        print(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        print(f"Scanned: {[_display_path(d, workspace) for d in scan_dirs]}")
        print(f"Output: {output_path}")
        # Show top 10 by keyword richness
        top = sorted(deduped, key=lambda e: len(e.get("tags", [])), reverse=True)[:5]
        for entry in top:
            tags = ", ".join(entry.get("tags", [])[:5])
            print(f"  {entry['displayName']:40s} [{tags}]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
