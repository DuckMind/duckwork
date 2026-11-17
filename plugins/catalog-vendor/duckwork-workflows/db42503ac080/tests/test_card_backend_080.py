#!/usr/bin/env python3
"""Regression: launch a run in the tool's session; the payload carries a
parser-valid card. O1 (1.1) deleted the auto-card hook (the model's paste became
the card); #157 re-arms it as the ENFORCEMENT rung (card_enforcement.py) — a
last-resort shipper behind the paste, not a replacement for the payload card.
This suite locks the owner record, the `card` fields on the run payload, and the
register() surface (exactly the transform_llm_output hook, nothing else).
"""
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
spec = importlib.util.spec_from_file_location("workflow_card_backend", ROOT / "__init__.py")
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)
import wf_test_isolation as _iso71_wf21; _iso71_wf21.install(wf)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
# Load the host's real stdlib-only ContextVars module without importing the
# unrelated gateway configuration/dependency stack (minimal macOS test Python).
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

# Desktop transcript-directives.ts SHA256 48cdf5a1083c0c6b9b2c815719942b6071c1e6291d697c55e2f2814e714aa9da
# The real parser extracts `key="value"` from braces; bare run ids yield attrs={}
# and desktop/plugin.js consumes attrs.id. This regex is NOT a substitute
# for the frontend lane's actual TypeScript parser test.
CARD = re.compile(r'^::workflow\{id="([A-Za-z0-9._-]+)"\}$')
GRAPH = {"name": "card-backend", "nodes": [{"id": "one", "type": "agent", "goal": "offline"}]}


class CardBackend(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory(dir=ROOT)
        # #71: DUCKWORK_HOME alone loses to the context-local home override — pin
        # the runs root too or these launches land on the shared estate shelf.
        self.env = patch.dict(os.environ, {"DUCKWORK_HOME": self.home.name, "WF_RUNS_ROOT": str(Path(self.home.name) / "workflows"), "DUCKWORK_SESSION_ID": "stale-process", "DUCKWORK_WF_DUCKWORK_BIN": "offline"})
        self.env.start()
        self.spawn = patch.object(wf, "_spawn_runner")
        self.spawn.start()

    def tearDown(self):
        self.spawn.stop()
        self.env.stop()
        self.home.cleanup()

    def bind(self, sid):
        return set_session_vars(platform="desktop", source="desktop", session_id=sid, ui_session_id="tab-" + sid)

    def launch(self):
        return json.loads(wf.handle({"action": "run", "graph": json.loads(json.dumps(GRAPH))}))

    def test_tool_context_is_owner_and_payload_carries_card(self):
        tokens = self.bind("session-a")
        try:
            out = self.launch()
            rid = out["run_id"]
            meta = json.loads((Path(self.home.name) / "workflows" / rid / "run.json").read_text())
            self.assertEqual(meta["owner"]["session_id"], "session-a")
            self.assertEqual(meta["owner"]["ui_session_id"], "tab-session-a")
            self.assertEqual(out["card"], f'::workflow{{id="{rid}"}}')
            self.assertEqual(CARD.fullmatch(out["card"]).group(1), rid)
            # Copy-exact inducement (papercut #70): the hint IS the paste line.
            self.assertIn(out["card"], out["hint"])
            self.assertIn("PASTE this line alone in your reply", out["hint"])
        finally:
            clear_session_vars(tokens)

    def test_status_and_wait_payloads_carry_card(self):
        tokens = self.bind("session-a")
        try:
            out = self.launch()
            rid = out["run_id"]
            st = wf.act_status({"run_id": rid})
            self.assertEqual(st.get("card"), out["card"], json.dumps(st)[:200])
        finally:
            clear_session_vars(tokens)

    def test_register_wires_tool_skill_command_and_card_hook(self):
        # #157: register() wires the tool, skill, command, and exactly the
        # card-enforcement hook — nothing else (the O1 law pins the surface).
        class Context:
            hooks = {}
            def register_hook(self, name, fn): self.hooks[name] = fn
            def register_tool(self, **_): pass
            def register_command(self, *_, **__): pass
            def register_skill(self, name, path, **_):
                assert name == 'workflow' and path.is_file()
            def get_config(self, _, default): return default
        ctx = Context()
        wf.register(ctx)
        self.assertEqual(set(ctx.hooks), {"transform_llm_output"})
        self.assertIs(ctx.hooks["transform_llm_output"],
                      wf._card_enforcement._card_hook)


if __name__ == "__main__":
    unittest.main(verbosity=2)
