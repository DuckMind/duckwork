#!/usr/bin/env python3
"""Fail-closed guard for the graphify CLI — the declared test dep behind the
graph gates (sys-hvd5gl).

History: the graph-gate tests skipped (exit 0, one SKIP line) when the graphify
CLI was absent, so a runner that never installed the pinned dep reported a
false-green census — CI installs ``graphifyy==0.9.67`` in every job that runs
these tests (``.github/workflows/ci.yml``), which makes a missing CLI a broken
environment, not a platform gate. The law now: a missing declared test dep is a
FAIL that names the dep, unless the operator sets the explicit opt-out
``DUCKWORK_ALLOW_SKIP_GRAPH_GATE=1`` (e.g. a deliberate no-graph lane).

Usage in a standalone PASS/FAIL test::

    from graph_gate_dep import graphify_dep_guard
    if (code := graphify_dep_guard("graph_check round-trip")) is not None:
        print("ALL PASS" if not fails else f"FAIL {fails}")
        sys.exit(code)

Returns None when the gate may run. Otherwise returns the exit code the caller
must propagate after printing its own ledger line: 1 and a FAIL line naming
``graphifyy`` (fail-closed, the default), or 0 and a SKIP line when the opt-out
env var is set.
"""
import os
import shutil

# The pinned dep is part of CI (see .github/workflows/ci.yml); keep this pin in
# sync with the workflow's `pip install graphifyy==...` line.
GRAPHIFY_PKG = "graphifyy==0.9.67"
OPT_OUT_ENV = "DUCKWORK_ALLOW_SKIP_GRAPH_GATE"


def graphify_dep_guard(gate_name):
    """None if graphify is on PATH; else the exit code (1 fail-closed, or 0 SKIP
    under the explicit opt-out) after printing the naming line."""
    if shutil.which("graphify"):
        return None
    naming = (f"missing declared test dep: graphify CLI ({GRAPHIFY_PKG}; "
              f"uv tool install graphifyy)")
    if os.environ.get(OPT_OUT_ENV) == "1":
        print(f"SKIP {gate_name} — {naming}; {OPT_OUT_ENV}=1 opt-out set")
        return 0
    print(f"FAIL {gate_name} — {naming}; "
          f"install it or set {OPT_OUT_ENV}=1 to opt out explicitly")
    return 1
