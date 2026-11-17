#!/usr/bin/env python3
"""Milestone 4 - one portable agent loop, end to end, with a runnable check.

    task -> discover -> inspect -> authorized call -> verified result

This is the same flow the live station registry serves over HTTP
(`POST /search` then `GET /inspect?identifier=<urn>`), distilled into a single
self-contained script: no server, no bearer token, no network. It reuses the
REAL ard-kit pieces rather than a parallel protocol:

  discover  ard_kit.registry.search_catalog  - lexical token overlap, top hit wins
  inspect   the (entries, schemas) pair catalog_directory returns; `schemas[urn]`
            is byte-for-byte the payload GET /inspect serves
            ({identifier, invoke, description, arguments})
  run       execution stays with the CLIENT (subprocess), never a universal
            executor - the registry only tells you what exists and how to call it
  verify    assert on the produced FILE / stdout, NOT on the chosen tool's name

A tool that is discovered but cannot be run (binary missing, or not on the
client's allowlist) is reported as unavailable instead of crashing - the
milestone-4 "done when" is that a small set of tasks get verified results AND
an unavailable tool is reported correctly.

Run it:  python3 examples/agent_loop.py     (prints OK and exits 0 when every
task behaves; a failed assert exits non-zero)
"""
from __future__ import annotations

import csv
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Same convention as selfcheck.py: make the in-repo ard_kit importable without
# installing the package, so the example runs from a clean checkout.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ard_kit.catalogize import ENTRY_TYPE, catalog_directory  # noqa: E402
from ard_kit.registry import search_catalog  # noqa: E402

# --- a tiny, safe toolset the agent will discover --------------------------
# Written to a temp dir at run time so the example is portable: no station
# scripts, no network, nothing to install. Each has a module docstring (mined
# for the description) and literal argparse flags (mined for the inspect schema).
TOOLS = {
    "csv_transform.py": '''#!/usr/bin/env python3
"""Transform a CSV file: uppercase every value in one named column.

Reads the input CSV, uppercases the cells of the given column and writes the
result to the output path. Local and safe - no network, no deletion.
"""
import argparse
import csv
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="Uppercase one column of a CSV file.")
    p.add_argument("--input", required=True, help="path to the source CSV")
    p.add_argument("--output", required=True, help="path to write the transformed CSV")
    p.add_argument("--column", required=True, help="name of the column to uppercase")
    a = p.parse_args()
    with open(a.input, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if a.column not in fields:
        print(f"error: no column {a.column!r}", file=sys.stderr)
        return 2
    for row in rows:
        row[a.column] = row[a.column].upper()
    with open(a.output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
    "json_validate.py": '''#!/usr/bin/env python3
"""Validate that a file contains well-formed JSON.

Prints 'valid' and exits 0 when the file parses; otherwise prints the parse
error and exits 1. Local and safe - no network, no deletion.
"""
import argparse
import json


def main() -> int:
    p = argparse.ArgumentParser(description="Check a file parses as JSON.")
    p.add_argument("--input", required=True, help="path to the JSON file to validate")
    a = p.parse_args()
    try:
        with open(a.input, encoding="utf-8") as fh:
            json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid: {exc}")
        return 1
    print("valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
    "text_count.py": '''#!/usr/bin/env python3
"""Count the lines, words and characters in a text file.

Prints 'lines=N words=M chars=K'. Local and safe - no network, no deletion.
"""
import argparse
import sys


def main() -> int:
    p = argparse.ArgumentParser(description="Count lines, words and characters.")
    p.add_argument("--input", required=True, help="path to the text file to count")
    a = p.parse_args()
    try:
        with open(a.input, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"lines={text.count(chr(10))} words={len(text.split())} chars={len(text)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
}

DATA = {
    "data.csv": "name,role\nalice,admin\nbob,user\n",
    "good.json": '{"ok": true, "n": 3}\n',
    "notes.txt": "alpha beta gamma\ndelta epsilon\n",
}

# A discovered-but-unrunnable tool. catalog_directory only catalogs real files,
# so this one entry is appended by hand to exercise the negative path: its
# binary is neither on PATH nor on the client allowlist, so the authorized-call
# gate must refuse it and report "unavailable", not crash the loop.
MISSING_ID = "urn:air:localhost:script:transcode_media"
MISSING_ENTRY = {
    "@context": "https://agenticresourcediscovery.org/context/v1",
    "identifier": MISSING_ID,
    "displayName": "transcode_media",
    "description": "transcode a media file to another container format",
    "type": ENTRY_TYPE,
    "url": "file:///opt/ard-demo/transcode_media.py",
    "tags": ["transcode", "media", "container"],
    "aliases": ["transcode_media"],
    "metadata": {"invoke": "ard-demo-nonexistent-binary --transcode"},
}
MISSING_SCHEMA = {
    "invoke": "ard-demo-nonexistent-binary --transcode",
    "description": "transcode a media file to another container format",
    "arguments": [{"name": "--transcode", "kind": "option", "help": "target format"}],
}

# ponytail: authorization here is a two-name binary allowlist, deliberately not
# the station's bearer-token/policy gate - the point of the example is the LOOP
# (discover -> inspect -> gated call -> verified result), not re-implementing
# ard-registry auth. Swap this set for a real policy check when integrating.
ALLOWED_BINARIES = {"python3", "bash"}


def discover(catalog: dict, intent: str) -> dict | None:
    """Top-ranked hit for an intent, or None when nothing matches."""
    _total, page, _next = search_catalog(catalog, intent, None, 5)
    return page[0] if page else None


def inspect(schemas: dict, identifier: str) -> dict | None:
    """Mirror of GET /inspect?identifier=<urn>: {identifier, invoke, ...}."""
    schema = schemas.get(identifier)
    return None if schema is None else {"identifier": identifier, **schema}


def authorized_call(invoke: str, args: list[str], cwd: Path) -> dict:
    """Run the discovered invoke locally, gated by availability + allowlist.

    Execution stays with the client: the registry never runs anything, it only
    says what exists and how to call it. A missing or unauthorized binary is
    reported, not executed.
    """
    argv = shlex.split(invoke) + list(args)
    if not argv:
        return {"status": "unavailable", "reason": "empty invoke"}
    binary = argv[0]
    if shutil.which(binary) is None:
        return {"status": "unavailable", "reason": f"binary {binary!r} not on PATH"}
    if binary not in ALLOWED_BINARIES:
        return {"status": "unavailable", "reason": f"binary {binary!r} not allowlisted"}
    try:
        proc = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"status": "unavailable", "reason": f"could not exec {binary!r}: {exc}"}
    return {
        "status": "ran",
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def run_task(catalog: dict, schemas: dict, root: Path, task: dict) -> dict:
    """One full loop: discover -> inspect -> authorized call -> verify result."""
    intent = task["intent"]
    hit = discover(catalog, intent)
    if hit is None:
        return {"task": intent, "status": "no-tool", "verified": False}
    tool = hit["displayName"]
    schema = inspect(schemas, hit["identifier"])
    if schema is None:
        return {"task": intent, "tool": tool, "status": "no-inspect", "verified": False}
    outcome = authorized_call(schema["invoke"], task["args"], cwd=root)
    if outcome["status"] != "ran":
        return {
            "task": intent, "tool": tool, "status": outcome["status"],
            "reason": outcome.get("reason"), "verified": False,
        }
    if outcome["returncode"] != 0:
        detail = (outcome["stderr"] or outcome["stdout"]).strip()[:120]
        return {
            "task": intent, "tool": tool, "status": "failed",
            "detail": detail, "verified": False,
        }
    # Verify the RESULT (the produced file / stdout), never the tool's name:
    # a different tool that produces the right artifact is a correct answer.
    verify = task.get("verify")
    ok, detail = verify(root, outcome) if verify else (True, "")
    return {
        "task": intent, "tool": tool, "status": "ok" if ok else "unverified",
        "verified": ok, "detail": detail,
    }


def _verify_csv(root: Path, _outcome: dict) -> tuple[bool, str]:
    with open(root / "out.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    names = [r["name"] for r in rows]
    roles = [r["role"] for r in rows]
    ok = names == ["ALICE", "BOB"] and roles == ["admin", "user"]
    return ok, f"out.csv names={names} roles={roles}"


def _verify_json(_root: Path, outcome: dict) -> tuple[bool, str]:
    ok = outcome["returncode"] == 0 and "valid" in outcome["stdout"]
    return ok, outcome["stdout"].strip()


def _verify_count(_root: Path, outcome: dict) -> tuple[bool, str]:
    text = DATA["notes.txt"]
    want = f"lines={text.count(chr(10))} words={len(text.split())} chars={len(text)}"
    got = outcome["stdout"].strip()
    return got == want, f"{got} (want {want})"


TASKS = [
    {"intent": "uppercase a column in a csv", "expect": "ok", "verify": _verify_csv,
     "args": ["--input", "data.csv", "--output", "out.csv", "--column", "name"]},
    {"intent": "validate json is well formed", "expect": "ok", "verify": _verify_json,
     "args": ["--input", "good.json"]},
    {"intent": "count lines words characters", "expect": "ok", "verify": _verify_count,
     "args": ["--input", "notes.txt"]},
    {"intent": "transcode media to another format", "expect": "unavailable",
     "args": []},
]


def demo() -> int:
    root = Path(tempfile.mkdtemp(prefix="ard-milestone4-"))
    try:
        for name, src in TOOLS.items():
            (root / name).write_text(src, encoding="utf-8")
        for name, body in DATA.items():
            (root / name).write_text(body, encoding="utf-8")

        # discover + inspect come from the REAL builders/registry, not a
        # parallel protocol: catalog_directory returns (entries, schemas) and
        # `schemas` is exactly what GET /inspect serves.
        entries, schemas = catalog_directory(root, root)
        entries.append(MISSING_ENTRY)
        schemas[MISSING_ID] = MISSING_SCHEMA
        catalog = {"entries": entries}
        print(f"catalog: {len(entries)} tools in {root}")

        failures = []
        for task in TASKS:
            res = run_task(catalog, schemas, root, task)
            good = res["status"] == task["expect"] and (
                task["expect"] != "ok" or res["verified"]
            )
            if not good:
                failures.append((task["intent"], res))
            line = f"[{'OK ' if good else 'FAIL'}] {task['intent']!r} -> {res['status']}"
            if res.get("tool"):
                line += f" via {res['tool']}"
            if res.get("detail"):
                line += f" ({res['detail']})"
            if res.get("reason"):
                line += f" ({res['reason']})"
            print(line)

        for intent, res in failures:
            print(f"  unexpected: {intent}: {res}", file=sys.stderr)
        assert not failures, f"{len(failures)} task(s) did not behave as expected"
        print("OK: discover -> inspect -> authorized call -> verified result")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(demo())
