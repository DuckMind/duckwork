#!/usr/bin/env python3
"""#27 regression pin: graph_check's canonical multi-edge policy.

graphify-out/graph.json grew 3503 → 8300 edges over 12 `--fix` regenerations while the distinct
(source, target, relation) triples went 2823 → 3179 — the old merge path re-appended carried-over
edges the fresh build already held, and the SET comparison could not see it. This pins:

  1. normalize() collapses a duplicated (source, target, relation) triple to ONE edge with count=2,
     drops shadow node ids (AST beats semantic), and is a fixed point / identity on clean input;
  2. the pinned extractor path run twice yields BYTE-IDENTICAL normalised output, and `--fix` twice
     yields a byte-identical committed file (converges, does not accrete);
  3. dedupe does not blind the gate: an edge removed from the committed copy is still STALE, and
     a committed file that is not its own normal form is STALE even when the sets match.

Standalone (no pytest). Parts 2/3b need the graphify CLI, a DECLARED test dep
(CI installs graphifyy==0.9.67): absent CLI FAILS naming the dep — it only SKIPs
under the explicit opt-out DUCKWORK_ALLOW_SKIP_GRAPH_GATE=1."""
import importlib.util, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

from graph_gate_dep import graphify_dep_guard

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
fails = 0


def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    fails += 0 if ok else 1


spec = importlib.util.spec_from_file_location("graph_check", ROOT / "scripts" / "graph_check.py")
gc = importlib.util.module_from_spec(spec); spec.loader.exec_module(gc)

# --- 1. synthetic normalisation -------------------------------------------------------------
E = lambda s, t, r, **kw: {"source": s, "target": t, "relation": r, "_origin": "ast", "weight": 1.0, **kw}
N = lambda i, **kw: {"id": i, "label": i, **kw}
dup = {"directed": True, "multigraph": False, "graph": {}, "hyperedges": [],
       "nodes": [N("a"), N("os"), N("os", _origin="semantic"), N("b")],
       "links": [E("a", "os", "imports"), E("a", "b", "calls"), E("a", "os", "imports"), E("b", "os", "imports_from")]}
before = json.dumps(dup, sort_keys=True)
n = gc.normalize(dup)
check("input untouched", json.dumps(dup, sort_keys=True) == before)
check("duplicated (from,to,type) triple → one edge with count=2",
      [e for e in n["links"] if (e["source"], e["target"], e["relation"]) == ("a", "os", "imports")] == [E("a", "os", "imports", count=2)],
      json.dumps(n["links"]))
check("singleton edges carry no count field", all("count" not in e for e in n["links"] if e["source"] != "a" or e["target"] != "os"))
check("edge order = first appearance", [(e["source"], e["target"]) for e in n["links"]] == [("a", "os"), ("a", "b"), ("b", "os")])
check("shadow node id collapsed, AST copy wins over semantic", [x["id"] for x in n["nodes"]] == ["a", "os", "b"]
      and all(x.get("_origin") != "semantic" for x in n["nodes"]))
sem_first = dict(dup, nodes=[N("os", _origin="semantic"), N("os"), N("a")])
check("AST copy wins even when the semantic shadow comes first",
      gc.normalize(sem_first)["nodes"][0] == N("os"))
check("count sums on re-normalisation (fixed point)", gc.normalize(n) == n
      and gc.normalize({"nodes": [], "links": [E("a", "b", "x", count=2), E("a", "b", "x", count=3)]})["links"][0]["count"] == 5)
clean = {"directed": True, "multigraph": False, "graph": {}, "hyperedges": [], "nodes": [N("a"), N("b")], "links": [E("a", "b", "calls")]}
check("clean graph normalises to itself byte-for-byte", gc._dump(gc.normalize(clean)) == gc._dump(clean))
check("'edges' key honoured too", gc.normalize({"nodes": [], "edges": [E("a", "b", "x"), E("a", "b", "x")]})["edges"][0]["count"] == 2)
# 3a. sig() over the normal form still sees a missing edge (pure python, no graphify)
mut = json.loads(json.dumps(n)); mut["links"].pop(1)
check("sig() of a copy with one edge removed differs (dedupe does not blind the set comparison)",
      gc.sig(n)[1] - gc.sig(mut)[1] == {("a", "b", "calls")})
# the shipped file is canonical
shipped_raw = json.loads((ROOT / "graphify-out" / "graph.json").read_text())
check("committed graphify-out/graph.json is its own normal form (no duplicate triples, no shadow ids)",
      gc.normalize(shipped_raw) == shipped_raw,
      f"{len(shipped_raw['nodes'])} nodes / {len(shipped_raw['links'])} edges raw vs "
      f"{len(gc.normalize(shipped_raw)['nodes'])} / {len(gc.normalize(shipped_raw)['links'])} normalised")

# --- 2/3b. the pinned extractor path, hermetic repo ------------------------------------------
_guard = graphify_dep_guard("extractor idempotency + gate round-trip")
if _guard is not None:
    fails += _guard  # fail-closed: a missing declared dep is a red, not a silent skip
    print("ALL PASS" if not fails else f"FAIL {fails}")
    sys.exit(1 if fails else 0)

SRC = "import os\nimport os\nfrom os import path\n\ndef alpha():\n    return beta() + beta()\n\ndef beta():\n    return os.getcwd()\n"
env = {**os.environ, "GRAPHIFY_NO_LLM": "1"}


def mkrepo(td):
    repo = Path(td) / "repo"; repo.mkdir(); (repo / "scripts").mkdir()
    shutil.copy(ROOT / "scripts" / "graph_check.py", repo / "scripts" / "graph_check.py")
    (repo / "a.py").write_text(SRC)
    (repo / ".gitignore").write_text("graphify-out/graph.html\ngraphify-out/cache/\n")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], check=True)
    return repo


def gate(repo, *args):
    return subprocess.run([PY, "scripts/graph_check.py", *args], cwd=repo, capture_output=True, text=True, env=env)


def strip(g, scratch):
    for x in g["nodes"]: x["id"] = gc._norm(x["id"], scratch)
    for e in g["links"]: e["source"], e["target"] = gc._norm(e["source"], scratch), gc._norm(e["target"], scratch)
    return g


import re
outs = []
for _ in range(2):  # two from-nothing extractor runs in two scratch dirs, exactly the gate's path:
    with tempfile.TemporaryDirectory(prefix="dedupe27-") as td:  # a plain tree, NOT a git repo (graphify
        tree = Path(td) / "tree"; tree.mkdir(); (tree / "a.py").write_text(SRC)  # stamps built_at_commit otherwise)
        r = subprocess.run(["graphify", "update", str(tree), "--force"], capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr[-800:]
        scratch = re.sub(r"[^a-z0-9]+", "_", str(tree).lower().strip("/")) + "_"
        outs.append(gc._dump(gc.normalize(strip(json.loads((tree / "graphify-out" / "graph.json").read_text()), scratch))))
check("pinned extractor run twice → normalised output BYTE-IDENTICAL", outs[0] == outs[1])
check("extractor output has edges", '"links": [\n    {' in outs[0])

with tempfile.TemporaryDirectory(prefix="dedupe27-") as td:
    repo = mkrepo(td); gp = repo / "graphify-out" / "graph.json"
    subprocess.run(["graphify", "update", str(repo), "--force"], capture_output=True, env=env, check=True)
    r = gate(repo); check("fresh graph → OK", r.returncode == 0 and "OK" in r.stdout, r.stdout[-200:])
    # 3b. drop a real edge from the committed copy: the gate must still FAIL
    g = json.loads(gp.read_text()); victim = next(e for e in g["links"] if e["relation"] == "calls"); g["links"].remove(victim)
    gp.write_text(gc._dump(g))
    r = gate(repo); check("committed copy with one edge removed → STALE exit 1 (dedupe does not blind the checker)",
                          r.returncode == 1 and "edges +1 -0" in r.stdout, r.stdout[-200:])
    r = gate(repo, "--fix"); check("--fix restores it", r.returncode == 0 and gate(repo).returncode == 0)
    # accretion itself is now STALE even though the sets are equal
    g = json.loads(gp.read_text()); g["links"].append(dict(g["links"][0])); g["nodes"].append(dict(g["nodes"][0], _origin="semantic"))
    gp.write_text(gc._dump(g))
    r = gate(repo); check("duplicated triple + shadow node in committed file → STALE (not canonical) even with equal sets",
                          r.returncode == 1 and "not canonical" in r.stdout, r.stdout[-200:])
    # --fix converges: two --fix passes produce a byte-identical file, no growth
    r = gate(repo, "--fix"); b1 = gp.read_bytes()
    (repo / "a.py").write_text(SRC + "\ndef gamma():\n    return alpha()\n")
    r = gate(repo, "--fix"); b2 = gp.read_bytes()
    r = gate(repo, "--fix"); b3 = gp.read_bytes()
    n1, n2 = json.loads(b1), json.loads(b2)
    check("--fix after an edit adds exactly the new node/edges (no accretion)",
          len(n2["nodes"]) == len(n1["nodes"]) + 1 and len(n2["links"]) - len(n1["links"]) in (1, 2, 3),
          f"{len(n1['nodes'])}/{len(n1['links'])} → {len(n2['nodes'])}/{len(n2['links'])}")
    check("second --fix on an unchanged tree is BYTE-IDENTICAL", b2 == b3)
    check("written file is its own normal form", gc.normalize(n2) == n2)
    check("gate OK after --fix", gate(repo).returncode == 0)

print("ALL PASS" if not fails else f"FAIL {fails}")
sys.exit(1 if fails else 0)
