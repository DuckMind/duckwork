#!/usr/bin/env python3
"""est-ij0: convoy splice (`order_only`) + run.blocked residue classifier +
dead-letter attempt ledger, proven end-to-end on the fake child and against the
distilled peer golden fixture (tests/fixtures/convoy-wave1.json).

Run: env -u WF_RUNS_ROOT -u DUCKWORK_HOME PYTHONPATH=/opt/duckwork
     /opt/duckwork/.venv/bin/python tests/test_convoy_splice_ij0.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wf_door_convoy_ij0", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation
wf_test_isolation.install(door)
C = door._common
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "convoy-wave1.json").read_text())


def convoy_graph(order_only=True):
    """Three lanes; lane B's work dies. Lane C's converge is ordered after B's
    (echo nodes cannot take order_only, so the two ordered converges are agents)."""
    def conv(nid, lane_dep, pred):
        n = {"id": nid, "type": "agent", "goal": "converge ok", "after": [lane_dep, pred]}
        if order_only:
            n["order_only"] = [pred]
        return n
    nodes = [
        {"id": "a_work", "type": "echo", "output": {"verdict": "merged"}},
        {"id": "a_conv", "type": "echo", "after": ["a_work"], "output": {"verdict": "ok"}},
        {"id": "b_work", "type": "agent", "goal": "FAILME please"},
        conv("b_conv", "b_work", "a_conv"),
        {"id": "c_work", "type": "echo", "output": {"verdict": "not-approved"}},
        conv("c_conv", "c_work", "b_conv"),
        {"id": "c_close", "type": "echo", "after": ["c_conv"], "output": 1},
    ]
    return {"name": "convoy-ij0", "nodes": nodes}


class ConvoySpliceRun(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="wf-ij0-convoy-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "home").mkdir()
        self.runs = self.root / "runs"
        env = patch.dict(os.environ, {"WF_RUNS_ROOT": str(self.runs),
                                      "DUCKWORK_HOME": str(self.root / "home"),
                                      "DUCKWORK_WF_DUCKWORK_BIN": str(ROOT / "tests" / "fake"),
                                      "FAKE_LOG": str(self.root / "fake.log")})
        env.start()
        self.addCleanup(env.stop)
        wf_test_isolation.install(door)
        spawn = patch.object(door, "_spawn_runner")
        spawn.start()
        self.addCleanup(spawn.stop)

    def _run(self, graph):
        started = door._create_run({"graph": graph}, graph, None, {}, {}, [], concurrency_meta={})
        self.assertIn("run_id", started, started)
        rid = started["run_id"]
        p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", rid],
                           env=os.environ.copy(), capture_output=True, text=True, timeout=180)
        self.assertEqual(p.returncode, 0, p.stderr)
        r = self.runs / rid
        events = [json.loads(x) for x in (r / "events.jsonl").read_text().splitlines()]
        return rid, r, p.stdout.strip(), events

    def _status(self, r, nid):
        f = r / "nodes" / f"{nid}.json"
        return json.loads(f.read_text())["status"] if f.exists() else None

    def test_splice_releases_lane_c_past_dead_lane_b(self):
        rid, r, out, events = self._run(convoy_graph(order_only=True))
        self.assertEqual(out, f"WORKFLOW_FAILED {rid} (b_work)")
        self.assertEqual(self._status(r, "c_conv"), "done")      # spliced past b_conv
        self.assertEqual(self._status(r, "c_close"), "done")
        self.assertIsNone(self._status(r, "b_conv"))             # data-dead, never spawned
        spl = [e for e in events if e["event"] == "node.spliced"]
        self.assertEqual([(e["node"], e["past"]) for e in spl], [("c_conv", ["b_conv"])])
        rb = next(e for e in events if e["event"] == "run.blocked")
        self.assertEqual(rb["blocked"], ["b_conv"])
        self.assertEqual(rb["residue"]["data_dead"], ["b_conv"])
        self.assertEqual(rb["residue"]["order_dead"], [])
        dl = rb["dead_letter"]["b_work"]
        self.assertEqual(set(dl), {"error_class", "attempts", "final_empty", "attempts_log", "last"})
        self.assertEqual(dl["error_class"], "schema")
        self.assertIsNone(dl["last"])                            # no state.db row: honest absence
        # the spliced node's prompt never received the dead lane's (absent) or the
        # ordering predecessor's output: ordering edges carry no data
        prompt = next((r / "logs").glob("c_conv.a0.prompt.md")).read_text()
        self.assertNotIn("b_conv", prompt)
        self.assertIn("c_work", prompt)

    def test_without_order_only_dead_lane_still_blocks_and_is_data_dead(self):
        rid, r, out, events = self._run(convoy_graph(order_only=False))
        self.assertEqual(out, f"WORKFLOW_FAILED {rid} (b_work)")
        self.assertIsNone(self._status(r, "c_conv"))
        self.assertFalse(any(e["event"] == "node.spliced" for e in events))
        rb = next(e for e in events if e["event"] == "run.blocked")
        self.assertEqual(rb["residue"]["data_dead"], ["b_conv", "c_conv", "c_close"])
        self.assertEqual(rb["residue"]["order_dead"], [])
        self.assertEqual(rb["residue"]["verdicts"]["c_work"],
                         {"status": "done", "verdict": "not-approved"})


class OrderOnlyGrammar(unittest.TestCase):
    def errs(self, nodes):
        return json.dumps(C.validate_graph_errors(nodes))

    def test_order_only_must_be_subset_of_after(self):
        e = self.errs([{"id": "a", "type": "agent", "goal": "x"},
                       {"id": "b", "type": "agent", "goal": "y", "order_only": ["a"]}])
        self.assertIn("order_only ids must also appear in after", e)

    def test_order_only_rejected_on_echo_and_non_list(self):
        e = self.errs([{"id": "a", "type": "echo", "output": 1},
                       {"id": "b", "type": "echo", "after": ["a"], "output": 2, "order_only": ["a"]}])
        self.assertIn("order_only is meaningless on echo", e)
        e = self.errs([{"id": "a", "type": "agent", "goal": "x"},
                       {"id": "b", "type": "agent", "goal": "y", "after": ["a"], "order_only": "a"}])
        self.assertIn("order_only must be a list", e)

    def test_valid_order_only_on_agent_and_gate(self):
        e = C.validate_graph_errors([
            {"id": "a", "type": "agent", "goal": "x"},
            {"id": "b", "type": "agent", "goal": "y", "after": ["a"], "order_only": ["a"]},
            {"id": "g", "type": "gate", "question": "go?", "after": ["b"], "order_only": ["b"]}])
        self.assertFalse([x for x in e if "order_only" in json.dumps(x)], e)


class GoldenFixtureWave1(unittest.TestCase):
    """The peer run that motivated est-ij0: 16 lanes, one convoy of converges,
    one dead build. Numbers below were verified seat-by-seat in both estates."""

    def setUp(self):
        self.nodes = [dict(n) for n in FIXTURE["nodes"]]
        self.states = dict(FIXTURE["states"])
        self.outputs = FIXTURE["outputs"]
        self.blocked = FIXTURE["run_blocked"]["blocked"]
        # declare the convoy: every converge's cross-lane converge edge is ordering-only
        self.convoy = []
        for n in self.nodes:
            if n["id"].endswith("__converge"):
                lane = n["id"].split("__")[0]
                oo = [a for a in n["after"] if a.endswith("__converge") and not a.startswith(lane + "__")]
                if oo:
                    n["order_only"] = oo
                    self.convoy.append((n["id"], oo[0]))

    def test_fixture_shape(self):
        self.assertEqual(len(self.nodes), 128)
        self.assertEqual(len(self.convoy), 15)                    # 15 cross-lane converge->converge
        self.assertEqual(FIXTURE["run_blocked"]["failed"], ["sys-i2ng1n__build"])
        self.assertEqual(len(self.blocked), 30)
        # the distilled fixture drops goals (prompts are private); the convoy
        # annotation itself must validate under the closed grammar
        self.assertEqual(C.validate_graph_errors([dict(n, goal="g") for n in self.nodes]), [])

    def test_residue_splits_6_data_dead_24_order_dead(self):
        unconverged, _ = C.blocked_legibility(self.nodes, self.states, self.blocked)
        res = C.residue(self.nodes, self.states, self.blocked, unconverged, self.outputs)
        self.assertEqual(res["data_dead"], [f"sys-i2ng1n__{s}" for s in
                                            ("test", "fix", "policy", "merge", "converge", "verify-close")])
        self.assertEqual(len(res["order_dead"]), 24)
        lanes = {x.split("__")[0] for x in res["order_dead"]}
        self.assertEqual(len(lanes), 12)
        self.assertTrue(all(x.endswith(("__converge", "__verify-close")) for x in res["order_dead"]))

    def test_verdicts_not_status_give_the_merge_state_classes(self):
        unconverged, _ = C.blocked_legibility(self.nodes, self.states, self.blocked)
        res = C.residue(self.nodes, self.states, self.blocked, unconverged, self.outputs)
        lanes = sorted({x.split("__")[0] for x in res["order_dead"]})
        classes = {}
        for lane in lanes:
            v = res["verdicts"][f"{lane}__merge"]
            fleet = (self.outputs.get(f"{lane}__policy") or {}).get("fleet_touching")
            if v["verdict"] == "merged":
                cls = "landed-fleet-pending" if fleet else "landed-no-fleet"
            elif v["status"] == "partial":
                cls = "pending-reprove"
            else:
                cls = "gate-refused"
            classes.setdefault(cls, []).append(lane)
        self.assertEqual({k: len(v) for k, v in classes.items()},
                         {"gate-refused": 10, "landed-no-fleet": 1, "pending-reprove": 1})
        self.assertEqual(classes["landed-no-fleet"], ["sys-2ro3n0"])
        self.assertEqual(classes["pending-reprove"], ["sys-plmnbx"])
        # node.status alone would have called 11 of the 12 merges "done"
        self.assertEqual(sum(res["verdicts"][f"{l}__merge"]["status"] == "done" for l in lanes), 11)

    def test_splice_frontier_and_convoy_drain(self):
        deps_ok, deps_res, spliced = C.release_law(self.nodes, self.states)
        byid = {n["id"]: n for n in self.nodes}
        frontier = [n["id"] for n in self.nodes if self.states[n["id"]] == "pending"
                    and deps_ok(n) and deps_res(n)]
        # lane hemsjz is released past the dead i2ng1n converge onto 7cppwl's committed one
        self.assertEqual(frontier, ["sys-hemsjz__converge"])
        self.assertEqual(spliced(byid["sys-hemsjz__converge"]), ["sys-i2ng1n__converge"])
        # drain: commit every released node (typed partial-ancestor fail mirrors the runner)
        states = dict(self.states)
        while True:
            dok, dres, _ = C.release_law(self.nodes, states)
            ready = [n for n in self.nodes if states[n["id"]] == "pending" and dok(n) and dres(n)]
            pend = [n for n in self.nodes if states[n["id"]] == "pending"]
            typed = [n for n in pend if any(states.get(a) == "partial" and a not in (n.get("order_only") or ())
                                            for a in n["after"])]
            for n in typed:
                states[n["id"]] = "failed"
            if not ready and not typed:
                break
            for n in ready:
                if n not in typed:
                    states[n["id"]] = "done"
        left = sorted(k for k, v in states.items() if v == "pending")
        self.assertEqual(left, sorted([f"sys-i2ng1n__{s}" for s in
                                       ("test", "fix", "policy", "merge", "converge", "verify-close")]
                                      + ["sys-plmnbx__verify-close"]))
        self.assertEqual(states["sys-plmnbx__converge"], "failed")   # partial merge: re-prove first
        self.assertEqual(states["sys-dr40m-33__verify-close"], "done")  # convoy tail closed

    def test_dead_letter_surfaces_the_ledger_not_final_alone(self):
        rec = FIXTURE["dead_records"]["sys-i2ng1n__build"]
        self.assertEqual(rec["final"], "")
        self.assertEqual(rec["attempts"], 2)
        self.assertEqual([a["error_class"] for a in rec["attempts_log"]], ["timeout"])
        self.assertTrue(rec["attempts_log"][0]["resume"])


if __name__ == "__main__":
    unittest.main()
