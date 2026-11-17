#!/usr/bin/env python3
"""Upstream hook contract probe (nightly drift hardening, 2026-10-10).

The plugin registers hooks on the Duckwork core via ctx.register_hook("<name>").
If a core-side change removes or renames one of those hook points, the plugin
fails silently at runtime (card loss) — nothing in CI catches it today. This
test is the drift probe: it parses the hook names THIS plugin registers out of
__init__.py source, extracts the core's VALID_HOOKS set out of
duckwork_cli/plugins.py WITHOUT importing it (importing pulls heavy agent
modules), and asserts every registered hook is still a core-known hook.

Conventions (repo test style):
  - stdlib only
  - prints one PASS line per hook plus summary lines
  - exit 0 = green (also green when duckwork_cli is not importable: the suite
    must run on checkouts without the core installed -> SKIP + exit 0)
  - empty VALID_HOOKS extraction = RED, never a silent pass (audit #112 lesson:
    empty discovery is a failure, not an absence of findings)

Run:  python3 tests/test_upstream_hook_contract.py   (from the repo root)
"""
import importlib.util
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INIT_PATH = REPO_ROOT / "__init__.py"

# Hook registrations look like: ctx.register_hook("transform_llm_output", fn)
REGISTER_HOOK_RE = re.compile(r"""register_hook\(\s*['"]([A-Za-z0-9_]+)['"]""")

# The core declares its accepted hook names as a module-level set literal:
#   VALID_HOOKS: set[str] = {
#       "pre_tool_call", "post_tool_call", ...
#   }
# Extract it textually so we never import duckwork_cli.plugins. The body runs
# to the closing brace at line start (MULTILINE), so a stray "}" inside an
# explanatory comment cannot truncate the extraction early.
VALID_HOOKS_RE = re.compile(
    r"""^VALID_HOOKS[^=\n]*=\s*\{(?P<body>.*?)^\}""",
    re.DOTALL | re.MULTILINE,
)
QUOTED_NAME_RE = re.compile(r"""['"]([A-Za-z0-9_]+)['"]""")


def registered_hooks():
    """Hook names this plugin registers, parsed from __init__.py source."""
    if not INIT_PATH.is_file():
        print(f"FAIL: plugin __init__.py not found at {INIT_PATH}")
        sys.exit(1)
    source = INIT_PATH.read_text(encoding="utf-8")
    names = sorted(set(REGISTER_HOOK_RE.findall(source)))
    if not names:
        # A plugin that registers nothing would make this probe vacuous.
        # Today it registers exactly one hook; zero parsed names means the
        # call shape changed or the registration vanished — that is red.
        print(f"FAIL: no ctx.register_hook(...) calls parsed from {INIT_PATH}")
        sys.exit(1)
    return names, source


def locate_core_plugins():
    """Path to the installed duckwork_cli/plugins.py, or None if not importable."""
    try:
        spec = importlib.util.find_spec("duckwork_cli")
    except (ImportError, ValueError, ModuleNotFoundError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    for loc in spec.submodule_search_locations:
        candidate = Path(loc) / "plugins.py"
        if candidate.is_file():
            return candidate
    return None


def core_valid_hooks(plugins_path):
    """Set of quoted names inside the VALID_HOOKS literal, extracted textually."""
    text = plugins_path.read_text(encoding="utf-8")
    match = VALID_HOOKS_RE.search(text)
    if match is None:
        return None
    # Drop comment lines before collecting quoted names: the literal carries
    # prose comments with quoted example payloads that are not hook names.
    body = "\n".join(line.split("#", 1)[0] for line in match.group("body").splitlines())
    return set(QUOTED_NAME_RE.findall(body))


def main():
    hooks, _ = registered_hooks()
    print(f"PASS: parsed {len(hooks)} plugin-registered hook(s) from {INIT_PATH}")
    for h in hooks:
        print(f"  registered: {h}")

    plugins_path = locate_core_plugins()
    if plugins_path is None:
        print("SKIP-reason: duckwork_cli is not importable in this environment; "
              "core VALID_HOOKS contract check deferred (suite-runs-without-core case)")
        sys.exit(0)

    valid = core_valid_hooks(plugins_path)
    if not valid:
        # Empty/failed extraction is red, not a silent pass (audit #112).
        print(f"FAIL: could not extract a non-empty VALID_HOOKS set from {plugins_path}")
        sys.exit(1)
    print(f"PASS: extracted {len(valid)} core VALID_HOOKS names from {plugins_path}")

    failures = [h for h in hooks if h not in valid]
    if failures:
        for h in failures:
            print(f"FAIL: hook '{h}' is registered by this plugin but is NOT in "
                  f"core VALID_HOOKS ({plugins_path}) — upstream drift")
        print(f"FAIL: {len(failures)} hook(s) broken against core")
        sys.exit(1)

    for h in hooks:
        print(f"{h} · found in core VALID_HOOKS (evidence: {plugins_path})")
    print("PASS: every plugin-registered hook is a core-valid hook")
    sys.exit(0)


if __name__ == "__main__":
    main()
