#!/usr/bin/env python3
"""#157 (belt): the door's run payload carries a compact `lifecycle_notice`
field — the exact ::workflow{id="..."} line plus a one-line standalone-paste
reminder — so the card contract is prompt-visible in the RESULT, not only in
the hint prose. A launch and a lane-key dedupe both carry it, keyed to the
exact run_id the caller holds. Mirrors the run-result pins of
test_card_backend_080.py (same hermetic isolation posture)."""
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, "/opt/duckwork")
spec = importlib.util.spec_from_file_location("workflow_card_notice_157", ROOT / "__init__.py")
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)
import wf_test_isolation as _iso; _iso.install(wf)  # #71: pin settings.runs_root alongside WF_RUNS_ROOT
gateway_spec = importlib.util.find_spec('gateway')
if gateway_spec is None or not gateway_spec.origin:
    raise RuntimeError('Tests require the Duckwork source checkout on PYTHONPATH')
context_spec = importlib.util.spec_from_file_location('gateway.session_context',
    Path(gateway_spec.origin).with_name('session_context.py'))
assert context_spec is not None and context_spec.loader is not None
context = importlib.util.module_from_spec(context_spec)
sys.modules['gateway.session_context'] = context
context_spec.loader.exec_module(context)
set_session_vars, clear_session_vars = context.set_session_vars, context.clear_session_vars

CARD = re.compile(r'^::workflow\{id="([A-Za-z0-9._-]+)"\}$')
GRAPH = {"name": "card-notice", "nodes": [{"id": "one", "type": "agent", "goal": "offline"}]}


class LifecycleNotice(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory(dir=ROOT)
        self.env = patch.dict(os.environ, {"DUCKWORK_HOME": self.home.name,
                                           "WF_RUNS_ROOT": str(Path(self.home.name) / "workflows"),
                                           "DUCKWORK_SESSION_ID": "stale-process",
                                           "DUCKWORK_WF_DUCKWORK_BIN": "offline"})
        self.env.start()
        self.spawn = patch.object(wf, "_spawn_runner")
        self.spawn.start()

    def tearDown(self):
        self.spawn.stop()
        self.env.stop()
        self.home.cleanup()

    def bind(self, sid):
        return set_session_vars(platform="desktop", source="desktop", session_id=sid, ui_session_id="tab-" + sid)

    def launch(self, extra=None):
        args = {"action": "run", "graph": json.loads(json.dumps(GRAPH))}
        args.update(extra or {})
        return json.loads(wf.handle(args))

    def test_run_result_carries_lifecycle_notice_with_exact_run_id(self):
        tokens = self.bind("session-a")
        try:
            out = self.launch()
            rid = out["run_id"]
            # The hint stays the copy-exact inducement (belt AND suspenders).
            self.assertIn("PASTE this line alone in your reply", out["hint"])
            self.assertEqual(out["card"], f'::workflow{{id="{rid}"}}')
            # The notice is a compact field: exact directive line + one-line reminder.
            self.assertIn("lifecycle_notice", out, json.dumps(out)[:200])
            notice = out["lifecycle_notice"]
            self.assertIn(f'::workflow{{id="{rid}"}}', notice)
            self.assertRegex(notice, r'^::workflow\{id="' + re.escape(rid) + r'"\} — ')
            self.assertIn("the desktop card renders from this line", notice)
            self.assertIn("paste it standalone", notice)
            # One line: it must survive copy into a reply as a single paragraph.
            self.assertNotIn("\n", notice.strip())
        finally:
            clear_session_vars(tokens)

    def test_lane_key_dedupe_carries_notice_for_incumbent(self):
        tokens = self.bind("session-a")
        try:
            first = self.launch({"lane_key": "wf157/duo"})
            again = self.launch({"lane_key": "wf157/duo"})
            self.assertTrue(again.get("deduped"), json.dumps(again)[:200])
            self.assertEqual(again["run_id"], first["run_id"])
            self.assertIn(f'::workflow{{id="{first["run_id"]}"}}', again["lifecycle_notice"])
        finally:
            clear_session_vars(tokens)


if __name__ == "__main__":
    unittest.main(verbosity=2)
