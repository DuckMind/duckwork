#!/usr/bin/env python3
"""graph_check.py contract: committed graph ⇔ tree, both directions, plus the shipped
graph's shape. Hermetic: builds a throwaway git repo. The graphify CLI is a DECLARED
test dep (CI installs graphifyy==0.9.67): absent CLI FAILS the gate naming the dep —
it only SKIPs (exit 0) under the explicit operator opt-out DUCKWORK_ALLOW_SKIP_GRAPH_GATE=1."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

from graph_gate_dep import graphify_dep_guard

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
fails = 0


def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    fails += 0 if ok else 1


# --- shipped graph shape (no graphify needed) -------------------------------------
g = json.loads((ROOT / "graphify-out" / "graph.json").read_text())
edges = g.get("links", g.get("edges", []))
check("shipped graph has nodes and edges", len(g["nodes"]) > 500 and len(edges) > 1000,
      f"{len(g['nodes'])} nodes / {len(edges)} edges")
names = {n.get("community_name") for n in g["nodes"]}
placeholder = [x for x in names if not x or x.startswith("Community ")]
check("every community carries a real label (no 'Community N' placeholders)", not placeholder, str(placeholder[:3]))
src = {n.get("source_file") for n in g["nodes"] if n.get("source_file")}
check("graph covers the door, runner, read model and desktop half",
      {"__init__.py", "wf.py", "wfcommon.py", "desktop/plugin.js"} <= src)
check("graph does not index itself or CI", not any(s.startswith(("graphify-out/", ".github/")) for s in src))
tracked = set(subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True).stdout.split())
orphans = sorted(s for s in src if s not in tracked)
check("every file the graph indexes is tracked in THIS tree (public graph built from public tree)",
      not orphans, str(orphans[:5]))
ignored = (ROOT / ".gitignore").read_text()
check(".gitignore keeps viz/cache/cost out of the repo",
      all(k in ignored for k in ("graphify-out/graph.html", "graphify-out/cache/", "graphify-out/cost.json")))

# --- the gate itself ---------------------------------------------------------------
_guard = graphify_dep_guard("graph_check round-trip")
if _guard is not None:
    fails += _guard  # fail-closed: a missing declared dep is a red, not a silent skip
    print("ALL PASS" if not fails else f"FAIL {fails}")
    sys.exit(1 if fails else 0)

with tempfile.TemporaryDirectory(prefix="gc-test-") as td:
    repo = Path(td) / "repo"
    repo.mkdir()
    (repo / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "graph_check.py", repo / "scripts" / "graph_check.py")
    (repo / "a.py").write_text("def alpha():\n    return beta()\n\ndef beta():\n    return 1\n")
    (repo / ".gitignore").write_text("graphify-out/graph.html\ngraphify-out/cache/\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], check=True)
    env = {**os.environ, "GRAPHIFY_NO_LLM": "1"}

    r = subprocess.run([PY, "scripts/graph_check.py"], cwd=repo, capture_output=True, text=True, env=env)
    check("no committed graph → exit 2", r.returncode == 2, r.stdout.strip()[-120:])

    subprocess.run(["graphify", "update", str(repo), "--force"], capture_output=True, env=env)
    r = subprocess.run([PY, "scripts/graph_check.py"], cwd=repo, capture_output=True, text=True, env=env)
    check("fresh graph → OK exit 0", r.returncode == 0 and "OK" in r.stdout, r.stdout.strip()[-160:])

    (repo / "a.py").write_text("def alpha():\n    return beta()\n\ndef beta():\n    return gamma()\n\ndef gamma():\n    return 2\n")
    r = subprocess.run([PY, "scripts/graph_check.py"], cwd=repo, capture_output=True, text=True, env=env)
    check("edited source, old graph → STALE exit 1 naming the new symbol",
          r.returncode == 1 and "STALE" in r.stdout and "gamma" in r.stdout, r.stdout.strip()[-200:])

    r = subprocess.run([PY, "scripts/graph_check.py", "--fix"], cwd=repo, capture_output=True, text=True, env=env)
    r2 = subprocess.run([PY, "scripts/graph_check.py"], cwd=repo, capture_output=True, text=True, env=env)
    check("--fix rewrites, then gate is OK again", r.returncode == 0 and r2.returncode == 0 and "OK" in r2.stdout,
          (r.stdout + r2.stdout).strip()[-200:])

print("ALL PASS" if not fails else f"FAIL {fails}")
sys.exit(1 if fails else 0)
