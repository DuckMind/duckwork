#!/usr/bin/env python3
"""DIAGRAM LAW v1 — the derived-diagram gate contracts (stdlib-only).

Laws under test:
 - L0 determinism: same graph bytes -> same candidate bytes (derive twice, equal).
 - L3 sidecar: a graph without its <name>.cards.json fails named, never silently.
 - L3/A3 counts injected, not typed: a bare digit in card text is refused with
   the token hint; an unknown {{token}} is refused closed.
 - L5 README derived: diagram_readme rebuilds the table byte-stably (idempotent).
 - A4 no twin rows: no shipped example is a copy of a foreign estate artifact
   under this PR's shape (frontier-review must NOT appear as an example graph).
 - --check is the CI freshness mode: byte-identical passes, drift exits 1.
"""
import json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "scripts", "graph_diagram.py")
ok = True
_n = 0


def check(name, cond, detail=""):
    global ok, _n
    _n += 1
    if cond:
        print(f"PASS {name}")
    else:
        ok = False
        print(f"FAIL {name} :: {detail[:200]}")


def run(args, cwd=ROOT):
    return subprocess.run([sys.executable, GEN] + args, cwd=cwd,
                          capture_output=True, text=True)


G = {"name": "gate-law", "description": "d",
     "nodes": [{"id": "a", "type": "agent", "goal": "do it"},
               {"id": "b", "type": "gate", "after": ["a"],
                "question": "ship?", "options": ["y", "n"]},
               {"id": "c", "type": "agent", "after": ["b"]}]}
CARDS = {"cards": [{"dot": "cyan", "title": "Why it works",
                    "items": ["entry -> hold -> act"]},
                   {"dot": "rose", "title": "Contract",
                    "items": ["{{nodes}} nodes, {{gates}} gates"]}]}

tmp = tempfile.mkdtemp(prefix="diagramlaw")
try:
    gp = os.path.join(tmp, "gate-law.json")
    cp = os.path.join(tmp, "gate-law.cards.json")
    json.dump(G, open(gp, "w"))
    json.dump(CARDS, open(cp, "w"))

    r1 = run([gp, "--out", tmp])
    check("L1 derive writes the candidate", r1.returncode == 0, r1.stderr)
    cand_path = os.path.join(tmp, "gate-law.candidate.json")
    b1 = open(cand_path, "rb").read() if os.path.exists(cand_path) else b""
    r2 = run([gp, "--out", tmp])
    b2 = open(cand_path, "rb").read() if os.path.exists(cand_path) else b""
    check("L0 determinism: same input, same bytes", bool(b1) and b1 == b2)
    cand = json.loads(b1 or b"{}")
    contract = json.dumps(cand.get("cards", []))
    check("A3 injection renders {{nodes}} -> 3", "3 nodes" in contract, contract)
    check("A3 injection renders {{gates}} -> 1", "1 gates" in contract, contract)

    r = run(["--check", gp, "--out", tmp])
    check("L6 --check passes on fresh bytes", r.returncode == 0, r.stderr)

    # typed digit refused
    bad = json.load(open(cp))
    bad["cards"][1]["items"][0] = "Nodes: 7, 3 gates"
    json.dump(bad, open(cp, "w"))
    r = run([gp, "--out", tmp])
    check("A3 bare digit in card refused", r.returncode != 0
          and "typed number" in (r.stderr + r.stdout), r.stderr)
    # unknown token refused
    bad["cards"][1]["items"][0] = "{{nonexistent}} nodes"
    json.dump(bad, open(cp, "w"))
    r = run([gp, "--out", tmp])
    check("A3 unknown token refused closed", r.returncode != 0
          and "unknown token" in (r.stderr + r.stdout), r.stderr)
    # drift: fresh candidate then mutate source graph, --check must go red
    good = json.load(open(cp))
    good["cards"][1]["items"][0] = "{{nodes}} nodes, {{gates}} gates"
    json.dump(good, open(cp, "w"))
    run([gp, "--out", tmp])
    G["nodes"].append({"id": "d", "type": "agent", "after": ["c"], "goal": "x"})
    json.dump(G, open(gp, "w"))
    r = run(["--check", gp, "--out", tmp])
    check("L6 --check red on graph drift", r.returncode != 0, "drift not caught")

    # missing sidecar named, not silent
    g2 = os.path.join(tmp, "no-cards.json")
    json.dump({"name": "no-cards", "nodes": [{"id": "a", "goal": "x"}]}, open(g2, "w"))
    r = run([g2, "--out", tmp])
    check("L3 missing cards sidecar fails named", r.returncode != 0
          and "no-cards.cards.json" in (r.stderr + r.stdout), r.stderr)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# repo-wide invariants over the shipped examples
r = run(["--check", "--all"])
check("L6 --check --all green on shipped bytes", r.returncode == 0, r.stderr)
twins = [p for p in os.listdir(os.path.join(ROOT, "examples", "review"))
         if "frontier" in p.lower()]
check("A4 no foreign-estate twin under examples/", not twins, str(twins))
r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "diagram_readme.py")],
                   cwd=ROOT, capture_output=True, text=True)
check("L5 README rebuild exits 0", r.returncode == 0, r.stderr)
check("L5 committed README is derived-current (no hand-edit, no staleness)",
      "UNCHANGED" in r.stdout, r.stdout + r.stderr)
r2 = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "diagram_readme.py")],
                    cwd=ROOT, capture_output=True, text=True)
check("L5 README rebuild idempotent", "UNCHANGED" in r2.stdout, r2.stdout)


# --- PR-3 contracts: vendored oven, spelled-numeral ban, QA-receipt-derived table
GEN_DIR = os.path.join(ROOT, "scripts", "vendor", "archify")

check("V1 vendored oven exists (recipe names no estate path)",
      os.path.isfile(os.path.join(GEN_DIR, "renderers", "workflow", "render-workflow.mjs"))
      and os.path.isfile(os.path.join(GEN_DIR, "assets", "template.html"))
      and os.path.isfile(os.path.join(GEN_DIR, "ARCHIFY_VERSION")))

import tempfile as _tf
with _tf.TemporaryDirectory() as _td:
    _rp = subprocess.run([shutil.which("node") or "node",
                          os.path.join(GEN_DIR, "renderers", "workflow", "render-workflow.mjs"),
                          os.path.join(ROOT, "examples", "diagrams", "smoke.candidate.json"),
                          os.path.join(_td, "a.html")],
                         capture_output=True, text=True, cwd=ROOT)
    _rp2 = subprocess.run([shutil.which("node") or "node",
                           os.path.join(GEN_DIR, "renderers", "workflow", "render-workflow.mjs"),
                           os.path.join(ROOT, "examples", "diagrams", "smoke.candidate.json"),
                           os.path.join(_td, "b.html")],
                          capture_output=True, text=True, cwd=ROOT)
    same = (_rp.returncode == 0 == _rp2.returncode
            and open(os.path.join(_td, "a.html"), "rb").read()
            == open(os.path.join(_td, "b.html"), "rb").read())
    check("V2 vendored renderer runs bare and is byte-deterministic", same,
          (_rp.stderr + _rp2.stderr)[:200])

# A3 spelled-numeral ban: word-count card refused, shape vocabulary accepted
with _tf.TemporaryDirectory() as _td:
    _g = json.loads(json.dumps(G))
    _c = json.loads(json.dumps(CARDS))
    _gp = os.path.join(_td, "w.json"); _cp = os.path.join(_td, "w.cards.json")
    json.dump(_g, open(_gp, "w"))
    _c["cards"][0]["items"][0] = "Smoke test in three nodes"
    json.dump(_c, open(_cp, "w"))
    r = run([_gp, "--out", _td])
    check("A3 spelled numeral refused like a digit",
          r.returncode != 0 and "spelled number" in (r.stderr + r.stdout), r.stderr)
    _c["cards"][0]["items"][0] = "Every one of the seats votes"
    json.dump(_c, open(_cp, "w"))
    r = run([_gp, "--out", _td])
    check("A3 'one' refused too (closed set, word-boundary)",
          r.returncode != 0 and "spelled number" in (r.stderr + r.stdout), r.stderr)
    _c["cards"][0]["items"][0] = "Seed fans out, lanes run, final joins"
    json.dump(_c, open(_cp, "w"))
    r = run([_gp, "--out", _td])
    check("A3 shape vocabulary still accepted", r.returncode == 0, r.stderr)

# shipped cards carry zero spelled counts (the enumeration is the receipt)
import re as _re
SPELL = _re.compile(r"(?<![A-Za-z])(zero|one|two|three|four|five|six|seven|eight|nine|ten"
                    r"|eleven|twelve|thirteen|fourteen|fifteen|twenty|thirty|forty|fifty|hundred)(?![A-Za-z])",
                    _re.IGNORECASE)
offenders = [os.path.relpath(p, ROOT)
             for dp, _, fs in os.walk(os.path.join(ROOT, "examples"))
             for f in fs if f.endswith(".cards.json")
             for p in [os.path.join(dp, f)] if SPELL.search(open(p, encoding="utf-8").read())]
check("A3 shipped cards enumerate zero spelled counts", not offenders, str(offenders))

# THE WALKER CONTRACT (born from austin's finding at 364ecf8: both walkers
# pruned the artifact dir by basename, so examples/diagrams/qa/*.qa.json walked
# in as phantom graphs — the queue contradicted the tree with CI green).
# Law: queue rows == graphs lacking a sidecar, by census; and no derived
# artifact (candidate, qa receipt, stray json) is ever counted as a graph.
import importlib.util as _ilu
_wspec = _ilu.spec_from_file_location(
    "graph_diagram_walker", os.path.join(ROOT, "scripts", "graph_diagram.py"))
_walk_mod = _ilu.module_from_spec(_wspec)
_wspec.loader.exec_module(_walk_mod)
_walk = _walk_mod.example_graphs
_dia = os.path.join(ROOT, "examples", "diagrams")
_walked = _walk(os.path.join(ROOT, "examples"), _dia)
check("WK1 walker counts no derived artifact as a graph",
      all(not os.path.abspath(f).startswith(os.path.abspath(_dia) + os.sep)
          for f in _walked),
      str([f for f in _walked if os.path.abspath(_dia) in os.path.abspath(f)][:3]))
_sidecar_less = [f for f in _walked
                 if not os.path.exists(_re.sub(r"\.json$", ".cards.json", f))
                 and not os.path.exists(os.path.join(
                     _dia, os.path.basename(f)[:-5] + ".candidate.json"))]
_tbl = open(os.path.join(_dia, "README.md")).read()
_queue = [ln for ln in _tbl.splitlines() if ln.startswith("- [ ] `")]
check("WK2 queue rows == sidecar-less graphs, by census",
      len(_queue) == len(_sidecar_less),
      f"queue {len(_queue)} vs census {len(_sidecar_less)}")
check("WK3 queue names no qa receipt or candidate",
      not [q for q in _queue if ".qa.json" in q or ".candidate.json" in q],
      str([q[:60] for q in _queue if ".qa.json" in q][:3]))
_stray = os.path.join(_dia, "decoy.json")
open(_stray, "w").write("{}")
try:
    _walk(os.path.join(ROOT, "examples"), _dia)
    check("WK4 unknown artifact under the out dir fails closed", False,
          "decoy.json walked in silently")
except SystemExit as e:
    check("WK4 unknown artifact under the out dir fails closed",
          "decoy.json" in str(e), str(e)[:120])
finally:
    os.remove(_stray)

# QA-receipt-derived gates: lying receipt -> named red; missing -> honest not-run
_readme_py = os.path.join(ROOT, "scripts", "diagram_readme.py")
_dia = os.path.join(ROOT, "examples", "diagrams")
_qa_dir = os.path.join(_dia, "qa")
_real = {f: open(os.path.join(_qa_dir, f), "rb").read()
         for f in os.listdir(_qa_dir) if f.endswith(".qa.json")}
try:
    _sp = os.path.join(_qa_dir, "smoke.qa.json")
    _lie = json.loads(_real["smoke.qa.json"]); _lie["expected_nodes"] = 99
    json.dump(_lie, open(_sp, "w"))
    r = subprocess.run([sys.executable, _readme_py], cwd=ROOT, capture_output=True, text=True)
    check("QR1 lying receipt (expected_nodes) refuses the rebuild, named",
          r.returncode != 0 and "QA RED smoke.qa.json" in (r.stderr + r.stdout),
          (r.stdout + r.stderr)[:200])
    os.remove(_sp)
    r = subprocess.run([sys.executable, _readme_py], cwd=ROOT, capture_output=True, text=True)
    _tbl = open(os.path.join(_dia, "README.md")).read()
    _smoke_row = next((ln for ln in _tbl.splitlines() if "smoke.png" in ln), "")
    check("QR2 missing receipt cannot claim receipted (honest not-run)",
          r.returncode == 0 and "WROTE" in r.stdout
          and "browser-check done" not in _smoke_row and "not-run" in _smoke_row,
          (r.stdout + r.stderr)[:200])
finally:
    for f, blob in _real.items():
        open(os.path.join(_qa_dir, f), "wb").write(blob)
    subprocess.run([sys.executable, _readme_py], cwd=ROOT, capture_output=True, text=True)

print(f"{'ALL PASS' if ok else 'FAILURES PRESENT'} ({_n} diagram-law contracts)")
sys.exit(0 if ok else 1)
