#!/usr/bin/env python3
"""#50 (epic #49, door half): discovery-first library.

Contracts pinned here:
  (1) RICH LIBRARY: library rows are entries {name, description, tags, provenance,
      path-relative id}; save stores the envelope {meta:{description,tags}, graph:{...}};
      R10 migration law — existing BARE graph files still load and list; unknown file
      shapes are skipped with a listed warning, never a crash.
  (2) SUBMIT: model-reachable write to runs_root()/inbox; why_not_library REQUIRED
      >=80 chars; the SAME graph validation act_run uses (no second validator);
      dedupe on identical graph digest + same submitted_by reports the existing id
      (hint, not a bounce); `inbox` action lists newest-first for a launcher and is
      LIST ONLY (nothing auto-joins the library). Consent gate shape mirrors save:
      submit accepts what save accepts; the launcher bounce happens at run.
  (3) FUZZY NUDGE: run from=<unknown> names closest library entries (incl general/)
      and points at the submit path with why_not_library.
  (4) SMART-DEFAULTS AUDIT: documented in references/operations.md ('Smart defaults').

Standalone script (no pytest): PYTHONPATH=/opt/duckwork
/opt/duckwork/.venv/bin/python tests/test_door_lib_50.py
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wf_door_50", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso71_door50; _iso71_door50.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT

G = {"name": "lib50", "nodes": [{"id": "x", "type": "echo", "output": {"ok": True}}]}
WHY = "the library has no graph for this shape: " + "it fans discovery before build " * 3  # >=80


class DoorLib50(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        env = patch.dict(os.environ, {"WF_RUNS_ROOT": str(self.root),
                                      "DUCKWORK_HOME": str(self.root / "home")})
        env.start()
        self.addCleanup(env.stop)
        # Standalone isolation (house convention, cf. test_steer_live_40 popping the
        # steer env before the stranger check): a door test must never inherit a
        # surrounding workflow spawn's baked steer env — that would route the
        # maintainer-side inbox list into the child-pull branch.
        for k in ("DUCKWORK_WF_STEER_FILE", "DUCKWORK_WF_STEER_CURSOR", "DUCKWORK_WF_STEER_HWM",
                  "DUCKWORK_WF_STEER_NODE", "DUCKWORK_WF_STEER_SPAWN", "DUCKWORK_WF_RUN_DIR"):
            os.environ.pop(k, None)
        self.spawns = []
        spawn = patch.object(door, "_spawn_runner", side_effect=lambda r: self.spawns.append(r))
        spawn.start()
        self.addCleanup(spawn.stop)

    def lib(self):
        return door.act_library({})

    # ---------------- (1) rich library ----------------

    def test_save_envelope_and_rich_rows(self):
        r = door.act_save({"graph": G, "name": "audit-flow", "description": "audit a repo",
                           "tags": ["review", "audit"], "source": "repo/audit.json"})
        self.assertEqual(r.get("saved"), "audit-flow")
        raw = json.loads((door.library_root() / "audit-flow.json").read_text())
        self.assertIn("graph", raw)
        self.assertEqual(raw["meta"].get("description"), "audit a repo")
        self.assertEqual(raw["meta"].get("tags"), ["review", "audit"])
        row = next(x for x in self.lib()["library"] if x["name"] == "audit-flow")
        self.assertEqual(row["description"], "audit a repo")
        self.assertEqual(row["tags"], ["review", "audit"])
        self.assertEqual(row["owner"], "default")          # provenance shown like before
        self.assertTrue(row["source"])
        self.assertTrue(row["source_digest"])
        self.assertIn("id", row)                            # path-relative id
        self.assertEqual(row["id"], "audit-flow.json")
        # the envelope replays: run from= unwraps it and launches
        started = door.act_run({"from": "audit-flow"})
        self.assertTrue(started.get("run_id"), started)
        self.assertEqual(len(self.spawns), 1)

    def test_r10_bare_form_still_loads_and_lists(self):
        # R10 migration law: files saved in the OLD bare-graph form keep working.
        door.library_root().mkdir(parents=True, exist_ok=True)
        legacy = dict(G, name="legacy-form", description="old style")
        (door.library_root() / "legacy-form.json").write_text(json.dumps(legacy))
        row = next(x for x in self.lib()["library"] if x["name"] == "legacy-form")
        self.assertEqual(row["description"], "old style")
        started = door.act_run({"from": "legacy-form"})
        self.assertTrue(started.get("run_id"), started)

    def test_unknown_shapes_skipped_with_warning_never_crash(self):
        door.library_root().mkdir(parents=True, exist_ok=True)
        (door.library_root() / "broken.json").write_text("not json {")
        (door.library_root() / "shapeless.json").write_text(json.dumps({"unexpected": True}))
        door.act_save({"graph": G, "name": "good"})
        out = self.lib()
        names = {x["name"] for x in out["library"]}
        self.assertIn("good", names)
        self.assertNotIn("broken", names)
        self.assertNotIn("shapeless", names)
        skipped = {Path(s).stem for s in out.get("skipped", [])}
        self.assertEqual(skipped, {"broken", "shapeless"})
        # a broken shape must also never crash run from=
        self.assertIn("no library graph", door.act_run({"from": "broken"}).get("error", ""))

    def test_quarantine_fixture_pair_good_beside_broken(self):
        # F-2 (#62) fixture — EXACT pair: valid good.json beside the malformed
        # broken.json. Law: fail-closed on the entry, fail-open on the library.
        GOOD = {"name": "good", "nodes": [{"id": "e", "type": "echo", "output": 1}]}
        BROKEN = {"meta": {"description": "junk"}, "graph": {"nodes": ["oops"]}}
        root = door.library_root(); root.mkdir(parents=True, exist_ok=True)
        (root / "good.json").write_text(json.dumps(GOOD))
        (root / "broken.json").write_text(json.dumps(BROKEN))
        out = self.lib()                                       # no exception
        names = {x["name"] for x in out["library"]}
        self.assertIn("good", names)                            # good still usable
        self.assertNotIn("broken", names)
        q = {x["name"]: x["reason"] for x in out["quarantined"]}
        self.assertIn("broken", q)                              # bad is named...
        self.assertEqual(q["broken"], "invalid: nodes[0] is not an object")  # ...with its typed reason
        self.assertIn("broken.json", out["skipped"])
        r = door.act_run({"from": "good"})                      # replay works beside it
        self.assertIn("run_id", r)
        r = door.act_run({"from": "broken"})                    # bad entry: nudge, never crash
        self.assertIn("no library graph", r.get("error", ""))
        self.assertNotIn("run_id", r)
        typo = door.act_run({"from": "good-typo"})              # typo hint still works
        self.assertIn("good", typo.get("closest", []))
        t = door._wf_command("")                                # /wf lists both rows
        self.assertIn("good", t)
        self.assertIn("broken", t)
        self.assertIn("invalid: nodes[0] is not an object", t)
        t = door._wf_command("broken")                          # /wf bad named, refusal shown
        self.assertIn("refused: invalid: nodes[0] is not an object", t)
        (root / "broken.json").unlink()                        # removal fully restores
        out = self.lib()
        self.assertEqual({x["name"] for x in out["library"]}, {"good"})
        self.assertNotIn("quarantined", out)
        self.assertNotIn("skipped", out)

    def test_tag_validation_fail_closed(self):
        bad = door.act_save({"graph": G, "name": "t1", "tags": ["ok"] * 11})
        self.assertIn("tags", bad.get("error", ""))
        bad = door.act_save({"graph": G, "name": "t2", "tags": ["BAD TAG!"]})
        self.assertIn("tag", bad.get("error", ""))
        bad = door.act_save({"graph": G, "name": "t3", "tags": "review"})
        self.assertIn("tags", bad.get("error", ""))
        bad = door.act_save({"graph": G, "name": "t4", "tags": []})
        self.assertIn("tags", bad.get("error", ""))
        self.assertFalse((door.library_root() / "t1.json").exists())
        self.assertFalse((door.library_root() / "t2.json").exists())

    # ---------------- (2) submit ----------------

    def submit_dir(self):
        return self.root / "inbox"

    def test_submit_requires_why(self):
        miss = door.act_submit({"graph": G})
        self.assertIn("why_not_library", miss.get("error", ""))
        short = door.act_submit({"graph": G, "why_not_library": "x" * 79})
        self.assertIn("80", short.get("error", ""))
        self.assertEqual(list(self.submit_dir().glob("*.json")) if self.submit_dir().exists() else [], [])

    def test_submit_reuses_act_run_graph_validation(self):
        bad_graph = {"name": "bad", "nodes": [{"id": "a", "type": "agent", "goal": "g", "nope": 1}]}
        s = door.act_submit({"graph": bad_graph, "why_not_library": WHY})
        self.assertIn("graph invalid", s.get("error", ""))
        self.assertFalse(self.submit_dir().exists() and list(self.submit_dir().glob("*.json")))
        # the identical graph is refused by run too — same validator, same verdict
        r = door.act_run({"graph": bad_graph})
        self.assertEqual(r.get("error", "").split(":")[0], s.get("error", "").split(":")[0])

    def test_submit_roundtrip_and_inbox_list_newest_first(self):
        s1 = door.act_submit({"graph": G, "why_not_library": WHY, "lane": "team/a"})
        self.assertTrue(s1.get("ok"), s1)
        rid = s1["submitted"]
        self.assertTrue(rid.endswith("-lib50"))
        entry = json.loads((self.submit_dir() / f"{rid}.json").read_text())
        self.assertEqual(set(entry), {"submitted_at", "submitted_by", "why_not_library", "lane", "graph"})
        self.assertEqual(entry["submitted_by"], door._common.launcher_profile())
        self.assertEqual(entry["lane"], "team/a")
        self.assertEqual(entry["graph"], dict(G))
        # a second, DIFFERENT graph from the same launcher lands; list is newest-first
        g2 = {"name": "lib50-b", "nodes": [{"id": "y", "type": "echo", "output": 1}]}
        s2 = door.act_submit({"graph": g2, "why_not_library": WHY})
        self.assertTrue(s2.get("ok"), s2)
        # pin distinct submitted_at so newest-first is deterministic
        f1, f2 = (self.submit_dir() / f"{s1['submitted']}.json"), (self.submit_dir() / f"{s2['submitted']}.json")
        e1, e2 = json.loads(f1.read_text()), json.loads(f2.read_text())
        e1["submitted_at"] = "2026-01-01T00:00:00+00:00"
        e2["submitted_at"] = "2026-01-02T00:00:00+00:00"
        f1.write_text(json.dumps(e1))
        f2.write_text(json.dumps(e2))
        listing = door.act_inbox({})
        ids = [x["id"] for x in listing["inbox"]]
        self.assertEqual(ids, [s2["submitted"], s1["submitted"]])
        self.assertEqual(listing["inbox"][0]["why_not_library"], WHY)
        # LIST ONLY: nothing auto-joined the library
        self.assertEqual([x["name"] for x in self.lib()["library"]], [])

    def test_submit_dedupe_same_digest_and_submitter_reports_existing(self):
        s1 = door.act_submit({"graph": G, "why_not_library": WHY})
        again = door.act_submit({"graph": G, "why_not_library": WHY + " (restated)"})
        self.assertTrue(again.get("deduped"), again)
        self.assertEqual(again["existing"], s1["submitted"])
        self.assertNotIn("error", again)  # hint, not a bounce
        # a DIFFERENT submitter with the identical graph is not deduped
        with patch.dict(os.environ, {"DUCKWORK_HOME": str(self.root / "profiles" / "teammate")}):
            s3 = door.act_submit({"graph": G, "why_not_library": WHY})
        self.assertTrue(s3.get("ok"), s3)
        self.assertNotEqual(s3["submitted"], s1["submitted"])

    def test_submit_graph_path_source(self):
        p = self.root / "hand.json"
        p.write_text(json.dumps(G))
        s = door.act_submit({"graph_path": str(p), "why_not_library": WHY})
        self.assertTrue(s.get("ok"), s)
        dup = door.act_submit({"graph_path": str(p), "why_not_library": WHY})
        self.assertTrue(dup.get("deduped"), dup)

    def test_submit_consent_shape_mirrors_save(self):
        # the SAME graph carrying an unconsented profile node: save accepts it,
        # submit accepts it (model-reachable write, same gate shape as save);
        # the bounce belongs to run, where launcher consent is enforced.
        pg = {"name": "pg", "nodes": [{"id": "a", "type": "agent", "goal": "x", "profile": "teammate"}]}
        tgt = self.root / "home" / "profiles" / "teammate"
        tgt.mkdir(parents=True)
        (tgt / "config.yaml").write_text("model: some/model\n")
        (tgt / "workflow_team.json").write_text(json.dumps({"accept_from": ["nobody"]}))
        self.assertIn("saved", door.act_save({"graph": pg, "name": "pg"}))
        s = door.act_submit({"graph": pg, "why_not_library": WHY})
        self.assertTrue(s.get("ok"), s)
        run = door.act_run({"graph": pg})
        self.assertIn("graph invalid", run.get("error", ""))   # launcher bounced at run
        self.assertIn("accept", run.get("error", ""))
        self.assertEqual(self.spawns, [])

    # ---------------- (3) fuzzy nudge ----------------

    def test_general_subset_lists_and_replays(self):
        door.library_root().mkdir(parents=True, exist_ok=True)
        (door.library_root() / "general").mkdir(exist_ok=True)
        (door.library_root() / "general" / "nightly-sweep.json").write_text(
            json.dumps({"name": "nightly-sweep", "nodes": [{"id": "e", "type": "echo", "output": 1}]}))
        names = {x["name"] for x in self.lib()["library"]}
        self.assertIn("general/nightly-sweep", names)        # (1) incl. the general/ subset
        self.assertEqual({x["id"] for x in self.lib()["library"]
                          if x["name"] == "general/nightly-sweep"},
                         {"general/nightly-sweep.json"})
        started = door.act_run({"from": "general/nightly-sweep"})
        self.assertTrue(started.get("run_id"), started)

    def test_from_unknown_error_is_the_nudge(self):
        door.act_save({"graph": dict(G, name="audit-notes"), "name": "audit-notes"})
        door.library_root().mkdir(parents=True, exist_ok=True)
        (door.library_root() / "general").mkdir(exist_ok=True)
        (door.library_root() / "general" / "nightly-sweep.json").write_text(
            json.dumps({"name": "nightly-sweep", "nodes": [{"id": "e", "type": "echo", "output": 1}]}))
        r = door.act_run({"from": "audit-note"})
        err = r.get("error", "")
        self.assertIn("no library graph", err)
        self.assertIn("closest:", err)
        self.assertIn("audit-notes", err)                    # fuzzy over library names
        self.assertIn("hand-rolled", err)
        self.assertIn("submit", err)
        self.assertIn("why_not_library", err)
        self.assertIsInstance(r.get("closest"), list)
        self.assertLessEqual(len(r["closest"]), 3)
        # general/ names participate in the fuzzy match set
        r2 = door.act_run({"from": "nightly-swee"})
        self.assertIn("nightly-sweep", json.dumps(r2))

    def test_from_unknown_empty_library_still_nudges(self):
        r = door.act_run({"from": "whatever"})
        err = r.get("error", "")
        self.assertIn("no library graph", err)
        self.assertIn("submit", err)
        self.assertIn("why_not_library", err)

    def test_general_save_echoes_replayable_name(self):
        # #50 review gap: saving `general/<name>` must echo the FULL replayable name
        # (plain stem would break `run from=` / the hint / /wf round-trip).
        r = door.act_save({"graph": G, "name": "general/pub-one", "description": "public"})
        self.assertEqual(r.get("saved"), "general/pub-one", r)
        self.assertIn("from=general/pub-one", r.get("hint", ""))
        self.assertTrue((door.library_root() / "general" / "pub-one.json").is_file())
        started = door.act_run({"from": r["saved"]})
        self.assertTrue(started.get("run_id"), started)

    def test_inbox_kind_submissions_explicit(self):
        # explicit kind routes to the maintainer list even with NO submissions;
        # a stranger child-pull (no env, no kind) stays the honest error.
        empty = door.act_inbox({"kind": "submissions"})
        self.assertTrue(empty.get("ok"), empty)
        self.assertEqual(empty["inbox"], [])
        stranger = door.act_inbox({})
        self.assertFalse(stranger.get("ok"))
        self.assertIn("not a workflow child spawn", stranger.get("error", ""))
        bad = door.act_inbox({"kind": "junk"})
        self.assertIn("unknown inbox kind", bad.get("error", ""))

    # ---------------- (5) F-1 (#62 review): inline graph size cap ----------------
    # The graph_path branch enforces GRAPH_MAX_BYTES on the file's bytes; the INLINE
    # branch must enforce the same cap on the serialized graph, BEFORE any write
    # (adversary repro at c12269f: an ~11MB inline graph wrote a 12,309,225-byte
    # inbox file — 11.7x over the cap). Parity law: submit, save (and run/amend,
    # same shared _input_graph helper) all refuse; the refusing call writes NOTHING.

    def _sized_graph(self, name, target_bytes):
        """A validator-clean echo graph whose COMPACT serialization is exactly
        target_bytes (ASCII padding is byte-for-byte in the dump, so the size is
        computed, never guessed)."""
        g = {"name": name, "nodes": [{"id": "e", "type": "echo", "output": {"pad": ""}}]}
        base = len(json.dumps(g, ensure_ascii=False).encode("utf-8"))
        g["nodes"][0]["output"]["pad"] = "p" * max(0, target_bytes - base)
        return g

    def assertCapError(self, res):
        err = res.get("error", "")
        self.assertIn("exceeds", err, res)
        self.assertIn(str(door.GRAPH_MAX_BYTES), err, res)
        self.assertNotIn("ok", res)
        self.assertNotIn("saved", res)
        self.assertNotIn("run_id", res)

    def test_f1_oversized_inline_graph_submit_caps_and_writes_nothing(self):
        # seed the inbox with one legitimate entry so the no-write proof is a diff
        # against a non-empty listing, not a vacuous "dir still empty".
        s0 = door.act_submit({"graph": G, "why_not_library": WHY})
        self.assertTrue(s0.get("ok"), s0)
        before = sorted(os.listdir(self.submit_dir()))
        big = self._sized_graph("f1-big", door.GRAPH_MAX_BYTES + 4096)
        self.assertCapError(door.act_submit({"graph": big, "why_not_library": WHY}))
        self.assertEqual(sorted(os.listdir(self.submit_dir())), before)  # no-write proof

    def test_f1_oversized_inline_graph_save_caps_and_writes_nothing(self):
        s0 = door.act_save({"graph": G, "name": "seed"})
        self.assertIn("saved", s0)
        before = sorted(os.listdir(door.library_root()))
        big = self._sized_graph("f1-huge", door.GRAPH_MAX_BYTES + 4096)
        self.assertCapError(door.act_save({"graph": big, "name": "f1-huge"}))
        self.assertEqual(sorted(os.listdir(door.library_root())), before)  # no-write proof
        self.assertFalse((door.library_root() / "f1-huge.json").exists())

    def test_f1_oversized_inline_graph_run_caps_and_creates_no_run_dir(self):
        # parity law: the SAME helper guards every inline entry point, run included —
        # no run directory may appear for a refused launch.
        root = self.root
        (root / "inbox").mkdir(parents=True, exist_ok=True)
        before = sorted(os.listdir(root))
        big = self._sized_graph("f1-run-big", door.GRAPH_MAX_BYTES + 4096)
        self.assertCapError(door.act_run({"graph": big}))
        self.assertEqual(sorted(os.listdir(root)), before)  # no-run-dir proof
        self.assertEqual(self.spawns, [])

    def test_f1_just_under_cap_inline_graph_succeeds(self):
        # the cap must cap, not strangle: a graph whose serialized size sits just
        # under GRAPH_MAX_BYTES still submits AND saves.
        near = self._sized_graph("f1-near", door.GRAPH_MAX_BYTES - 1024)
        s = door.act_submit({"graph": near, "why_not_library": WHY})
        self.assertTrue(s.get("ok"), s)
        self.assertTrue((self.submit_dir() / f"{s['submitted']}.json").is_file())
        v = door.act_save({"graph": near, "name": "f1-near"})
        self.assertIn("saved", v)
        self.assertTrue((door.library_root() / "f1-near.json").is_file())

    # ---------------- (4) smart-defaults audit doc ----------------

    def test_smart_defaults_doc_section(self):
        doc = (ROOT / "references" / "operations.md").read_text()
        self.assertIn("## Smart defaults", doc)
        self.assertIn("submit", doc)
        self.assertIn("lane_key", doc)


if __name__ == "__main__":
    unittest.main()
