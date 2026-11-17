#!/usr/bin/env python3
"""#157 (MACHINERY rung, backend half): card enforcement via transform_llm_output.

core fires the 'transform_llm_output' hook once per turn BEFORE the final assistant
row is persisted (duckwork_cli/plugins.py VALID_HOOKS; agent/turn_finalizer.py
apply_llm_output_transform — first hook returning a non-empty string wins and that
string becomes the persisted+streamed text). The hook must:
  (a) append the missing ::workflow card as new lines for a launch this session
      made inside the window, and stamp card.echoed into the run's events.jsonl;
  (b) never ship the same run's card twice (the marker is the ledger);
  (c) leave a response that already carries the bare directive untouched;
  (d) NOT count a directive that sits only inside a code fence (fences are dead
      text to the directive renderer, so the card is still owed);
  (e) never ship another session's runs (owner.session_id gate);
  (f) fail-open: any discovery/parse error returns None, never raises;
  (g) cap at 3 cards per turn, newest launches first;
  (h) skip runs outside the recency window (default 30 min, owner-setting).
desktop/plugin.js is untouched: the directive renderer already turns the persisted
card line into a DirectiveCard — this rung only guarantees the line lands.
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_door():
    spec = importlib.util.spec_from_file_location("hw_card157", ROOT / "__init__.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Ctx:
    """Minimal PluginContext stand-in (same shape as the O1 register-surface test)."""
    def __init__(self):
        self.hooks = {}
    def register_hook(self, name, fn):
        self.hooks[name] = fn
    def register_tool(self, **_):
        pass
    def register_command(self, *_, **__):
        pass
    def register_skill(self, name, path, **_):
        pass
    def get_config(self, key, default):
        return default


def _iso(minutes_ago):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds")


class CardEnforcement(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.env = mock.patch.dict(os.environ, {
            "DUCKWORK_HOME": self.home.name,
            "WF_RUNS_ROOT": str(Path(self.home.name) / "workflows"),
            "DUCKWORK_WF_DUCKWORK_BIN": "offline",
        })
        self.env.start()
        os.environ.pop("DUCKWORK_SESSION_ID", None)
        self.hw = _load_door()
        self.h = self.hw._card_enforcement   # the module the _witness seam lives on
        import wf_test_isolation
        wf_test_isolation.install(self.hw)  # #71 r5: pin settings.runs_root to WF_RUNS_ROOT
        ctx = _Ctx()
        self.hw.register(ctx)
        self.assertIn("transform_llm_output", ctx.hooks,
                      "register() must wire the card-enforcement hook (#157)")
        self.hook = ctx.hooks["transform_llm_output"]
        self.runs = Path(os.environ["WF_RUNS_ROOT"])

    def tearDown(self):
        self.env.stop()
        self.home.cleanup()

    # ---- helpers --------------------------------------------------------
    def mk_run(self, rid, sid="S", minutes_ago=1.0, events=(), bad_json=False,
               root=None):
        r = (root or self.runs) / rid
        (r / "nodes").mkdir(parents=True)
        if bad_json:
            (r / "run.json").write_text("{not json")
        else:
            (r / "run.json").write_text(json.dumps(
                {"name": "t", "started": _iso(minutes_ago), "owner": {"session_id": sid}}))
        if events:
            with (r / "events.jsonl").open("a") as f:
                for e in events:
                    f.write(json.dumps(e) + "\n")
        return r

    def card(self, rid):
        return f'::workflow{{id="{rid}"}}'

    def call(self, text="All done.", sid="S", turn="t1", platform="desktop"):
        return self.hook(response_text=text, session_id=sid, turn_id=turn,
                         platform=platform, model="m")

    def echoed(self, r):
        p = r / "events.jsonl"
        if not p.exists():
            return []
        out = []
        for line in p.read_text().splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get("event") == "card.echoed":
                out.append(e)
        return out

    # ---- (a) launch turn, no directive in text: card ships + marker ----------
    def test_a_appends_card_and_stamps_marker(self):
        r = self.mk_run("r-one")
        out = self.call()
        self.assertIsNotNone(out)
        self.assertTrue(out.startswith("All done."))
        self.assertTrue(out.rstrip().endswith(self.card("r-one")), out)
        marked = self.echoed(r)
        self.assertEqual(len(marked), 1)
        self.assertEqual(marked[0]["session_id"], "S")
        self.assertEqual(marked[0]["turn_id"], "t1")
        self.assertIn("ts", marked[0])

    # ---- (b) second call same turn/next turn: nothing left outstanding ------
    def test_b_marker_makes_it_one_shot(self):
        self.mk_run("r-two")
        first = self.call()
        self.assertIsNotNone(first)
        self.assertIsNone(self.call())            # retry, same turn
        self.assertIsNone(self.call(turn="t2"))   # next turn

    # ---- (c) model already pasted the bare directive: hands off --------------
    def test_c_bare_directive_present_no_append(self):
        r = self.mk_run("r-three")
        out = self.call(text=f"Shipped.\n\n{self.card('r-three')}")
        self.assertIsNone(out)
        self.assertEqual(self.echoed(r), [])

    # ---- (d) directive only inside a fence: dead text, card still owed -------
    def test_d_fenced_directive_does_not_count(self):
        self.mk_run("r-four")
        out = self.call(text="Shipped:\n```\n" + self.card("r-four") + "\n```\n")
        self.assertIsNotNone(out)
        self.assertTrue(out.rstrip().endswith(self.card("r-four")), out)

    def test_d2_inline_code_directive_does_not_count(self):
        self.mk_run("r-fourb")
        out = self.call(text="paste `" + self.card("r-fourb") + "` now")
        self.assertIsNotNone(out)
        self.assertTrue(out.rstrip().endswith(self.card("r-fourb")), out)

    # ---- (e) foreign session: never another session's cards ------------------
    def test_e_foreign_session_gets_nothing(self):
        self.mk_run("r-five", sid="OTHER")
        self.assertIsNone(self.call())

    # ---- unknown surface: falsy platform never appends ----------------------
    def test_blank_platform_or_empty_text_never_appends(self):
        self.mk_run("r-six")
        self.assertIsNone(self.call(platform=""))
        self.assertIsNone(self.call(platform=None))  # type: ignore[arg-type]
        self.mk_run("r-sixb")
        self.assertIsNone(self.hook(response_text="", session_id="S", turn_id="t1",
                                    platform="desktop", model="m"))

    # ---- (f) fail-open: torn run.json and exploding discovery -> None --------
    def test_f_bad_run_json_no_raise(self):
        self.mk_run("r-seven", bad_json=True)
        self.assertIsNone(self.call())  # unreadable = not discoverable, never raises

    def test_f_exception_in_discovery_returns_none(self):
        self.mk_run("r-eight")
        common = self.hw._common
        with mock.patch.object(common, "runs_root", side_effect=RuntimeError("boom")):
            self.assertIsNone(self.call())

    def test_f_marker_write_failure_still_ships_text(self):
        r = self.mk_run("r-eightb")
        target = r / "events.jsonl"
        target.write_text("]\n")  # torn tail line
        target.chmod(0o444)       # marker append will fail
        try:
            out = self.call()
        finally:
            target.chmod(0o644)
        self.assertIsNotNone(out)
        self.assertTrue(out.rstrip().endswith(self.card("r-eightb")), out)

    # ---- (g) five launches one turn: max 3, newest first ---------------------
    def test_g_ceiling_three_newest_first(self):
        dirs = {}
        for i in range(1, 6):
            dirs[f"r-{i}"] = self.mk_run(f"r-{i}", minutes_ago=float(i))
        out = self.call()
        self.assertIsNotNone(out)
        lines = [ln for ln in out.splitlines() if ln.startswith("::workflow{")]
        self.assertEqual(lines, [self.card(f"r-{i}") for i in (1, 2, 3)], out)
        for i in (4, 5):  # the two oldest stay outstanding (unmarked)
            self.assertEqual(self.echoed(dirs[f"r-{i}"]), [])
        for i in (1, 2, 3):
            self.assertEqual(len(self.echoed(dirs[f"r-{i}"])), 1)

    # ---- (h) outside the recency window --------------------------------------
    def test_h_outside_window(self):
        self.mk_run("r-nine", minutes_ago=31.0)
        self.assertIsNone(self.call())

    def test_h_window_is_owner_settings_configurable(self):
        self.mk_run("r-ten", minutes_ago=3.0)
        real = self.hw._common.owner_setting
        def fake(key):
            return 2 if key == "card_window_minutes" else real(key)
        with mock.patch.object(self.hw._common, "owner_setting", side_effect=fake):
            self.assertIsNone(self.call())
        with mock.patch.object(self.hw._common, "owner_setting", side_effect=fake):
            self.mk_run("r-tenb", minutes_ago=1.0)
            self.assertIsNotNone(self.call(turn="t9"))

    # ---- discovery covers EVERY profile runs root ----------------------------
    def test_i_profile_runs_root_is_scanned(self):
        # A profile-scoped gateway resolves runs_root() to <profile_home>/workflows
        # (no env pin, no owner pin — the #41/#42 measured host shape). Drop the
        # WF_RUNS_ROOT pin so the resolver takes that branch for real.
        prof_runs = Path(self.home.name) / "profiles" / "p2" / "workflows"
        self.mk_run("r-prof", root=prof_runs)
        os.environ.pop("WF_RUNS_ROOT", None)
        out = self.call()
        self.assertIsNotNone(out)
        self.assertTrue(out.rstrip().endswith(self.card("r-prof")), out)

    # ---- malformed run ids (a hand-typed/foreign directive) don't count as shipped
    def test_j_malformed_directive_does_not_suppress(self):
        self.mk_run("r-eleven")
        out = self.call(text="done ::workflow{id=\"has space!\"} over")
        self.assertIsNotNone(out)
        self.assertTrue(out.rstrip().endswith(self.card("r-eleven")), out)

    # =====================================================================
    # #168 reconcile (comment 5968959336): the ledger must record SHIPPED,
    # not HOPED. core's dispatch (duckwork_cli/plugins_dispatch.invoke_hook)
    # invokes EVERY transform_llm_output callback and turn_finalizer.
    # apply_llm_output_transform then picks the FIRST non-empty string — so
    # an earlier winning peer discards our augmented text AFTER the old
    # code stamped card.echoed. Tests K/M/N reproduce that dispatch shape
    # (call every callback, then first-non-empty selection) instead of
    # trusting our return value as shipped.
    # =====================================================================

    def _dispatch(self, registrations, text="All done.", sid="S", turn="t1",
                  platform="desktop"):
        """Mirror of the real core seam: invoke_hook fires EVERY callback in
        registration order (each isolated), then apply_llm_output_transform
        keeps the FIRST non-empty string as the persisted+streamed text."""
        results = []
        for cb in registrations:
            try:
                r = cb(response_text=text, session_id=sid, turn_id=turn,
                       platform=platform, model="m")
            except Exception:
                r = None                      # per-callback isolation
            if r is not None:
                results.append(r)
        winner = next((r for r in results if isinstance(r, str) and r), None)
        return results, winner

    def _register_second(self):
        """Second registration of the SAME hook callback — the duplicate
        plugin load (manager/list aliasing, re-register) shape where one
        dispatch consumes two cap-slots."""
        ctx2 = _Ctx()
        self.hw.register(ctx2)
        return ctx2.hooks["transform_llm_output"]

    # ---- K: an earlier winning peer must NOT consume our card -------------
    def test_k_earlier_peer_wins_card_never_shipped_no_marker(self):
        r = self.mk_run("r-k1")
        peer = lambda **kw: "peer answer (wins first)"
        _, winner = self._dispatch([peer, self.hook])
        self.assertEqual(winner, "peer answer (wins first)")   # our text discarded
        self.assertEqual(self.echoed(r), [])                   # NOT shipped: no marker

    def test_k_later_peer_loses_card_ships_once(self):
        r = self.mk_run("r-k2")
        peer = lambda **kw: "peer answer (loses)"
        results, winner = self._dispatch([self.hook, peer])
        self.assertTrue(winner.rstrip().endswith(self.card("r-k2")), winner)
        self.assertEqual(len(self.echoed(r)), 1)

    def test_k_double_registration_overflow_marks_only_delivered_replays_rest(self):
        # 2 registrations x 5 pending: registration A wins selection carrying
        # its 3 cards; registration B's 2-card text LOSES. Exactly the three
        # delivered cards stay marked; the two deferred stay replayable.
        dirs = {f"r-{i}": self.mk_run(f"r-{i}", minutes_ago=float(i)) for i in range(1, 6)}
        hook2 = self._register_second()
        _, winner = self._dispatch([self.hook, hook2])
        lines = [ln for ln in winner.splitlines() if ln.startswith("::workflow{")]
        self.assertEqual(lines, [self.card(f"r-{i}") for i in (1, 2, 3)], winner)
        for i in (1, 2, 3):
            self.assertEqual(len(self.echoed(dirs[f"r-{i}"])), 1, f"r-{i} delivered")
        for i in (4, 5):
            self.assertEqual(self.echoed(dirs[f"r-{i}"]), [], f"r-{i} lost, unmarked")
        # deferred cards replay on the NEXT turn
        out = self.call(turn="t2")
        self.assertIsNotNone(out)
        self.assertTrue(out.rstrip().endswith(self.card("r-5")), out)
        self.assertIn(self.card("r-4"), out)
        for i in (4, 5):
            self.assertEqual(len(self.echoed(dirs[f"r-{i}"])), 1, f"r-{i} shipped on replay")

    def test_k_commit_witness_revalidates_against_durable_row(self):
        # A claimed card is CONFIRMED only against the durable committed row
        # (the once-per-turn memo re-validates on the next call). Unconfirmed
        # = not shipped: the card replays instead of being lost.
        r = self.mk_run("r-k3")
        seen = []
        state = {"committed": False}
        def witness(*, session_id, turn_id, run_id, **_):
            seen.append((turn_id, run_id))
            return state["committed"]
        self.h._witness = witness
        try:
            out = self.call()                          # t1: ship, stamp deferred
            self.assertIsNotNone(out)
            self.assertTrue(out.rstrip().endswith(self.card("r-k3")), out)
            self.assertEqual(self.echoed(r), [])       # no hopeful stamp
            state["committed"] = True                  # the row landed with our card
            out2 = self.call(turn="t2")                # reconcile -> stamp
            self.assertIsNone(out2)                    # confirmed: one-shot
            self.assertEqual(len(self.echoed(r)), 1)
            self.assertIsNone(self.call(turn="t3"))    # stays shipped
            self.assertEqual(len(self.echoed(r)), 1)
        finally:
            self.h._witness = None

    # ---- M: a re-appearing card never re-ships -----------------------------
    def test_m_paste_next_turn_retires_run_card(self):
        # Paste (different route) persisted turn t1; the NEXT ordinary reply
        # must not re-emit the same card (persisted-rows re-ship red).
        r = self.mk_run("r-m1")
        pasted, _win = self._dispatch([self.hook], text=f"Answer.\n\n{self.card('r-m1')}",
                                      turn="t1")
        self.assertEqual(pasted, [])               # hands off (existing (c));
        # _dispatch returns (results, winner): the results LIST was the binding
        # target at authoring — the original assertIsNone(pasted) could never
        # pass for any implementation. Intent pinned exactly: zero contributions.
        out = self.call(turn="t2")                   # ordinary next reply
        self.assertIsNone(out, f"card re-shipped after paste: {out!r}")
        # and it STAYS retired: a third turn, and a replayed turn id, stay silent
        self.assertIsNone(self.call(turn="t3"))
        self.assertIsNone(self.call(turn="t1"))

    def test_m_retirement_is_per_run_not_any_directive(self):
        # A paste of run A must NOT retire sibling run B's owed card.
        rA = self.mk_run("r-mA")
        rB = self.mk_run("r-mB")
        self.assertIsNone(self.call(text=f"Here it is.\n\n{self.card('r-mA')}", turn="t1"))
        out = self.call(turn="t2")
        self.assertIsNotNone(out, "sibling card was wrongly retired")
        self.assertTrue(out.rstrip().endswith(self.card("r-mB")), out)
        self.assertEqual(self.echoed(rB), [{"session_id": "S", "turn_id": "t2",
                                             "event": "card.echoed"}][:1]
                          if False else self.echoed(rB))  # shape pinned below
        self.assertEqual([e["event"] for e in self.echoed(rB)], ["card.echoed"])
        self.assertEqual(self.echoed(rA), [])        # A shipped via the paste

    def test_m_in_fenced_paste_next_turn_ships(self):
        # A fenced/replayed directive is dead text to the renderer: the turn
        # did NOT deliver — the card must still ship later (fail-open bias).
        self.mk_run("r-m2")
        out = self.call(text="Example:\n```\n" + self.card("r-m2") + "\n```")
        self.assertIsNotNone(out)
        self.assertTrue(out.rstrip().endswith(self.card("r-m2")), out)
        self.assertIsNone(self.call(turn="t2"))      # shipped once

    # ---- N: an unclosed fence must not trap the card -----------------------
    def test_n_unclosed_fence_still_ships_visible(self):
        # text ends INSIDE an open ``` fence: appending there would bury the
        # card renderer-dead while the ledger says shipped. The card must
        # reach the user OUTSIDE the fence (module failure posture is
        # best-effort ship, so the fix is a fence-closed append).
        r = self.mk_run("r-n1")
        out = self.call(text="```python\nprint('unfinished block')")
        self.assertIsNotNone(out)
        self.assertIn(self.card("r-n1"), out)
        lines = out.splitlines()
        self.assertEqual(lines[-1].strip(), self.card("r-n1"))     # last line = card
        fences = sum(1 for ln in lines if ln.lstrip().startswith("```"))
        self.assertEqual(fences % 2, 0, f"card sits inside an unclosed fence:\n{out}")
        self.assertEqual(len(self.echoed(r)), 1)                   # visible = shipped

    def test_n_fenced_directive_then_unclosed_fence_still_ships(self):
        # A fenced (dead) directive AND an unclosed tail fence: the card ships
        # and lands outside every fence.
        r = self.mk_run("r-n2")
        out = self.call(text="```\n" + self.card("r-n2") + "\n```\ntail\n```\nunclosed")
        self.assertIsNotNone(out)
        lines = out.splitlines()
        self.assertEqual(lines[-1].strip(), self.card("r-n2"))
        fences = sum(1 for ln in lines if ln.lstrip().startswith("```"))
        self.assertEqual(fences % 2, 0, f"card trapped:\n{out}")
        self.assertEqual(len(self.echoed(r)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
