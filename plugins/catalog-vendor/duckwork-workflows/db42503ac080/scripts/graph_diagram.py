#!/usr/bin/env python3
"""DIAGRAM LAW v1 — derive archify workflow candidates from shipped example graphs.

Stdlib-only, deterministic: same graph bytes -> same candidate bytes.
The candidate JSON is the gate artifact; html/png are rendered from it with
archify (`node archify finalize workflow <candidate> <html> --quality standard`).

Usage (from repo root):
  python3 scripts/graph_diagram.py examples/basics/approve-publish.json
  python3 scripts/graph_diagram.py --all
  python3 scripts/graph_diagram.py --check --all   # CI freshness gate; exit 1 on drift
  python3 scripts/graph_diagram.py --header        # print this file (one-source law)

Each graph <name>.json needs a sibling <name>.cards.json — the ONLY human-authored
input — holding exactly two cards: {"cards":[{"dot":"cyan","title":...,"items":[...]},
{"dot":"rose","title":...,"items":[...]}]}. Card counts are INJECTED via {{tokens}}
only (§3/A3): a bare digit or unknown token fails the generator closed.

LAYOUT RULE (§2 as amended in-thread 2026-10-06; this paragraph IS the spec — the
diagram lying about its graph is a bug in THIS file, named defendant):
  lane  = actor class from the node's `type` key: agent -> "work" (Agents),
          gate -> "gates" (Gates), echo -> "room" (Deterministic).
          Model pins are NEVER consulted (they ride the seat and change more often
          than the shape; a pin edit must not re-draw a diagram).
  col   = longest-path depth from roots, capped at 5.
  stack = nodes sharing (lane, col) get yOffset = tier * STACK.
Edges emit one per (dep, node) `after` pair — no bundle idiom exists in archify;
branch edges carry variant "security". The compared bytes are candidate.json
(canonical: json.dumps sort_keys, indent 2, trailing newline); png is a stamp
record in the README table, never re-rastered in CI (§4 as amended).
"""
import argparse, hashlib, json, os, re, sys

ACTOR = {"agent": "backend", "gate": "security", "echo": "messagebus"}
WIDTH = 104
STACK = 92


def sha256_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def slug(s):
    return re.sub(r"[^a-zA-Z0-9_]", "-", s or "x")


def phrase(s, n=4):
    # sublabel fit law: at node width 104 the text box is 96px; the compiler
    # measures the 6px sublabel ~4.2px/char — pack whole words up to 20 chars.
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", s or "") if p]
    out = ""
    for p in parts[:n]:
        cand = (out + " " + p).strip()
        if len(cand) > 20 and out:
            break
        out = cand
    return out.lower()


def fit_label(s, budget=14):
    # label fit law: the compiler measures labels ~6.8px/char; keep whole
    # words inside budget-1 and fail over to an ellipsis, never mid-word
    # unless the word itself splits the budget with >=4 visible chars.
    s = s.strip()
    if len(s) <= budget:
        return s
    out = ""
    for w in s.split(" "):
        cand = (out + " " + w).strip()
        if len(cand) <= budget - 1:
            out = cand
        else:
            room = budget - len(out) - 2
            if room >= 4:
                out = (out + " " + w[:room]).strip()
            break
    return out + "…"


def depth_map(nodes):
    by_id = {n["id"]: n for n in nodes}
    depth = {}

    def d(nid, seen):
        if nid in depth:
            return depth[nid]
        if nid in seen:
            raise SystemExit(f"cycle at {nid}")
        deps = by_id[nid].get("after") or []
        depth[nid] = 0 if not deps else 1 + max(d(x, seen | {nid}) for x in deps)
        return depth[nid]

    for n in nodes:
        d(n["id"], frozenset())
    return depth


def derive(graph, cards, rel_graph):
    nodes = graph["nodes"]
    depth = depth_map(nodes)
    maxc = min(max(depth.values()), 5)

    lane_defs = (("work", "Agents"), ("gates", "Gates"), ("room", "Deterministic"))
    lanes = [{"id": lid, "label": lab, "variant": "normal"}
             for lid, lab in lane_defs
             if any(({"agent": "work", "gate": "gates", "echo": "room"}
                     .get(n.get("type", "agent"), "work")) == lid for n in nodes)]

    out_nodes, stacked = [], {}
    for n in sorted(nodes, key=lambda x: (min(depth[x["id"]], 5), x["id"])):
        t = n.get("type", "agent")
        lane = {"agent": "work", "gate": "gates", "echo": "room"}[t]
        col = min(depth[n["id"]], 5)
        cell = (lane, col)
        node = {"id": slug(n["id"]), "lane": lane, "col": col,
                "type": ACTOR.get(t, "backend"),
                "label": fit_label(re.sub(r"[_-]", " ", n["id"]).strip().title()),
                "width": WIDTH}
        tier = stacked.get(cell, 0)
        if tier:
            node["yOffset"] = tier * STACK
        stacked[cell] = tier + 1
        goal = n.get("goal") or n.get("question") or ""
        if t == "gate":
            if n.get("wait"):
                node["tag"] = "machine hold"
                node["sublabel"] = phrase(n["wait"].get("until_argv", ["poll"])[0]
                                          if isinstance(n.get("wait"), dict) and n["wait"].get("until_argv")
                                          else f"every {n['wait'].get('every_s', '?')}s"
                                          if isinstance(n.get("wait"), dict) else "timed wait", 3)
            else:
                node["tag"] = "human hold"
                node["sublabel"] = phrase(n.get("question") or goal, 4)
            if n.get("when"):
                node["tag"] = "branch"
        elif goal:
            node["sublabel"] = phrase(goal, 4)
        fo = n.get("fanout") or {}
        if fo:
            node["tag"] = ("quorum " if fo.get("quorum") is not None else "") + \
                          f"fan-out {len(fo.get('items', [])) or 'N'}"
        out_nodes.append(node)

    edges = []
    for n in nodes:
        for dep in (n.get("after") or []):
            e = {"id": f"{slug(dep)}-{slug(n['id'])}", "from": slug(dep),
                 "to": slug(n["id"]), "variant": "default"}
            if n.get("when"):
                e["variant"] = "security"
            edges.append(e)

    phases = [{"id": "roots", "label": "entry", "fromCol": 0, "toCol": 0}]
    if maxc >= 2:
        phases.append({"id": "mid", "label": "hand-offs",
                       "fromCol": 1, "toCol": max(1, maxc - 1)})
    phases.append({"id": "out", "label": "terminus", "fromCol": maxc, "toCol": maxc})

    name = graph.get("name") or os.path.basename(rel_graph)
    cand = {
        "schema_version": 2, "diagram_type": "workflow",
        "meta": {"title": name, "subtitle": (graph.get("description") or "")[:110],
                 "quality_profile": "standard",
                 "output": f"examples/diagrams/{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')}.html"},
        "lanes": lanes, "phases": phases, "nodes": out_nodes, "edges": edges,
        "cards": cards,
    }
    return cand


def cards_for(graph_path):
    p = re.sub(r"\.json$", ".cards.json", graph_path)
    if not os.path.exists(p):
        raise SystemExit(f"MISSING {p}: author the two human cards first (DIAGRAM LAW 3)")
    cards = json.load(open(p))["cards"]
    if len(cards) != 2:
        raise SystemExit(f"{p}: exactly two cards, got {len(cards)}")
    for c in cards:
        if len(c.get("items", [])) > 4:
            raise SystemExit(f"{p}: card '{c.get('title')}' over 4 bullets")
    return cards


# A3 (DIAGRAM LAW 3 amendment): counts are INJECTED, not typed. Card items may
# reference computed values only via {{tokens}}; any bare digit is a drift vector
# and fails the gate. Allowed tokens are computed by counts_for().
# Spelled numerals are the same crime in the other alphabet: a prose "three
# nodes" survives every mutation of the graph it describes (peer cold-read
# receipt at 6454b50: a mutant 4-node smoke kept saying "three nodes", exit
# 0). Vocabulary lines carry SHAPE, never counts, in either
# script — the word list is the small closed set; deletion beats tokenizing.
def example_graphs(examples_dir, out_dir):
    """The ONE walker for shipped example graphs — shared by --all here and
    diagram_readme.py's table (one-source law; the README builder imports it).

    Everything under out_dir is an ARTIFACT, never a graph: candidates, pngs,
    the derived README, and qa/ receipts. Receipts are *.json too, and the
    original basename-only exclusion let qa/<stem>.qa.json walk in as phantom
    pending graphs (the queue contradicted the tree with CI green — austin's
    finding at 364ecf8). Exclusion is therefore by PATH PREFIX, and the
    artifact set is fail-closed: any other .json under out_dir names itself
    and fails, so an unknown artifact can never masquerade as a graph.
    """
    ex, out = os.path.abspath(examples_dir), os.path.abspath(out_dir)
    files = []
    for dp, _, fs in os.walk(ex):
        dp = os.path.abspath(dp)
        if dp == out or dp.startswith(out + os.sep):
            for f in fs:
                artifact = (f.endswith(".candidate.json")
                            or (os.path.basename(dp) == "qa"
                                and f.endswith(".qa.json")))
                if f.endswith(".json") and not artifact:
                    raise SystemExit(f"unknown artifact under {out}: {f} —"
                                     " artifacts are *.candidate.json or"
                                     " qa/*.qa.json; graphs live OUTSIDE the"
                                     " out dir (DIAGRAM LAW: derived files"
                                     " cannot pose as inputs)")
            continue
        for f in fs:
            if f.endswith(".json") and not f.endswith(".cards.json"):
                files.append(os.path.join(dp, f))
    return sorted(files)


COUNT_TOKEN = re.compile(r"\{\{(\w+)\}\}")
BARE_DIGIT = re.compile(r"(?<!\{)\d(?!\})")
SPELLED_NUM = re.compile(
    r"(?<![A-Za-z])(zero|one|two|three|four|five|six|seven|eight|nine|ten"
    r"|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen"
    r"|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)(?![A-Za-z])",
    re.IGNORECASE)


def counts_for(graph):
    ns = graph["nodes"]
    return {
        "nodes": len(ns),
        "gates": sum(1 for n in ns if n.get("type") == "gate"),
        "agents": sum(1 for n in ns if n.get("type", "agent") == "agent"),
        "echoes": sum(1 for n in ns if n.get("type") == "echo"),
        "fanouts": sum(1 for n in ns if n.get("fanout")),
        "edges": sum(len(n.get("after") or []) for n in ns),
        "branches": sum(1 for n in ns if n.get("when")),
    }


def inject(cards, counts):
    def fill(s):
        bad = BARE_DIGIT.search(s)
        if bad:
            raise SystemExit(f"DIAGRAM LAW 3/A3: typed number in card item "
                             f"(use {{{{token}}}}): ...{s[max(0,bad.start()-25):bad.start()+15]}...")
        spelled = SPELLED_NUM.search(s)
        if spelled:
            raise SystemExit(f"DIAGRAM LAW 3/A3: spelled number '{spelled.group(0)}' in card item "
                             f"— shape vocabulary, no counts in either script: "
                             f"...{s[max(0,spelled.start()-25):spelled.start()+15]}...")
        unknown = [t for t in COUNT_TOKEN.findall(s) if t not in counts]
        if unknown:
            raise SystemExit(f"DIAGRAM LAW 3/A3: unknown token(s) {unknown} in card item: {s[:60]}")
        return COUNT_TOKEN.sub(lambda m: str(counts[m.group(1)]), s)
    return [{"dot": c["dot"], "title": fill(c["title"]),
             "items": [fill(i) for i in c["items"]]} for c in cards]


def main():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("graphs", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default=os.path.join("examples", "diagrams"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--header", action="store_true")
    a = ap.parse_args()
    if a.header:
        sys.stdout.write(open(os.path.abspath(__file__)).read())
        return 0
    files = list(a.graphs)
    if a.all:
        files = example_graphs(os.path.join(here, "examples"),
                               os.path.join(here, a.out))
    bad = 0
    pending = []
    for f in files:
        f = f if os.path.isabs(f) else os.path.join(here, f)
        graph = json.load(open(f))
        if not os.path.exists(re.sub(r"\.json$", ".cards.json", f)):
            out_pre = os.path.join(here, a.out, os.path.basename(f)[:-5] + ".candidate.json")
            if a.all and not a.graphs and not os.path.exists(out_pre):
                pending.append(f)           # split in flight: pending, not broken
                continue
            raise SystemExit(f"MISSING {re.sub(r'.json$', '.cards.json', f)}: author the two human cards first (DIAGRAM LAW 3)"
                             + (f" — or delete the orphan {out_pre}" if os.path.exists(out_pre) else ""))
        cand = derive(graph, inject(cards_for(f), counts_for(graph)), os.path.relpath(f, here))
        blob = json.dumps(cand, indent=2, sort_keys=True) + "\n"
        out = os.path.join(here, a.out, os.path.basename(f)[:-5] + ".candidate.json")
        if a.check:
            have = open(out).read() if os.path.exists(out) else ""
            if have != blob:
                print(f"DRIFT {out}: derived bytes differ from committed (rerun: python3 scripts/graph_diagram.py --all)")
                bad += 1
            continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, "w").write(blob)
        print(f"WROTE {out}")
    for f in pending:
        print(f"PENDING {os.path.relpath(f, here)} (cards sidecar not yet authored)")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
