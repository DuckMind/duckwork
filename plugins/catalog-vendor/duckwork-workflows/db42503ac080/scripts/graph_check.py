#!/usr/bin/env python3
"""Graph drift gate: is the committed graphify-out/graph.json current for this tree?

Usage: python3 scripts/graph_check.py [--fix]

Runs `graphify update .` (AST only, no LLM, no network) from NOTHING into a scratch copy of
the tracked tree and compares the AST-derived node/edge SET with the committed graph.
Semantic nodes/edges (`_origin == "semantic"`, from the one LLM pass) are the graph's memory,
not the tree's truth: ignored by the comparison, carried over verbatim by `--fix`. Communities
are re-clustered locally (no LLM) and named from the committed `.graphify_labels.json` cache;
a brand-new community shows up as an unlabeled one → run `graphify label .` once (LLM) and
commit the cache. Ids graphify derives from the scratch path are normalised.

  exit 0  graph current
  exit 1  graph stale → prints the delta; `--fix` rewrites the committed graph in place
  exit 2  graphify not installed (uv tool install graphifyy) or no committed graph

WHY a gate and not auto-commit: the graph is a build product of the source; a stale
committed graph is a lie the agents will read. Making the contributor run one command
is cheaper than a bot commit racing every push.

CANONICAL MULTI-EDGE POLICY (#27). graphify 0.9.67 emits every (source, target, relation)
triple exactly once and its output is byte-deterministic for a given tree (measured: two
from-nothing runs, scratch prefix stripped, identical). The committed file nevertheless grew
3503 → 8300 edges over 12 regenerations while the distinct triples went 2823 → 3179: the old
`--fix` merge carried over every committed edge touching a "semantic" node, and all 45
semantic nodes are id-shadows of AST module nodes (os, pathlib, ...) whose edges the fresh
build already holds — +758 duplicate edge objects and +45 duplicate node ids per --fix.
The set-based comparison could not see it. No consumer distinguishes the copies: graphify
itself loads the file as a plain networkx Graph (the header says `"multigraph": false`),
GRAPH_REPORT.md/manifest.json are written from graphify's own build, and the only readers
in-tree (this gate, tests/test_graph_gate.py) look at sets and coarse sizes. So the canonical
form is the simplest one that keeps the gate honest:

  * one edge object per (source, target, relation); `count` = number of objects collapsed
    (summing prior counts, so normalising is a fixed point), written only when > 1 so a
    pristine extractor build normalises to itself byte-for-byte;
  * one node object per id; an AST node beats a `_origin: semantic` shadow of the same id;
  * `normalize()` runs on BOTH sides before the comparison and on the merged graph before
    `--fix` writes, and a committed graph that is not already its own normal form is STALE
    (`--fix` rewrites it) — the file converges instead of merely comparing green.
"""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "graphify-out"
GRAPH = OUT / "graph.json"


def _ast(x):
    return x.get("_origin") != "semantic"


def _norm(nid, scratch):
    # graphify keys root-level files it cannot classify (LICENSE) by the absolute path it was pointed
    # at: /tmp/x/tree/LICENSE -> tmp_x_tree_license_md. Strip the scratch prefix so ids are path-free.
    return nid[len(scratch):] if scratch and nid.startswith(scratch) else nid


def _edge_key(e):
    return e["source"], e["target"], e.get("relation", "")


def normalize(g):
    """Return a NEW graph dict in canonical form (see module docstring). Pure; input untouched.

    Nodes: first object per id wins unless it is a semantic shadow and an AST object follows.
    Edges: first object per (source, target, relation) wins its fields; `count` accumulates.
    Order of first appearance is preserved on both, so a duplicate-free graph round-trips
    byte-identically (`json.dumps(normalize(g)) == json.dumps(g)`)."""
    E = "links" if "links" in g else "edges"
    nodes, at = [], {}
    for n in g.get("nodes", []):
        i = n["id"]
        if i not in at:
            at[i] = len(nodes); nodes.append(dict(n))
        elif not _ast(nodes[at[i]]) and _ast(n):
            nodes[at[i]] = dict(n)
    edges, seen = [], {}
    for e in g.get(E, []):
        k = _edge_key(e)
        if k not in seen:
            seen[k] = len(edges); edges.append(dict(e))
        else:
            kept = edges[seen[k]]
            kept["count"] = kept.get("count", 1) + e.get("count", 1)
    for e in edges:
        if e.get("count", 1) <= 1: e.pop("count", None)
    out = {k: v for k, v in g.items() if k not in ("nodes", E)}
    out["nodes"] = nodes; out[E] = edges
    return out


def _dump(g):
    return json.dumps(g, indent=2) + "\n"


def sig(g, scratch=""):
    # A node is semantic only by its own marker. Module nodes (os, json) carry no _origin in either
    # build; treating "unmarked" as semantic hid 370 import edges from the comparison.
    nodes = {_norm(n["id"], scratch) for n in g["nodes"] if _ast(n)}
    edges = {(_norm(e["source"], scratch), _norm(e["target"], scratch), e.get("relation", ""))
             for e in g.get("links", g.get("edges", [])) if _ast(e)}
    return nodes, edges  # SETS of the canonical form; normalize() first so multiplicity cannot hide


def main():
    fix = "--fix" in sys.argv
    if not shutil.which("graphify"):
        print("graph_check: graphify not on PATH (uv tool install graphifyy)"); return 2
    pin = OUT / "VERSION"
    if pin.exists():  # extraction differs across graphify versions; compare only with the version that built the graph
        have = subprocess.run(["graphify", "--version"], capture_output=True, text=True).stdout.split()[-1]
        if have != pin.read_text().strip():
            print(f"graph_check: graphify {have} != pinned {pin.read_text().strip()} — uv tool install graphifyy=={pin.read_text().strip()}"); return 2
    if not GRAPH.exists():
        print(f"graph_check: no committed graph at {GRAPH}"); return 2
    committed_raw = json.loads(GRAPH.read_text())
    committed = normalize(committed_raw)
    canonical = committed == committed_raw  # structural: graphify's own formatting is not the gate's business

    with tempfile.TemporaryDirectory(prefix="graph-check-") as td:
        work = Path(td) / "tree"
        # Snapshot the WORKING TREE (tracked + staged + unstaged), not HEAD: the local
        # use is "did I regenerate after my edit", and that edit is usually not yet
        # committed. `git ls-files` honours .gitignore exactly like a contributor's checkout.
        work.mkdir()
        files = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-co", "--exclude-standard", "-z"],
                               capture_output=True, check=True).stdout.split(b"\0")
        for rel in files:
            if not rel or rel.startswith(b"graphify-out/"): continue
            src = ROOT / rel.decode()
            if not src.is_file(): continue
            dst = work / rel.decode(); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy(src, dst)
        # Build the GRAPH from nothing (seeding with the committed graph made the update incremental,
        # and an incremental update never drops a node whose source file is gone — ghost nodes
        # survived locally while a fresh CI runner flagged them). Seed ONLY the label cache: clustering
        # is local math (Leiden, ~3 s, no LLM) and the cached names give every community its label.
        (work / "graphify-out").mkdir(exist_ok=True)
        for name in (".graphify_labels.json", ".graphify_labels.json.sig"):
            if (OUT / name).exists():
                shutil.copy(OUT / name, work / "graphify-out" / name)
        r = subprocess.run(["graphify", "update", str(work), "--force"], capture_output=True, text=True,
                           env={**os.environ, "GRAPHIFY_NO_LLM": "1"})
        if r.returncode != 0:
            print(r.stdout[-1500:], r.stderr[-1500:]); print("graph_check: graphify update failed"); return 2
        fresh_path = work / "graphify-out" / "graph.json"
        fresh = normalize(json.loads(fresh_path.read_text()))

        scratch = re.sub(r"[^a-z0-9]+", "_", str(work).lower().strip("/")) + "_"
        cn, ce = sig(committed); fn, fe = sig(fresh, scratch)
        if cn == fn and ce == fe and canonical:
            print(f"graph_check: OK — {len(cn)} nodes, {len(ce)} edges match the tree"); return 0

        add_n = sorted(fn - cn); del_n = sorted(cn - fn)
        add_e = len(fe - ce); del_e = len(ce - fe)
        dup = "" if canonical else (f", committed file not canonical ({len(committed_raw['nodes'])}→{len(committed['nodes'])} nodes, "
                                    f"{len(committed_raw.get('links', committed_raw.get('edges', [])))}→{len(committed.get('links', committed.get('edges', [])))} edges)")
        print(f"graph_check: STALE — nodes +{len(add_n)} -{len(del_n)}, edges +{add_e} -{del_e}{dup}")
        for n in add_n[:12]: print(f"  + {n}")
        for n in del_n[:12]: print(f"  - {n}")
        if fix:
            # fresh AST build is the truth; the committed graph's semantic memory rides along:
            # semantic nodes the fresh build does not already produce, edges touching them
            # (endpoints must still exist), community labels. Then normalise, so the written
            # file is its own fixed point — the accretion of #27 came from appending carried-over
            # edges the fresh build already held.
            E = "links" if "links" in fresh else "edges"
            for n in fresh["nodes"]:
                n["id"] = _norm(n["id"], scratch)
            for e in fresh[E]:
                e["source"], e["target"] = _norm(e["source"], scratch), _norm(e["target"], scratch)
            fresh_ids = {n["id"] for n in fresh["nodes"]}
            keep_n = [n for n in committed["nodes"] if not _ast(n) and n["id"] not in fresh_ids]
            sem_ids = {n["id"] for n in keep_n}
            ids = fresh_ids | sem_ids
            keep_e = [e for e in committed.get(E, []) if (e["source"] in sem_ids or e["target"] in sem_ids)
                      and e["source"] in ids and e["target"] in ids]
            fresh["nodes"] += keep_n; fresh[E] += keep_e
            fresh_path.write_text(_dump(normalize(fresh)))
            for name in ("graph.json", "GRAPH_REPORT.md", "manifest.json"):
                src = work / "graphify-out" / name
                if src.exists(): shutil.copy(src, OUT / name)
            print("graph_check: rewrote graphify-out/{graph.json,GRAPH_REPORT.md,manifest.json} — commit them")
            return 0
        print("fix: python3 scripts/graph_check.py --fix   (or: graphify update .)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
