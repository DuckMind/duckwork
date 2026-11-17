#!/usr/bin/env python3
"""Ledger e68544a37be37657 (fb-fix-2dd8de73): a harvest-on-death `partial` must
NOT silently satisfy a plain after-edge. Live shape: node `impl` died at
max_turns 40/40 with only RED tests committed; status=partial was committed
(#4 harvest law — untouched here), and the runner released BOTH `verify` and
`suite` onto the incomplete candidate (they had to be cancelled).

The law this test locks (fail-closed default, #4 carve-outs preserved):
  * a plain after-edge is NOT satisfied by a `partial` ancestor; the descendant
    FAILS TYPED at the wave boundary (error 'blocked_by_partial_ancestor: <nid>',
    error_class 'precondition' — the _fail_precondition class) and NEVER spawns;
  * a descendant that wants the harvest opts in with `after_partial: true`
    (agent + gate only, bool only; echo rejects it, unknown-key errors name it);
  * a `requires` ref resolving from an ancestor whose committed record carries
    harvested provenance is UNMET without the opt-in, satisfied WITH it;
  * PRESERVED (#4): a node's OWN fanout partial-credit merge still commits
    done; a LEAF partial still closes the run green with its harvested output
    in summary.md; deps_res keeps counting partial as RESOLVED (typed verdict,
    never a deadlock).

Run: env -u WF_RUNS_ROOT -u DUCKWORK_HOME \
     PYTHONPATH=/opt/duckwork /opt/duckwork/.venv/bin/python tests/test_partial_block_87.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

FAKE = str(ROOT / "tests" / "fake")
SCHEMA = {"type": "object", "properties": {"result": {"type": "string"}},
         "required": ["result"]}


class PB87(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pb87-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.runs = self.home / "workflows"
        self.runs.mkdir()
        (self.home / "fake.log").write_text("")

    def mk(self, run_id, nodes, **meta):
        r = self.runs / run_id
        (r / "nodes").mkdir(parents=True)
        (r / "gates").mkdir()
        (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": nodes}))
        m = {"duckwork_bin": FAKE, "concurrency": 4, "node_timeout": 30}
        m.update(meta)
        (r / "run.json").write_text(json.dumps(m))
        return r

    def wf(self, run_id, extra_env=None, timeout=120):
        env = dict(os.environ, DUCKWORK_HOME=str(self.home),
                   WF_RUNS_ROOT=str(self.runs),
                   FAKE_LOG=str(self.home / "fake.log"),
                   **(extra_env or {}))
        return subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                              env=env, capture_output=True, text=True,
                              timeout=timeout).stdout.strip()

    def rec(self, r, nid):
        return json.loads((r / "nodes" / f"{nid}.json").read_text())

    def spawns_of(self, run_id):
        return len(list((self.runs / run_id / "logs").glob("*.log")))

    def events(self, r):
        try:
            return [json.loads(l) for l in (r / "events.jsonl").read_text().splitlines()]
        except FileNotFoundError:
            return []

    # ---- unit: the vocabulary change itself --------------------------------
    def test_dep_satisfied_strict_and_optin(self):
        self.assertTrue(wfcommon.dep_satisfied({"a": "done"}, "a"))
        self.assertTrue(wfcommon.dep_satisfied({"a": "skipped"}, "a"))
        self.assertFalse(wfcommon.dep_satisfied({"a": "partial"}, "a"),
                         "plain after-edge must NOT be satisfied by partial")
        self.assertTrue(wfcommon.dep_satisfied({"a": "partial"}, "a", allow_partial=True),
                        "the after_partial opt-in satisfies on partial")
        self.assertFalse(wfcommon.dep_satisfied({"a": "failed"}, "a", allow_partial=True))

    # ---- C1: partial ancestor blocks a plain after-edge, typed, no spawn ----
    def test_C1_partial_blocks_plain_after_edge(self):
        # Control (pre-fix discriminator): same graph, descendant opts IN — the
        # harvest releases it and the child DOES spawn. If the control's spawn
        # vanished, the C1 assertion below could not be attributed to the law.
        ctrl = self.mk("pb87-c1-ctl", [
            {"id": "impl", "type": "agent", "goal": "DIETEST c1", "schema": SCHEMA},
            {"id": "verify", "type": "agent", "after": ["impl"], "goal": "VERIFY c1",
             "schema": SCHEMA, "after_partial": True}])
        out = self.wf("pb87-c1-ctl", {"FAKE_MODE": "die_after_json"})
        self.assertEqual(self.rec(ctrl, "impl")["status"], "partial")
        self.assertEqual(self.rec(ctrl, "verify")["status"], "done")
        self.assertEqual(self.spawns_of("pb87-c1-ctl"), 2, "control: both spawned")
        self.assertTrue(out.startswith("WORKFLOW_DONE"), out)
        # The law: identical graph WITHOUT the opt-in.
        r = self.mk("pb87-c1", [
            {"id": "impl", "type": "agent", "goal": "DIETEST c1", "schema": SCHEMA},
            {"id": "verify", "type": "agent", "after": ["impl"], "goal": "VERIFY c1",
             "schema": SCHEMA}])
        out = self.wf("pb87-c1", {"FAKE_MODE": "die_after_json"})
        impl, ver = self.rec(r, "impl"), self.rec(r, "verify")
        self.assertEqual(impl["status"], "partial")          # #4 harvest kept
        self.assertEqual(ver["status"], "failed", str(ver))
        self.assertEqual(ver["error_class"], "precondition", str(ver))
        self.assertEqual(ver["error"], "blocked_by_partial_ancestor: impl")
        self.assertEqual(ver["output"], {"missing": ["impl"]})
        self.assertEqual(self.spawns_of("pb87-c1"), 1, "verify must NEVER spawn")
        self.assertTrue(out.startswith("WORKFLOW_FAILED"), out)
        self.assertIn("WORKFLOW_FAILED pb87-c1 (verify)", out)
        evs = self.events(r)
        self.assertTrue(any(e.get("event") == "node.failed" and e.get("node") == "verify"
                            and e.get("error_class") == "precondition"
                            and "blocked_by_partial_ancestor: impl" in (e.get("error") or "")
                            for e in evs), str(evs[-3:]))

    # ---- C2: after_partial:true consumes the harvest normally ---------------
    # (the C1 control above is the spawn-side proof with a real child; this
    # second opt-in run confirms the verdict is per-node, not a global flip.)
    def test_C2_optin_releases_off_the_harvest(self):
        r = self.mk("pb87-c2", [
            {"id": "impl", "type": "agent", "goal": "DIETEST c2", "schema": SCHEMA},
            {"id": "check", "type": "agent", "after": ["impl"], "goal": "CHECK c2",
             "schema": SCHEMA, "after_partial": True}])
        out = self.wf("pb87-c2", {"FAKE_MODE": "die_after_json"})
        self.assertEqual(self.rec(r, "impl")["status"], "partial")
        self.assertEqual(self.rec(r, "check")["status"], "done")
        self.assertEqual(self.spawns_of("pb87-c2"), 2)
        self.assertTrue(out.startswith("WORKFLOW_DONE"), out)

    # ---- C3: a LEAF partial still closes the run green (#4 preserved) -------
    def test_C3_leaf_partial_closes_green(self):
        r = self.mk("pb87-c3", [
            {"id": "plan", "type": "agent", "goal": "PLAN c3", "schema": SCHEMA},
            {"id": "harv", "type": "agent", "after": ["plan"], "goal": "DIETEST c3",
             "schema": SCHEMA}])
        out = self.wf("pb87-c3", {"FAKE_MODE": "die_after_json"})
        self.assertEqual(self.rec(r, "harv")["status"], "partial")
        self.assertTrue(out.startswith("WORKFLOW_DONE"), out)
        summary = (r / "summary.md").read_text()
        self.assertIn("harvested", summary)          # harvested output IN the summary
        st = wfcommon.run_state(r)
        self.assertEqual(st["status"], "done")
        self.assertEqual(st["nodes"]["harv"]["status"], "partial")

    # ---- C4: fanout partial-credit merge still commits done (#4 preserved) --
    def test_C4_fanout_partial_credit_merge(self):
        r = self.mk("pb87-c4", [
            {"id": "fan", "type": "agent", "goal": "FAN c4",
             "fanout": {"items": [{"n": "x"}, {"n": "DIETEST c4"}], "schema": SCHEMA}}])
        out = self.wf("pb87-c4", {"FAKE_MODE": "die_after_json"})
        rec = self.rec(r, "fan")
        self.assertEqual(rec["status"], "done", str(rec)[:300])
        self.assertEqual(len(rec["output"]["items"]), 2)       # harvest merged in
        self.assertEqual(rec["output"]["failed_items"], 0)     # partial counts toward done
        self.assertTrue(out.startswith("WORKFLOW_DONE"), out)

    # ---- C5: requires on a harvested ancestor: unmet w/o opt-in, met with ----
    def test_C5_requires_provenance(self):
        # (a) direct partial ancestor + requires: the after-edge block fires
        # first (the ancestor IS the block — the requires list never gets read).
        r = self.mk("pb87-c5a", [
            {"id": "gen", "type": "agent", "goal": "DIETEST c5", "schema": SCHEMA},
            {"id": "use", "type": "agent", "after": ["gen"], "goal": "USE c5",
             "schema": SCHEMA, "requires": {"gen": ["result"]}}])
        out = self.wf("pb87-c5a", {"FAKE_MODE": "die_after_json"})
        use = self.rec(r, "use")
        self.assertEqual(self.rec(r, "gen")["status"], "partial")
        self.assertEqual(use["status"], "failed")
        self.assertEqual(use["error_class"], "precondition")
        self.assertEqual(use["error"], "blocked_by_partial_ancestor: gen")
        self.assertEqual(use["output"], {"missing": ["gen"]})
        self.assertEqual(self.spawns_of("pb87-c5a"), 1, "use must NEVER spawn")
        self.assertIn("WORKFLOW_FAILED pb87-c5a (use)", out)
        # (b) the provenance rule's real terrain: requires names a HARVESTED
        # GRANDPARENT (harvest consumed by the opted-in middle, C stays plain) —
        # the ref resolves through committed outputs yet is unmet without opt-in.
        r2 = self.mk("pb87-c5b", [
            {"id": "gen", "type": "agent", "goal": "DIETEST c5", "schema": SCHEMA},
            {"id": "mid", "type": "agent", "after": ["gen"], "goal": "MID c5",
             "schema": SCHEMA, "after_partial": True},
            {"id": "use", "type": "agent", "after": ["mid"], "goal": "USE c5",
             "schema": SCHEMA, "requires": {"gen": ["result"]}}])
        out2 = self.wf("pb87-c5b", {"FAKE_MODE": "die_after_json"})
        use2 = self.rec(r2, "use")
        self.assertEqual(self.rec(r2, "mid")["status"], "done")   # opt-in consumed harvest
        self.assertEqual(use2["status"], "failed")
        self.assertEqual(use2["error_class"], "precondition")
        self.assertEqual(use2["error"], "precondition unmet: gen.harvested")
        self.assertEqual(use2["output"], {"missing": ["gen.harvested"]})  # the PATH resolves; provenance is the unmet item
        self.assertEqual(self.spawns_of("pb87-c5b"), 2, "use must NEVER spawn")
        # (c) every node opts in -> the harvest flows, run closes green
        r3 = self.mk("pb87-c5c", [
            {"id": "gen", "type": "agent", "goal": "DIETEST c5", "schema": SCHEMA},
            {"id": "mid", "type": "agent", "after": ["gen"], "goal": "MID c5",
             "schema": SCHEMA, "after_partial": True},
            {"id": "use", "type": "agent", "after": ["mid"], "goal": "USE c5",
             "schema": SCHEMA, "requires": {"gen": ["result"]}, "after_partial": True}])
        out3 = self.wf("pb87-c5c", {"FAKE_MODE": "die_after_json"})
        self.assertEqual(self.rec(r3, "use")["status"], "done")
        self.assertEqual(self.spawns_of("pb87-c5c"), 3)
        self.assertTrue(out3.startswith("WORKFLOW_DONE"), out3)
        # (d) control: an all-DONE chain never provenance-blocks (provenance is
        # harvest:true, not merely a non-done status).
        r4 = self.mk("pb87-c5d", [
            {"id": "gen", "type": "agent", "goal": "GEN c5", "schema": SCHEMA},
            {"id": "mid", "type": "agent", "after": ["gen"], "goal": "MID c5",
             "schema": SCHEMA},
            {"id": "use", "type": "agent", "after": ["mid"], "goal": "USE c5",
             "schema": SCHEMA, "requires": {"gen": ["result"]}}])
        out4 = self.wf("pb87-c5d")
        self.assertEqual(self.rec(r4, "use")["status"], "done")
        self.assertTrue(out4.startswith("WORKFLOW_DONE"), out4)

    # ---- C6: the closed grammar owns the new key ------------------------------
    def test_C6_validator_grammar(self):
        base = {"id": "a", "type": "agent", "goal": "g"}
        def errs(**over):
            n = dict(base)
            n.update(over)
            return wfcommon.validate_graph_errors([n])
        self.assertEqual(errs(after_partial=True), [])
        self.assertEqual(errs(after_partial=False), [])
        for bad in ("yes", 1, None, {}):
            e = errs(after_partial=bad)
            self.assertTrue(any(x["field"] == "after_partial" for x in e),
                            f"after_partial={bad!r} must be rejected: {e}")
        g_ok = wfcommon.validate_graph_errors(
            [{"id": "a", "type": "agent", "goal": "g"},
             {"id": "g", "type": "gate", "after": ["a"], "question": "?",
              "after_partial": True}])
        self.assertEqual(g_ok, [])
        e = wfcommon.validate_graph_errors(
            [{"id": "a", "type": "agent", "goal": "g"},
             {"id": "e", "type": "echo", "after": ["a"], "output": {},
              "after_partial": True}])
        self.assertTrue(any(x["node"] == "e" and x["field"] == "after_partial"
                            and "after_partial" in x["msg"] for x in e), str(e))

    # ---- C7: a gate obeys the same law (fail-closed, no hold; opt-in holds) --
    def test_C7_gate_same_law(self):
        gate = {"id": "g", "type": "gate", "after": ["impl"], "question": "ship?"}
        # Control: opt-in gate HOLDS on the harvest (released only with the key).
        ctl = self.mk("pb87-c7-ctl", [
            {"id": "impl", "type": "agent", "goal": "DIETEST c7", "schema": SCHEMA},
            {**gate, "after_partial": True}])
        out = self.wf("pb87-c7-ctl", {"FAKE_MODE": "die_after_json"}, timeout=40)
        self.assertTrue(out.startswith("WORKFLOW_HELD"), out)
        st_ctl = wfcommon.run_state(ctl)
        self.assertEqual((st_ctl or {}).get("status"), "held")
        self.assertEqual((st_ctl or {}).get("nodes", {}).get("g", {}).get("status"), "pending")
        # The law: plain gate + partial ancestor -> typed fail, NEVER holds.
        r = self.mk("pb87-c7", [
            {"id": "impl", "type": "agent", "goal": "DIETEST c7", "schema": SCHEMA},
            gate])
        out = self.wf("pb87-c7", {"FAKE_MODE": "die_after_json"}, timeout=40)
        g = self.rec(r, "g")
        self.assertEqual(self.rec(r, "impl")["status"], "partial")
        self.assertEqual(g["status"], "failed", str(g))
        self.assertEqual(g["error_class"], "precondition", str(g))
        self.assertEqual(g["error"], "blocked_by_partial_ancestor: impl")
        self.assertEqual(g["output"], {"missing": ["impl"]})
        self.assertFalse((r / "gates" / "g.json").exists(), "a blocked gate never holds")
        self.assertIn("WORKFLOW_FAILED pb87-c7 (g)", out)
        st = wfcommon.run_state(r)
        self.assertEqual(st["status"], "failed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
