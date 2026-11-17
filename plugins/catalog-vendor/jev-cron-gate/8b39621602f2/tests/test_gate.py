"""Offline tests: no network. Run: python -m pytest tests/"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gate  # noqa: E402


class GateTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {"DUCKWORK_HOME": self.home, "TYPESAFE_API_KEY": "k"})
        self.env.start()
        os.makedirs(gate.gates_dir())
        self.cfg = {"question": "q", "sources": [{"text": "hello"}], "skip_below": 0.2, "max_consecutive_skips": 2}
        json.dump(self.cfg, open(os.path.join(gate.gates_dir(), "g.json"), "w"))

    def tearDown(self):
        self.env.stop()

    def test_no_config_wakes(self):
        self.assertTrue(gate.decide("missing")[0])

    def test_jev_error_wakes(self):
        with mock.patch.object(gate, "ask_jev", return_value=(None, "jev error")):
            self.assertTrue(gate.decide("g")[0])

    def test_low_score_skips_then_cap_forces_wake(self):
        with mock.patch.object(gate, "ask_jev", return_value=(0.05, None)):
            self.assertEqual([gate.decide("g")[0] for _ in range(3)], [False, False, True])

    def test_high_score_wakes(self):
        with mock.patch.object(gate, "ask_jev", return_value=(0.9, None)):
            self.assertTrue(gate.decide("g")[0])

    def test_non_localhost_url_refused(self):
        s = gate.build_state({"sources": [{"url": "https://example.com/x"}]}, 0)
        self.assertIn("only localhost", s)

    def test_state_is_capped(self):
        s = gate.build_state({"sources": [{"text": "x" * 20000}]}, 0)
        self.assertLessEqual(len(s), gate.MAX_STATE)

    def test_main_prints_wake_line_last(self):
        with mock.patch.object(gate, "ask_jev", return_value=(0.01, None)), \
             mock.patch("builtins.print") as p:
            gate.main(["g"])
        self.assertEqual(json.loads(p.call_args_list[-1][0][0]), {"wakeAgent": False})


if __name__ == "__main__":
    unittest.main()
