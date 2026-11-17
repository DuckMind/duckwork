#!/usr/bin/env python3
"""est-2ek.1.603 — publisher capability gate (typed refusal, pre-spawn).

Incident shape (fb key 074cafcbc108a918): a fresh verifier placed a
publish-capable node BEFORE the suite node in its ancestor chain; the suite
later failed; the publication had already committed. Graph validation cannot
infer publication side effects from prose, so the contract is now EXPLICIT:

  * an agent/echo node opts into publication with `publishes: true` (bool only;
    a non-bool or a gate-carried key is a validator rejection naming the key);
  * a node is a recognized SUITE-PROOF producer only by declaration:
    `suite_proof: true` (bool only, agent/gate); on commit with status done the
    runner writes a durable proof token at nodes/<id>.suite-proof.json
    (node id + committed efp — the same efp save_node stamps);
  * the runner REFUSES to start a publisher node — agent OR echo — until a
    valid token exists among its `after` ancestors (node_rec exists, status
    done, efp matches the CURRENT definition, and it is a declared producer).
    The refusal is typed at spawn, pre-execution, like the shelf guard:
    error_class 'precondition', error 'publisher_ungated: <nid> requires a
    verified suite proof token; missing proof from: <ancestors>'; the node
    NEVER spawns and the publish NEVER executes;
  * nodes not declaring the capability are untouched — no inference from prose.

RED proof (run before the fix): case (a) FAILS — the publisher spawns and the
publish side effect executes with no suite proof at all.

Run: env -u WF_RUNS_ROOT -u DUCKWORK_HOME \
     PYTHONPATH=/opt/duckwork /opt/duckwork/.venv/bin/python tests/test_publisher_cap_1603.py
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
import wf  # noqa: E402

FAKE = str(ROOT / "tests" / "fake")
PUBLISH_GOAL = "PUBLISH-Marker run the catalog PR open and push to main"


class PC1603(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pc1603-")
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

    def wf(self, run_id, timeout=120):
        env = dict(os.environ, DUCKWORK_HOME=str(self.home),
                   WF_RUNS_ROOT=str(self.runs),
                   FAKE_LOG=str(self.home / "fake.log"))
        return subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                              env=env, capture_output=True, text=True,
                              timeout=timeout).stdout.strip()

    def rec(self, r, nid):
        return json.loads((r / "nodes" / f"{nid}.json").read_text())

    def fake_log(self):
        return (self.home / "fake.log").read_text()

    # ---- (a) publisher BEFORE a failing suite => typed refusal, publish
    #         must NOT execute. This is the estate incident shape.
    def test_a_publisher_before_failing_suite_refused(self):
        r = self.mk("pc-a", [
            {"id": "publish", "type": "agent", "publishes": True,
             "goal": PUBLISH_GOAL},
            {"id": "suite", "type": "agent", "suite_proof": True,
             "after": ["publish"], "goal": "FAILME run the native suite"},
        ])
        out = self.wf("pc-a")
        rec = self.rec(r, "publish")
        self.assertNotEqual(rec.get("status"), "done",
                            f"publisher committed despite no suite proof: {rec}")
        self.assertNotIn("PUBLISH-Marker", self.fake_log(),
                         "publisher child SPAWNED without a suite proof — "
                         "the estate incident (publish committed before the suite failed)")
        self.assertEqual(rec.get("status"), "failed")
        self.assertEqual(rec.get("error_class"), "precondition")
        self.assertIn("publisher_ungated", rec.get("error", ""))
        self.assertIn("suite proof", rec.get("error", ""))   # refusal NAMES the missing proof
        self.assertIn("node.failed", (r / "events.jsonl").read_text())

    # ---- (a2) the same law for a publisher ECHO node: echo commits without a
    #           spawn, so the gate must cover the echo commit path too.
    def test_a2_publisher_echo_refused(self):
        r = self.mk("pc-a2", [
            {"id": "publish", "type": "echo", "publishes": True,
             "output": {"published": True}},
            {"id": "suite", "type": "agent", "suite_proof": True,
             "after": ["publish"], "goal": "FAILME run the native suite"},
        ])
        self.wf("pc-a2")
        rec = self.rec(r, "publish")
        self.assertNotEqual(rec.get("status"), "done",
                            f"publisher echo committed without proof: {rec}")
        self.assertEqual(rec.get("status"), "failed")
        self.assertEqual(rec.get("error_class"), "precondition")
        self.assertIn("publisher_ungated", rec.get("error", ""))
        self.assertNotIn("published", json.dumps(self.rec(r, "publish").get("output") or {})
                         if rec.get("status") == "failed" else "")

    # ---- (b) publisher AFTER a green suite proof RUNS.
    def test_b_publisher_after_green_suite_proof_runs(self):
        r = self.mk("pc-b", [
            {"id": "suite", "type": "agent", "suite_proof": True,
             "goal": "run the native suite green"},
            {"id": "publish", "type": "agent", "publishes": True,
             "after": ["suite"], "goal": PUBLISH_GOAL},
        ])
        self.wf("pc-b")
        self.assertEqual(self.rec(r, "suite").get("status"), "done")
        tok = r / "nodes" / "suite.suite-proof.json"
        self.assertTrue(tok.exists(), "green suite_proof node wrote no proof token")
        t = json.loads(tok.read_text())
        self.assertEqual(t.get("node"), "suite")
        self.assertEqual(t.get("efp"), self.rec(r, "suite").get("efp"),
                         "token efp must match the committed node efp")
        self.assertEqual(self.rec(r, "publish").get("status"), "done")
        self.assertIn("PUBLISH-Marker", self.fake_log())

    # ---- (b2) a STALE token never launders a publish: the suite node was
    #           amended (its efp changed) but the old token file survives —
    #           verification must fail closed against the current definition.
    def test_b2_stale_token_refused(self):
        r = self.mk("pc-b2", [
            {"id": "suite", "type": "agent", "suite_proof": True,
             "goal": "run the native suite green"},
            {"id": "publish", "type": "agent", "publishes": True,
             "after": ["suite"], "goal": PUBLISH_GOAL},
        ])
        # the suite record is a CURRENT green commit (real efp — node_rec sees it
        # done, no re-drive), but the token's efp is a lie: minted over a DIFFERENT
        # definition (the amended-suite shape). Verification must fail closed.
        byid = {n["id"]: n for n in json.loads((r / "graph.json").read_text())["nodes"]}
        live_efp = wfcommon.efp(byid, byid["suite"])
        (r / "nodes" / "suite.json").write_text(json.dumps(
            {"status": "done", "output": {"result": "ok"},
             "efp": live_efp, "fp_rule_version": wfcommon.FP_RULE_VERSION}))
        (r / "nodes" / "suite.suite-proof.json").write_text(json.dumps(
            {"node": "suite", "efp": "deadbeefdeadbeef", "written_at": "2026-10-04T00:00:00+00:00"}))
        self.wf("pc-b2")
        rec = self.rec(r, "publish")
        self.assertNotEqual(rec.get("status"), "done",
                            f"stale token laundered a publish: {rec}")
        self.assertEqual(rec.get("error_class"), "precondition")
        self.assertIn("publisher_ungated", rec.get("error", ""))
        self.assertNotIn("PUBLISH-Marker", self.fake_log())

    # ---- (c) non-publisher graphs are UNAFFECTED: a plain node BEFORE a
    #           failing suite behaves as before (spawns, no refusal class).
    def test_c_non_publisher_graph_unaffected(self):
        r = self.mk("pc-c", [
            {"id": "work", "type": "agent", "goal": "do ordinary work"},
            {"id": "suite", "type": "agent", "after": ["work"],
             "goal": "FAILME run the native suite"},
        ])
        self.wf("pc-c")
        self.assertEqual(self.rec(r, "work").get("status"), "done")
        self.assertIn("do ordinary work", self.fake_log())
        self.assertEqual(self.rec(r, "suite").get("status"), "failed")
        self.assertNotIn("publisher_ungated", (r / "events.jsonl").read_text())

    # ---- validator contract: closed grammar + explicit declarations.
    def test_d_validator_grammar(self):
        def errs(nodes):
            return wfcommon.validate_graph_errors({"name": "g", "nodes": nodes})

        ok = [{"id": "s", "type": "agent", "suite_proof": True, "goal": "g"},
              {"id": "p", "type": "agent", "publishes": True, "after": ["s"], "goal": "g"}]
        self.assertEqual(errs(ok), [], "declared publisher/suite_proof must validate")
        self.assertIn("publishes", wfcommon.AGENT_KEYS)
        self.assertIn("publishes", wfcommon.ECHO_KEYS)
        self.assertIn("suite_proof", wfcommon.AGENT_KEYS)
        self.assertIn("suite_proof", wfcommon.GATE_KEYS)

        bad = [dict(ok[1], publishes="yes")]
        e = errs([ok[0], bad[0]])
        self.assertTrue(any("publishes" in x.get("msg", "") for x in e),
                        f"non-bool publishes must be rejected naming the key: {e}")
        gatepub = [{"id": "s", "type": "agent", "goal": "g"},
                   {"id": "g8", "type": "gate", "after": ["s"], "publishes": True,
                    "question": "q?"}]
        e = errs(gatepub)
        self.assertTrue(any("publishes" in x.get("msg", "") for x in e),
                        f"gate must not carry publishes: {e}")
        suiteecho = [{"id": "s", "type": "echo", "suite_proof": True, "output": {}}]
        e = errs(suiteecho)
        self.assertTrue(any("suite_proof" in x.get("msg", "") for x in e),
                        f"echo must not carry suite_proof: {e}")

    # ---- the refusal copy is stable and names the missing proof.
    def test_e_refusal_names_missing_proof(self):
        r = self.mk("pc-e", [
            {"id": "pub", "type": "agent", "publishes": True, "goal": PUBLISH_GOAL},
            {"id": "s1", "type": "agent", "suite_proof": True, "after": ["pub"],
             "goal": "FAILME suite one"},
        ])
        self.wf("pc-e")
        err = self.rec(r, "pub").get("error", "")
        self.assertIn("publisher_ungated", err)
        self.assertIn("suite proof", err)
        # the publisher's ancestry declares NO proof producer at all — the refusal
        # says so (no inference, no free pass).
        self.assertIn("no suite_proof node", err)


if __name__ == "__main__":
    unittest.main(verbosity=2)
