#!/usr/bin/env python3
"""est-2ek.1.46: a literal node.model 'provider/model' with no node.provider reached the
child as a bare `-m provider/model` (no --provider), so the child spoke to the seat's
DEFAULT route with the prefixed id and died HTTP 400, while the alias for the same model
worked (aliases bake their provider at submit). The door now bakes the provider for a
literal whose prefix is a provider the seat itself routes through (the 'provider/' prefix
of a seat alias or tier target, or a configured `providers:` key).

Pinned here:
  (1) alias 'sol' and the literal 'openai-codex/gpt-6-sol' resolve to the SAME route
      (provider openai-codex, model gpt-6-sol / alias target) in routes.resolved;
  (2) the author's request is preserved in routes.requested (provider None, literal model);
  (3) a vendor-namespaced id whose prefix the seat does not route through is left
      alone (an aggregator route's 'vendor/model' is not a provider claim);
  (4) an explicit node.provider is never overridden; re-resolving a baked node is a no-op.

Run (stdlib only): python3 tests/test_literal_provider_prefix_46.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
spec = importlib.util.spec_from_file_location("wf_door_46", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

SEAT = {"default": "seat-default", "aliases": {"sol": "openai-codex/gpt-6-sol"}}


def node(nid, **kw):
    return {"id": nid, "type": "agent", "goal": "route", **kw}


class LiteralProviderPrefix46(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="wf46-")
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, {"DUCKWORK_HOME": tmp.name})
        env.start()
        self.addCleanup(env.stop)
        for target, value in (("_seat_model_cfg", lambda: SEAT), ("model_tiers", lambda: {})):
            p = patch.object(door, target, value)
            p.start()
            self.addCleanup(p.stop)

    def resolve(self, *nodes):
        err, _table, routes = door._resolve_models(list(nodes))
        self.assertIsNone(err, err)
        return routes

    def test_alias_and_literal_resolve_to_the_same_route(self):
        alias, literal = node("alias", model="sol"), node("literal", model="openai-codex/gpt-6-sol")
        routes = self.resolve(alias, literal)
        self.assertEqual(routes["alias"]["resolved"]["provider"], "openai-codex")
        self.assertEqual(routes["literal"]["resolved"],
                         {"provider": "openai-codex", "model": "gpt-6-sol"})
        self.assertEqual(literal["provider"], "openai-codex")
        self.assertEqual(literal["model"], SEAT["aliases"]["sol"].partition("/")[2])

    def test_request_is_preserved_in_routes(self):
        routes = self.resolve(node("literal", model="openai-codex/gpt-6-sol"))
        self.assertEqual(routes["literal"]["requested"],
                         {"provider": None, "model": "openai-codex/gpt-6-sol"})

    def test_literal_equal_to_a_tier_target_still_bakes(self):
        # the seat-owned name set (tier targets) is where the literal usually lives
        with patch.object(door, "model_tiers", lambda: {"sol-tier": "openai-codex/gpt-6-sol"}):
            n = node("literal", model="openai-codex/gpt-6-sol")
            routes = self.resolve(n)
        self.assertEqual(routes["literal"]["resolved"],
                         {"provider": "openai-codex", "model": "gpt-6-sol"})

    def test_unrouted_vendor_prefix_is_left_literal(self):
        n = node("vendor", model="vendor-a/alpha")
        routes = self.resolve(n)
        self.assertNotIn("provider", n)
        self.assertEqual(n["model"], "vendor-a/alpha")
        self.assertEqual(routes["vendor"]["resolved"], {"provider": None, "model": "vendor-a/alpha"})

    def test_explicit_provider_wins_and_rebake_is_a_noop(self):
        explicit = node("explicit", provider="other-prov", model="openai-codex/gpt-6-sol")
        self.resolve(explicit)
        self.assertEqual(explicit["provider"], "other-prov")
        literal = node("literal", model="openai-codex/gpt-6-sol")
        self.resolve(literal)
        baked = dict(literal)
        self.resolve(literal)
        self.assertEqual(literal, baked)


LITERAL = "openai-codex/gpt-6-sol"


class BakedIdentityComparators46(unittest.TestCase):
    """#291 review (zap): the bake must not erase the full 'provider/model' identity from
    the comparators that ran on the author form before it — policy bans at amend (F1),
    replay-skip freezing of the author literal (F2), and quota-cache keys (F3)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="wf46b-")
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        env = patch.dict(os.environ, {"DUCKWORK_HOME": tmp.name,
                                      "WF_RUNS_ROOT": str(self.home / "workflows"),
                                      "WF_QUOTA_CACHE": str(self.home / "quota.json")})
        env.start()
        self.addCleanup(env.stop)
        self.seat = {"default": "seat-default", "aliases": dict(SEAT["aliases"])}
        for target, value in (("_seat_model_cfg", lambda: self.seat), ("model_tiers", lambda: {}),
                              ("_ping_route_once", lambda p, m: {"liveness": "unknown"})):
            p = patch.object(door, target, value)
            p.start()
            self.addCleanup(p.stop)

    def author(self, **graph):
        return {"name": "lit46", "nodes": [node("a", model=LITERAL)], **graph}

    def commit_run(self, rid="run-46"):
        from wfcommon import efp
        g = door._common.apply_graph_defaults(self.author())
        err, _t, _r = door._resolve_models(g["nodes"])
        self.assertIsNone(err, err)
        self.assertEqual((g["nodes"][0].get("provider"), g["nodes"][0]["model"]),
                         ("openai-codex", "gpt-6-sol"))
        r = self.home / "workflows" / rid
        (r / "nodes").mkdir(parents=True)
        (r / "graph.json").write_text(json.dumps(g))
        byid = {n["id"]: n for n in g["nodes"]}
        for n in g["nodes"]:
            (r / "nodes" / f"{n['id']}.json").write_text(
                json.dumps({"status": "done", "efp": efp(byid, n)}))
        return rid

    def amend(self, rid, graph):
        return door.act_amend({"run_id": rid, "graph": graph, "dry_run": True})

    # F1: a full-id ban still binds the amend path (policy runs after the bake there)
    def test_f1_full_id_ban_binds_baked_node(self):
        baked = node("a", provider="openai-codex", model="gpt-6-sol")
        err = door._model_policy_error({"nodes": [baked],
                                        "model_policy": {"forbidden_models": [LITERAL]}})
        self.assertIsNotNone(err)

    def test_f1_full_id_ban_refuses_amend(self):
        rid = self.commit_run()
        out = self.amend(rid, self.author(model_policy={"forbidden_models": [LITERAL]}))
        self.assertIn("forbidden", str(out.get("error")), out)

    def test_f1_seat_ban_refuses_amend(self):
        rid = self.commit_run()
        self.seat["workflows_forbidden_models"] = [LITERAL]
        out = self.amend(rid, self.author())
        self.assertIn("forbidden", str(out.get("error")), out)

    # F2: the author literal replays as the committed baked node -> frozen, unchanged
    def test_f2_author_literal_freezes_committed_bake(self):
        rid = self.commit_run()
        old = json.loads((self.home / "workflows" / rid / "graph.json").read_text())
        g = door._common.apply_graph_defaults(self.author())
        _ob, frozen = door._frozen_committed(door.run_dir(rid), old, g["nodes"])
        self.assertEqual(frozen, {"a"})
        out = self.amend(rid, self.author())
        self.assertIsNone(out.get("error"), out)
        self.assertEqual((out.get("unchanged"), out.get("will_rerun")), (["a"], []), out)

    def test_f2_seat_alias_removed_does_not_rerun_done_work(self):
        rid = self.commit_run()
        self.seat["aliases"] = {}
        out = self.amend(rid, self.author())
        self.assertIsNone(out.get("error"), out)
        self.assertEqual((out.get("unchanged"), out.get("will_rerun")), (["a"], []), out)

    # F3: a quota entry stamped under the pre-change full key still refuses
    def test_f3_full_id_quota_key_still_refuses(self):
        (self.home / "quota.json").write_text(json.dumps(
            {LITERAL: {"resets_epoch": time.time() + 3600, "at": time.time(), "marker": "q"}}))
        g = self.author()
        err, _t, routes = door._resolve_models(g["nodes"])
        self.assertIsNone(err, err)
        msg = door._quota_refusal(g, routes)
        self.assertIsNotNone(msg)
        self.assertIn("quota-exhausted", msg)


if __name__ == "__main__":
    unittest.main()
