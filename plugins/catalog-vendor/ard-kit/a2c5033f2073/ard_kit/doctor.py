#!/usr/bin/env python3
"""Preflight for an ard-kit install: is discovery actually usable from here?

Installing the plugin and being able to use it are two different states, and
between them sit failures that no single command surfaces. A Windows onboarding
run collected six of them at once: `python3` is not on PATH, so every wrapper
dies with `env: 'python3': No such file or directory`; the catalog path is
POSIX, so it resolves under the system drive instead of failing; the registry
answers 401 on every endpoint but `/health`, which reads as "broken" to a caller
that never learned the gate is deliberate; and the harness that would have
caught all of it only runs from a checkout.

So one command walks the whole chain and, for every failure, prints the reason
and the next command. Order follows the chain: interpreter -> wrappers ->
catalog -> registry -> search -> harness. A check that cannot run because an
earlier one failed says SKIP and names the earlier one, so one broken link is
reported once rather than five times.

Exit status is 0 when nothing FAILed (warnings and skips included) and 1 when
something did: this is a gate, and a gate that always passes is decoration.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ard_kit import __version__
from ard_kit.catalogize import guard_posix_paths, interpreter

# Same command names as bin/ and [project.scripts]. ard-doctor is in the list on
# purpose: being able to run it via `python -m` does not mean an agent's shell
# can, and the plugin commands call the bare names.
COMMANDS = (
    "ard-catalogize",
    "ard-registry",
    "ard-mcp",
    "ard-verify",
    "ard-doctor",
)
INTERPRETERS = ("python3", "python", "py")
# Fallback probe phrase, used only when the catalog yields no term of its own.
PROBE_QUERY = "doctor probe"
DEFAULT_URL = "http://127.0.0.1:8390"
# Long enough for the end-to-end harness on a cold machine, short enough that a
# wedged subprocess does not turn a preflight into a hang.
SELFCHECK_TIMEOUT = 900.0
# Set in the harness subprocess's environment so a harness that itself pins the
# doctor does not start a second harness: doctor -> selfcheck -> doctor -> ...
# is a fork bomb with a progress bar.
NESTED_ENV = "ARD_DOCTOR"
# Label column: every label in this file fits, so the dots line up.
WIDTH = 26

OK = "ok"
WARN = "WARN"
FAIL = "FAIL"
SKIP = "SKIP"


@dataclasses.dataclass(frozen=True)
class Check:
    """One row of the report, plus what to do about it when it is not ok."""

    label: str
    status: str
    detail: str
    hint: str = ""
    next: str = ""


def emit(text: str = "") -> None:
    """Print and flush: a preflight read through a pipe still shows progress."""
    print(text, flush=True)


def row(label: str, text: str) -> str:
    return f"  {label} {'.' * max(3, WIDTH - len(label))} {text}"


def report(check: Check) -> None:
    """One check as a padded row; anything not ok carries hint and next command."""
    detail = check.detail if check.status == OK else f"{check.status}: {check.detail}"
    emit(row(check.label, detail))
    pad = " " * (WIDTH + 4)
    if check.hint:
        emit(f"{pad}hint: {check.hint}")
    if check.next:
        emit(f"{pad}next: {check.next}")


def bin_dir() -> Path:
    """This checkout's bin/, the fallback source wrapper() searches."""
    return Path(__file__).resolve().parent.parent / "bin"


def wrapper(name: str) -> str | None:
    """Path to a command wrapper, or None: PATH first, then this checkout's bin/.

    The bin/ fallback is what makes the doctor usable before PATH is set up -
    which is exactly when it is needed. On Windows the .cmd twin is the runnable
    one; the POSIX script beside it resolves but cannot be exec'd.
    """
    found = shutil.which(name)
    if found:
        return found
    candidates = (name + ".cmd", name) if os.name == "nt" else (name,)
    for candidate in candidates:
        path = bin_dir() / candidate
        if path.is_file():
            return str(path)
    return None


def http_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 5.0,
) -> tuple[int, dict[str, Any]]:
    """(status, parsed body) for one request; 4xx/5xx come back, not raised.

    A 401 here is the answer, not an error: the registry's refusal body carries
    the hint that explains the gate, and raising it would throw that away.
    """
    request = urllib.request.Request(url, method=method)
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", "application/json")
        request.data = json.dumps(body).encode("utf-8")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    try:
        payload = json.loads(raw)
    except ValueError:
        payload = {"raw": raw[:200]}
    return status, payload if isinstance(payload, dict) else {"raw": payload}


def check_interpreter() -> Check:
    """The interpreter catalogize will name in every invoke line it writes."""
    want = interpreter()
    found = shutil.which(want)
    if found:
        return Check("interpreter", OK, f"{want} -> {found}")
    others = [
        f"{name} -> {path}"
        for name in INTERPRETERS
        if name != want and (path := shutil.which(name))
    ]
    if others:
        return Check(
            "interpreter",
            WARN,
            f"{want} NOT FOUND ({', '.join(others)})",
            hint=f"metadata.invoke lines in any catalog built here will start "
            f"with {want!r}, so an agent copying one verbatim gets "
            f"'command not found' on a machine that does have Python",
            next=f"put a {want!r} on PATH, or edit the invoke before running it",
        )
    return Check(
        "interpreter",
        FAIL,
        f"no Python on PATH (tried {', '.join(INTERPRETERS)})",
        hint="ard-kit is Python and nothing below can work without one; the "
        "Microsoft Store python.exe stub resolves but refuses to run anything",
        next="install Python 3.10+ and reopen the shell so PATH is re-read",
    )


def check_wrappers() -> Check:
    """Are the console commands reachable the way an agent would call them.

    Found-on-PATH and found-in-this-checkout are counted apart, because they
    mean different things to the caller: a wrapper that only exists under bin/
    runs for the doctor and for nobody else. Reporting the union as "on PATH"
    is a green light over a broken install.
    """
    on_path = {name: shutil.which(name) for name in COMMANDS}
    resolved = {name: on_path[name] or wrapper(name) for name in COMMANDS}
    present = [name for name in COMMANDS if resolved[name]]
    missing = [name for name in COMMANDS if not resolved[name]]
    if not present:
        return Check(
            "bin/ard-* on PATH",
            FAIL,
            "none found",
            hint="without the wrappers every plugin command and every documented "
            "invocation is a bare `python -m ard_kit...` the caller has to know",
            next=f"add {bin_dir()} to PATH, or: pip install agentic-ard-kit",
        )
    detail = f"{len(present)} of {len(COMMANDS)} found"
    if missing:
        return Check(
            "bin/ard-* on PATH",
            WARN,
            f"{detail} (missing: {', '.join(missing)})",
            hint="a partial set usually means bin/ was copied or a .cmd twin is "
            "absent where cmd.exe needs one",
            next=f"check {bin_dir()} holds both forms of every command",
        )
    off_path = [name for name in COMMANDS if not on_path[name]]
    if off_path:
        return Check(
            "bin/ard-* on PATH",
            WARN,
            f"{detail} ({', '.join(off_path)} only in {bin_dir()}, not on PATH)",
            hint="a shell in any other cwd cannot call these by name, so plugin "
            "commands and catalog invoke lines that say `ard-catalogize` will "
            "not resolve",
            next=f"add {bin_dir()} to PATH (the .cmd twins live there too)",
        )
    return Check("bin/ard-* on PATH", OK, detail)


def check_runnable() -> Check:
    """Does a wrapper actually run - PATH presence proves nothing on Windows.

    `command -v python3` succeeded on the onboarding machine too, and the
    wrapper still died at exec time. Only running one tells the truth, and
    --help is the cheapest thing that exercises the whole shebang-plus-PYTHONPATH
    path without touching a catalog.
    """
    target = wrapper("ard-verify")
    if target is None:
        return Check(
            "bin/ard-verify runnable",
            SKIP,
            "no wrapper found on PATH or in bin/",
            next="fix 'bin/ard-* on PATH' first",
        )
    try:
        proc = subprocess.run(
            [target, "--help"], capture_output=True, text=True, timeout=60
        )
    except subprocess.TimeoutExpired:
        return Check(
            "bin/ard-verify runnable", FAIL, "no --help within 60s",
            hint="a wrapper that hangs is worse than one that fails: callers "
            "block instead of reading an error",
            next=f"run it by hand to see where it stalls: {target} --help",
        )
    except OSError as exc:
        return Check(
            "bin/ard-verify runnable",
            FAIL,
            f"cannot exec {target}: {exc}",
            hint="on POSIX this is a missing +x, on Windows it is a .sh being "
            "picked up where the .cmd twin should have been",
            next=f"chmod +x {target}",
        )
    if proc.returncode != 0:
        noise = (proc.stderr or proc.stdout or "").strip().splitlines()
        return Check(
            "bin/ard-verify runnable",
            FAIL,
            f"exit {proc.returncode}: {noise[-1] if noise else 'no output'}",
            hint="every wrapper shares this shape, so all of them fail the same "
            "way - which is also how every catalog invoke fails",
            next=f"{target} --help",
        )
    return Check("bin/ard-verify runnable", OK, f"{target} --help")


def check_catalog(raw: str) -> tuple[Check, str]:
    """Is there a catalog to serve, and can this machine read the path naming it.

    Second element is a search term lifted from the catalog itself, so the
    probe downstream asks for something this file does contain.
    """
    # Reported as a check rather than refused up front like the other CLIs do:
    # doctor creates nothing, and exiting here would hide the one line that
    # explains the trap it exists to diagnose.
    complaint = guard_posix_paths({"catalog": raw})
    if complaint:
        return Check(
            "catalog path",
            FAIL,
            "POSIX path under Windows",
            hint=complaint,
            next="pass a Windows path (D:\\project\\ai-catalog.json) or the UNC "
            "form for a file inside WSL",
        ), ""
    path = Path(raw).expanduser()
    py = interpreter()
    if not path.is_file():
        return Check(
            "catalog path",
            FAIL,
            f"NOT FOUND {path.resolve()}",
            hint="the registry and the MCP front both serve a catalog file; with "
            "no file there is nothing to discover and every search returns zero",
            next=f"{py} -m ard_kit.catalogize --dir scripts --output {raw}",
        ), ""
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return Check(
            "catalog path", FAIL, f"unreadable {path.resolve()}: {exc}",
            next=f"{py} -m ard_kit.catalogize --dir scripts --output {raw}",
        ), ""
    entries = catalog.get("entries") if isinstance(catalog, dict) else None
    count = len(entries) if isinstance(entries, list) else 0
    term = ""
    if count:
        first = entries[0].get("displayName") if isinstance(entries[0], dict) else None
        term = first if isinstance(first, str) else ""
    sidecar = path.with_suffix(".inspect.json")
    detail = f"{count} entries, specVersion {catalog.get('specVersion')}"
    if count == 0:
        return Check(
            "catalog path", WARN, f"{detail} (empty)",
            hint="an empty catalog answers every query with zero results, which "
            "reads as 'discovery is broken' rather than 'nothing was scanned'",
            next=f"{py} -m ard_kit.catalogize --dir <where the scripts are> "
            f"--output {raw}",
        ), ""
    if not sidecar.is_file():
        return Check(
            "catalog path", WARN, f"{detail}, no inspect sidecar",
            hint=f"{sidecar.name} is what /inspect answers from; without it the "
            "endpoint 501s and an agent gets no invoke schema",
            next=f"{py} -m ard_kit.catalogize --dir scripts --output {raw}",
        ), term
    return Check("catalog path", OK, f"{detail} ({path.resolve()})"), term


def check_health(url: str, catalog_raw: str) -> tuple[Check, dict[str, Any]]:
    """Liveness plus the two facts that decide how to read every later failure."""
    py = interpreter()
    try:
        status, body = http_json(url.rstrip("/") + "/health")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return Check(
            "registry /health",
            FAIL,
            f"unreachable {url}: {exc}",
            hint="/health is the one endpoint the token does not cover, so this "
            "is not an auth problem - nothing is listening there",
            next=f"{py} -m ard_kit.registry --catalog {catalog_raw} --port 8390",
        ), {}
    if status != 200:
        return Check(
            "registry /health", FAIL, f"HTTP {status}: {body.get('hint') or body}",
            hint="something else answers on that port",
            next="check what owns it, or point --url/ARD_REGISTRY_URL at the registry",
        ), {}
    detail = (
        f"{body.get('status')} v{body.get('version')}, auth {body.get('auth')}, "
        f"entries {body.get('entries')}, generated {body.get('catalogGeneratedAt')}"
    )
    if body.get("status") != "ok":
        return Check(
            "registry /health", WARN, detail,
            hint="the registry is up but could not read its catalog, so search "
            "will answer from nothing",
            next=f"{py} -m ard_kit.registry --catalog <a path this machine can read>",
        ), body
    if body.get("entries") == 0:
        return Check(
            "registry /health", WARN, detail,
            hint="serving an empty catalog: reachable, but every search returns zero",
            next=f"{py} -m ard_kit.catalogize --dir scripts --output {catalog_raw}",
        ), body
    return Check("registry /health", OK, f"{detail} ({url})"), body


def check_search(
    url: str, token: str | None, health: dict[str, Any], query: str
) -> Check:
    """One authenticated query: the step an agent actually performs."""
    if not health:
        return Check(
            "search probe", SKIP, "registry not reachable",
            next="fix 'registry /health' first",
        )
    query = query or PROBE_QUERY
    status, body = http_json(
        url.rstrip("/") + "/search",
        method="POST",
        body={"query": {"text": query}, "pageSize": 1},
        token=token,
    )
    if status == 401:
        return Check(
            "search probe",
            FAIL,
            f"401 unauthorized (ARD_REGISTRY_TOKEN {'set' if token else 'NOT set'})",
            hint=body.get("hint")
            or "every endpoint except /health needs the bearer token",
            next="export ARD_REGISTRY_TOKEN=<the token this registry was started "
            "with>, then re-run ard-doctor",
        )
    if status != 200:
        return Check(
            "search probe", FAIL, f"HTTP {status}: {body.get('hint') or body}",
            next=f"{interpreter()} -m ard_kit.registry --help",
        )
    results = body.get("results")
    total = body.get("totalResults")
    if not isinstance(results, list):
        return Check(
            "search probe", FAIL, f"response has no results list: {sorted(body)}",
            hint="a registry that answers 200 with the wrong envelope breaks "
            "every client that reads results[].identifier",
        )
    detail = f"{len(results)} returned, totalResults {total} for {query!r}"
    if total == 0:
        return Check(
            "search probe", WARN, detail,
            hint="the query is a name this catalog contains, so zero matches "
            "means the registry is serving a different or empty file",
            next="compare 'catalog path' and 'registry /health' above",
        )
    return Check("search probe", OK, detail)


def check_selfcheck(timeout: float) -> Check:
    """Run the harness - but only where it exists: it ships in the checkout.

    selfcheck.py is deliberately not in the wheel, so an installed copy cannot
    prove itself and must say so instead of failing on a missing file.
    """
    root = Path(__file__).resolve().parent.parent
    harness = root / "selfcheck.py"
    if os.environ.get(NESTED_ENV):
        return Check(
            "selfcheck",
            SKIP,
            "already inside an ard-doctor run",
            hint="the harness pins this doctor, so a nested run would only "
            "re-prove what the outer one is proving right now",
            next=f"{sys.executable} selfcheck.py  # run it by hand, once",
        )
    if not harness.is_file():
        return Check(
            "selfcheck",
            SKIP,
            "selfcheck.py is not installed beside the package",
            hint="the harness ships in the checkout, not in the wheel, so this "
            "install cannot prove itself here",
            next="git clone https://gitlab.com/ameobius-ai/ard-kit && cd ard-kit "
            f"&& {sys.executable} selfcheck.py",
        )
    try:
        proc = subprocess.run(
            [sys.executable, str(harness), "--quiet"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, NESTED_ENV: "1"},
        )
    except subprocess.TimeoutExpired:
        return Check(
            "selfcheck", WARN, f"still running after {timeout:.0f}s",
            next=f"{sys.executable} selfcheck.py  # watch it live",
        )
    except OSError as exc:
        return Check("selfcheck", FAIL, f"cannot run {harness}: {exc}")
    if proc.returncode != 0:
        tail = [
            line
            for line in (proc.stderr or "").strip().splitlines()
            if line.strip()
        ]
        return Check(
            "selfcheck",
            FAIL,
            f"exit {proc.returncode}: {tail[-1] if tail else 'no output'}",
            hint="the harness fails on the machine that will also fail the "
            "plugin, so this is the finding, not a formality",
            next=f"{sys.executable} selfcheck.py  # full output, no --quiet",
        )
    passed = [
        line for line in (proc.stdout or "").strip().splitlines() if line.strip()
    ]
    return Check("selfcheck", OK, passed[-1] if passed else "PASS")


def run_checks(
    catalog_raw: str, url: str, token: str | None, timeout: float
) -> list[Check]:
    """Every check in chain order, printed as it completes.

    Order is cheap-and-blocking first: an interpreter nothing can run makes the
    wrapper probe pointless, and a registry nobody can reach makes the search
    probe pointless. The harness goes last because it is the slow one, and a
    preflight that hides its own progress behind a minute of silence reads as a
    hang. /health and the search probe stay paired - the second reads the
    first's answer to tell an expected 401 from a surprise.
    """
    checks: list[Check] = []

    def add(check: Check) -> None:
        checks.append(check)
        report(check)

    add(check_interpreter())
    add(check_wrappers())
    add(check_runnable())
    catalog_check, query = check_catalog(catalog_raw)
    add(catalog_check)
    health_check, health = check_health(url, catalog_raw)
    add(health_check)
    add(check_search(url, token, health, query))
    add(check_selfcheck(timeout))
    return checks


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def verdict(checks: list[Check]) -> tuple[str, int]:
    """Summary line and exit status: warnings pass, failures do not."""
    failed = sum(1 for c in checks if c.status == FAIL)
    warned = sum(1 for c in checks if c.status == WARN)
    skipped = sum(1 for c in checks if c.status == SKIP)
    total = len(checks)
    if failed:
        extra = f", {_plural(warned, 'warning')}" if warned else ""
        return f"{failed} of {total} checks failed{extra} - hints above", 1
    notes = ", ".join(
        part
        for part in (
            _plural(warned, "warning") if warned else "",
            _plural(skipped, "skip") if skipped else "",
        )
        if part
    )
    return f"all {total} checks passed" + (f" ({notes})" if notes else ""), 0


def main(argv: list[str] | None = None) -> int:
    """CLI: 0 = nothing FAILed, 1 = something did."""
    parser = argparse.ArgumentParser(
        prog="ard-doctor",
        description="Preflight an ard-kit install: interpreter, wrappers, "
        "catalog, registry, search, harness - each failure with its next command.",
    )
    parser.add_argument(
        "--catalog",
        default="ai-catalog.json",
        help="Catalog the registry should be serving (default ai-catalog.json).",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("ARD_REGISTRY_URL", DEFAULT_URL),
        help=f"Registry base URL (default {DEFAULT_URL}, or $ARD_REGISTRY_URL).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=SELFCHECK_TIMEOUT,
        help=f"Seconds to give selfcheck.py (default {SELFCHECK_TIMEOUT:.0f}).",
    )
    args = parser.parse_args(argv)

    emit(
        f"ard-kit doctor {__version__} "
        f"({sys.version.split()[0]} on {sys.platform}, cwd {os.getcwd()})"
    )
    token = os.environ.get("ARD_REGISTRY_TOKEN")
    if token:
        # Named, never printed: a preflight that leaks the bearer token into a
        # transcript or a CI log is worse than no preflight.
        emit(f"  ARD_REGISTRY_TOKEN set ({len(token)} chars)")
    checks = run_checks(args.catalog, args.url, token, args.timeout)
    line, status = verdict(checks)
    report(Check("verdict", FAIL if status else OK, line))
    return status


if __name__ == "__main__":
    sys.exit(main())
