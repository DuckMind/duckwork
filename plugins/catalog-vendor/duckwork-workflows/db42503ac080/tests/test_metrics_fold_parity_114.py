#!/usr/bin/env python3
"""#114 dual-surface fold parity contract (test-only — RED on unfixed main by design).

The invariant this file locks (R2: an absent count reads unknown, never invented):
across the fixture grid and EVERY aggregation level, the door's
``act_status(detail="full")`` and the dashboard's ``_view(r, full=True)`` must AGREE
— a level carries an exact numeric ``api_calls`` on both surfaces with the SAME
value, or the key is absent on both — and no level ever reports a numeric
``api_calls`` (0 or a partial sum) as exact while any contributing child says
``api_calls_known: false``. Fan-out ``item_metrics`` exists only on the dashboard
surface, so its rule is the same numeric-or-absent contract driven from the shared
fixture rows.

R8 sibling completeness — the complete fold call set (re-verified at this base):
  - door:      __init__.py act_status per-node line fold + run total (~:3010-3037);
  - dashboard: dashboard/plugin_api.py _view -> _fold_metrics at the node line
               (~:163), fan-out item_metrics (~:169) and the run rollup (~:175);
  - no third fold: `grep -rn 'api_calls|child_metrics|_fold' scripts/` is EMPTY
               (rc=1, re-verified at 2d97807 and at this base).
Every fold is driven through the identical grid; each drives the SAME seeded
sessions rows (NULL api_call_count = the issue's {api_calls: 0,
api_calls_known: false} shape). Assertions ride the returned dicts only, never
helper names (R6). Mergeable only alongside the item-1 fold-helper fix PR.
"""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCRATCH = tempfile.TemporaryDirectory(prefix="wf114-parity-")
HOME = Path(_SCRATCH.name) / "home"
RUNS = HOME / "workflows"
# #71/#42 law: pin BOTH resolvers before the door/dashboard exec-load their
# sibling wfcommon — an inherited lane WF_RUNS_ROOT outranks DUCKWORK_HOME and is
# exactly the leak tests/fixtures/wf_spawn_isolation_762.py exists to kill.
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(RUNS)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


door = _load("parity114_door", ROOT / "__init__.py")
api = _load("parity114_dashboard", ROOT / "dashboard" / "plugin_api.py")
for _m in {id(door._common): door._common,
           id(api._workflow_common()): api._workflow_common()}.values():
    _m.duckwork_home = lambda: HOME   # children's state.db = the scratch seat (904f pattern)

ABSENT = "ABSENT"   # the omission convention: the api_calls key is absent on this surface

SESSION_TABLE = ("create table sessions (title text, model text, input_tokens int, output_tokens int,"
                 " cache_read_tokens int, reasoning_tokens int, api_call_count int,"
                 " tool_call_count int, estimated_cost_usd real, last_activity_at real,"
                 " last_activity_description text, ended_at real, started_at real)")


def agent(nid, items=None):
    node = {"id": nid, "type": "agent", "goal": f"do {nid}"}
    if items:
        node["fanout"] = {"items": items, "goal": "{item}"}
    return node


def skey(rid, nid, item=None):
    tail = f"{item}:abcd.1111" if item is not None else "abcd.1111"
    return f"wf:{rid}:{nid}:{tail}#a0"


# rows: (node, fanout_item_or_None, tokens_in, tokens_out, api_calls_or_None, tools)
# api_calls None = the column is NULL = the row says api_calls_known:false (the issue's
# child_metrics shape {'api_calls': 0, 'api_calls_known': False}).
# expect keys: ("node", nid) | ("run", None) | ("item", (nid, i)) -> int | ABSENT.
GRID = [
    {"case": "issue fixture (divergence table verbatim)", "run": "t114issue",
     "nodes": [agent("solo")],
     "rows": [("solo", None, 12, 3, None, 1)],
     "expect": {("node", "solo"): ABSENT, ("run", None): ABSENT}},
    {"case": "all-unknown (every contributing child unknown)", "run": "t114allunk",
     "nodes": [agent("solo"), agent("other")],
     "rows": [("solo", None, 10, 5, None, 1), ("other", None, 20, 7, None, 2)],
     "expect": {("node", "solo"): ABSENT, ("node", "other"): ABSENT, ("run", None): ABSENT}},
    {"case": "mixed known+unknown (never a partial sum as exact)", "run": "t114mix",
     "nodes": [agent("solo"), agent("other")],
     "rows": [("solo", None, 10, 5, 5, 1), ("other", None, 20, 7, None, 2)],
     "expect": {("node", "solo"): 5, ("node", "other"): ABSENT, ("run", None): ABSENT}},
    {"case": "all-known (exact numbers preserved today and after the fold helper)", "run": "t114known",
     "nodes": [agent("solo"), agent("other")],
     "rows": [("solo", None, 10, 6, 5, 1), ("other", None, 20, 8, 7, 2)],
     "expect": {("node", "solo"): 5, ("node", "other"): 7, ("run", None): 12}},
    {"case": "known-zero (a real 0 stays numeric 0 on every level)", "run": "t114zero",
     "nodes": [agent("solo"), agent("other")],
     "rows": [("solo", None, 10, 6, 0, 1), ("other", None, 20, 8, 0, 2)],
     "expect": {("node", "solo"): 0, ("node", "other"): 0, ("run", None): 0}},
    {"case": "fan-out mixed (item level rides the same rule)", "run": "t114fanmix",
     "nodes": [agent("fan", ["x", "y"])],
     "rows": [("fan", 0, 10, 4, 4, 1), ("fan", 1, 20, 6, None, 2)],
     "expect": {("node", "fan"): ABSENT, ("run", None): ABSENT,
                ("item", ("fan", 0)): 4, ("item", ("fan", 1)): ABSENT}},
]


class FoldParity114(unittest.TestCase):
    def make_run(self, case):
        HOME.mkdir(parents=True, exist_ok=True)
        rid, nodes = case["run"], case["nodes"]
        r = RUNS / rid
        (r / "nodes").mkdir(parents=True, exist_ok=True)
        (r / "graph.json").write_text(json.dumps({"name": rid, "nodes": nodes}))
        (r / "run.json").write_text("{}")
        byid = {n["id"]: n for n in nodes}
        for n in nodes:
            (r / "nodes" / f"{n['id']}.json").write_text(
                json.dumps({"status": "done", "efp": door.efp(byid, n), "output": {"answer": "ok"}}))
        with closing(sqlite3.connect(HOME / "state.db")) as c:
            try:
                c.execute(SESSION_TABLE)
            except sqlite3.OperationalError:
                pass          # table survives from an earlier case; the delete below isolates
            c.execute("delete from sessions")
            c.executemany(
                "insert into sessions (title, model, input_tokens, output_tokens, api_call_count,"
                " tool_call_count, estimated_cost_usd, last_activity_at, started_at)"
                " values (?,?,?,?,?,?,0.0,100.0,90.0)",
                [(skey(rid, nid, item), "fake", ti, to, api_v, tools)
                 for (nid, item, ti, to, api_v, tools) in case["rows"]])
            c.commit()
        return r

    def views(self, case):
        self.make_run(case)
        tool = door.act_status({"run_id": case["run"], "detail": "full"})
        self.assertNotIn("error", tool, case["case"])
        dash = api._view(RUNS / case["run"], full=True)
        self.assertIsNotNone(dash, case["case"])
        return tool, dash

    def check_level(self, tag, tool_m, dash_m, expected):
        def state(m, where):
            self.assertIsNotNone(m, f"{tag}: {where} metrics dict missing")
            return ("num", m["api_calls"]) if "api_calls" in m else (ABSENT, None)
        tool_state, dash_state = state(tool_m, "door"), state(dash_m, "dashboard")
        self.assertEqual(tool_state, dash_state,
                         f"{tag}: surfaces DISAGREE door={tool_state} dashboard={dash_state}")
        want = (ABSENT, None) if expected is ABSENT else ("num", expected)
        self.assertEqual(tool_state, want,
                         f"{tag}: both surfaces answer {tool_state}, spec wants {want}")

    def drive(self, case):
        tool, dash = self.views(case)
        for (kind, key), expected in sorted(case["expect"].items(), key=lambda kv: str(kv[0])):
            tag = f"[{case['case']}] {kind}" + (f" {key}" if key is not None else "")
            if kind == "node":
                self.check_level(tag, tool["nodes"][key].get("metrics"),
                                 dash["nodes"][key].get("metrics"), expected)
            elif kind == "run":
                self.check_level(tag, tool.get("metrics"), dash.get("metrics"), expected)
            else:   # item: dashboard-only surface — same numeric-or-absent rule, shared rows
                m = dash["nodes"][key[0]]["item_metrics"][key[1]]
                has = "api_calls" in m
                self.assertEqual(has, expected is not ABSENT,
                                 f"{tag}: item api_calls present={has}, spec wants "
                                 f"{'absent' if expected is ABSENT else expected}")
                if expected is not ABSENT:
                    self.assertEqual(m["api_calls"], expected, f"{tag}: item api_calls != {expected}")
        return tool, dash

    def test_grid_parity(self):
        for case in GRID:
            with self.subTest(case=case["case"]):
                self.drive(case)

    def test_no_unknown_zero_per_level_from_rows(self):
        # Hard invariant, re-derived from the seeded rows (never from the tables):
        # a level's numeric api_calls is lawful ONLY when every row contributing
        # to THAT level is known — on both surfaces; a level with an unknown
        # contributing row must omit the key on both surfaces (dashboard items:
        # the only surface that has them).
        for case in GRID:
            with self.subTest(case=case["case"]):
                tool, dash = self.views(case)
                rows = case["rows"]

                def law(contrib):
                    return ABSENT if any(r[4] is None for r in contrib) else sum(r[4] for r in contrib)

                def state(m):
                    return ("num", m["api_calls"]) if m and "api_calls" in m else (ABSENT, None)

                def claim(tag, tool_m, dash_m, contrib):
                    want = law(contrib)
                    want = (ABSENT, None) if want is ABSENT else ("num", want)
                    self.assertEqual(state(tool_m), state(dash_m), f"{tag}: surfaces DISAGREE")
                    self.assertEqual(state(tool_m), want,
                                     f"{tag}: answered {state(tool_m)}, rows say {want}")

                for n in case["nodes"]:
                    nid = n["id"]
                    claim(f"[{case['case']}] node {nid}", tool["nodes"][nid].get("metrics"),
                          dash["nodes"][nid].get("metrics"), [r for r in rows if r[0] == nid])
                    for i in range(len(n.get("fanout", {}).get("items", []) or [])):
                        m = dash["nodes"][nid].get("item_metrics", {}).get(i, {})
                        contrib = [r for r in rows if r[0] == nid and r[1] == i]
                        want = law(contrib)
                        want = (ABSENT, None) if want is ABSENT else ("num", want)
                        self.assertEqual(("num", m["api_calls"]) if "api_calls" in m else (ABSENT, None), want,
                                         f"[{case['case']}] item {nid}[{i}]")
                claim(f"[{case['case']}] run", tool.get("metrics"), dash.get("metrics"), rows)

    def test_item_level_keeps_exact_known_counts(self):
        # The fan-out case pins BOTH item rules: item 1 (unknown row) must be
        # absent on the dashboard, and item 0 (known row) must stay EXACTLY
        # numeric 4 there — the direction item 1's shared fold helper must keep.
        case = next(c for c in GRID if c["run"] == "t114fanmix")
        _, dash = self.views(case)
        items = dash["nodes"]["fan"]["item_metrics"]
        self.assertEqual(items[0].get("api_calls"), 4,
                         f"item 0 lost its exact known count: {items[0]}")
        self.assertNotIn("api_calls", items[1],
                         f"item 1 reports numeric api_calls while unknown: {items[1]}")

    def test_r8_no_third_fold(self):
        # The complete fold call set is door act_status + dashboard _view/_fold_metrics:
        # scripts/ (the CLI/read-model side) must stay fold-free — re-verifies the
        # grep that was empty at 2d97807 and at this base.
        hits = [p for p in (ROOT / "scripts").iterdir()
                if p.is_file() and any(t in p.read_text(errors="replace")
                                       for t in ("api_calls", "child_metrics", "_fold"))]
        self.assertEqual([p.name for p in hits], [],
                         "a third fold appeared under scripts/ — the parity matrix must grow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
