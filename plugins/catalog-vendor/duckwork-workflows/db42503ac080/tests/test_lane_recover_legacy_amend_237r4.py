#!/usr/bin/env python3
"""PR #237 r4 (zap blocker, B3): the recovery path must honor LEGACY
def_hash-only done commits through the SAME primitive the read model uses.

The gap (zap certification, QUEUE-RESULTS rows[pr=237], control
logs237/genuine-legacy-amend-control.log): crashed_no_exit_signature routed a
terminal aggregate through wfcommon.node_rec ONLY when the record carried an
`efp` key ("the ONE validity rule" branch). A VALID legacy (pre-efp) record —
def_hash + fp_rule_version only — skipped node_rec entirely (`continue`), so a
genuinely amended legacy done commit read `pending` in wfcommon while the
watchdog signature stayed false: recovery never spawned and unfinished work
hid from the watchdog forever. The legacy-cancelled control (failed/cancelled
legacy commit == pending per the read model, node_rec's cancelled branch) was
skipped by the same bypass.

Fix shape (verified here): when wfcommon is importable, terminal aggregates go
through node_rec — the efp-era branch stays byte-identical; legacy records are
validated via the same primitive (which internally applies the legacy-chain
rule), never skipped as no-efp.

Scenes (mirroring zap's controls under the zap run dir):
  A. valid legacy done (def_hash-only, matching graph): NOT a signature.
  B. same commit, genuine amendment (graph goal changed, no new commit):
     pending in wfcommon AND watchdog_signature true (zap's control exits 1
     on today's head — this is the RED).
  C. legacy cancelled commit (failed + error_class=cancelled): signature true.
  D. efp-era behavior byte-identical: valid efp done => no signature; genuine
     efp amend => signature.
  E. recover_crashed_runner on scene B SPAWNS (injectable spawn), writes the
     receipt + guard — proving the fix reaches the recovery entry, not just
     the predicate.

Plain script, no pytest: exits non-zero on any red.
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import wfcommon as wc  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FAILS = []


def check(name, cond, detail=None):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  ::  " + str(detail)[:600]))
    if not cond:
        FAILS.append(name)


DEAD_PID = 999_998 if sys.maxsize > 2**16 else 32_766


def mk_scene(runs, run_id, node, rec):
    """A dead run whose aggregate commit is `rec` under graph node `node`."""
    r = runs / run_id
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps({"name": run_id, "nodes": [node]}))
    (r / "run.json").write_text("{}")
    (r / "wf.pid").write_text(str(DEAD_PID))
    (r / "nodes" / f"{node['id']}.json").write_text(json.dumps(rec))
    return r


def main():
    lr = load("lane_recover_237r4", ROOT / "scripts" / "lane_recover.py")
    sig = getattr(lr, "crashed_no_exit_signature", None)
    recover = getattr(lr, "recover_crashed_runner", None)
    check("r4: crashed_no_exit_signature exposed", callable(sig), "attribute missing")
    check("r4: recover_crashed_runner exposed", callable(recover), "attribute missing")
    if not (callable(sig) and callable(recover)):
        print(f"FAILED: {FAILS}")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="lr237r4-") as td:
        runs = Path(td) / "workflows"
        runs.mkdir()

        # --- zap's control, verbatim shape: legacy237.py -------------------
        n = {"id": "build", "type": "agent", "goal": "original"}
        r = mk_scene(runs, "r237-legacy-amend", n,
                     {"status": "done", "def_hash": wc.def_hash(n),
                      "fp_rule_version": wc.FP_RULE_VERSION})
        byid = {n["id"]: n}

        # A. the valid legacy done commit: read model done, NOT a signature.
        st_a = wc.node_rec(r, n, byid)[0]
        sig_a = bool(sig(r))
        check("A: valid legacy done reads done in wfcommon", st_a == "done", st_a)
        check("A: valid legacy done is NOT a crashed-no-exit signature", not sig_a,
              "signature fired on a valid legacy commit")

        # B. genuine amendment: the graph changed after the commit; no new
        #    commit exists. Read model reads pending; the watchdog MUST agree.
        n2 = dict(n, goal="amended")
        (r / "graph.json").write_text(json.dumps({"name": r.name, "nodes": [n2]}))
        byid2 = {n2["id"]: n2}
        st_b = wc.node_rec(r, n2, byid2)[0]
        sig_b = bool(sig(r))
        check("B: genuinely amended legacy done reads pending in wfcommon",
              st_b == "pending", st_b)
        check("B: genuinely amended legacy done IS a crashed-no-exit signature "
              "(zap's genuine-legacy-amend control must not hide unfinished work)",
              sig_b, "watchdog_signature=false — recovery would never spawn")

        # C. legacy cancelled commit (failed + error_class=cancelled): the read
        #    model reads pending (stop != failure); the watchdog must too.
        nc = {"id": "work", "type": "agent", "goal": "first task"}
        rc = mk_scene(runs, "r237-legacy-cancelled", nc,
                      {"status": "failed", "error_class": "cancelled",
                       "def_hash": wc.def_hash(nc), "fp_rule_version": wc.FP_RULE_VERSION})
        st_c = wc.node_rec(rc, nc, {nc["id"]: nc})[0]
        check("C: legacy cancelled reads pending in wfcommon", st_c == "pending", st_c)
        check("C: legacy cancelled IS a crashed-no-exit signature", bool(sig(rc)),
              "signature false — cancelled legacy work hides from the watchdog")

        # D. efp-era behavior byte-identical.
        ne = {"id": "build", "type": "agent", "goal": "ship it"}
        re_ = mk_scene(runs, "r237-efp-valid", ne,
                       {"status": "done", "def_hash": wc.def_hash(ne),
                        "efp": wc.efp({ne["id"]: ne}, ne),
                        "fp_rule_version": wc.FP_RULE_VERSION})
        check("D: efp-valid done commit is NOT a signature (unchanged behavior)",
              not bool(sig(re_)), "signature fired on a valid efp commit")
        ne2 = dict(ne, goal="changed")
        (re_ / "graph.json").write_text(json.dumps({"name": re_.name, "nodes": [ne2]}))
        check("D: efp-era genuine amend IS a signature (unchanged behavior)",
              bool(sig(re_)), "signature false on efp amend")

        # E. the recovery entry itself: scene B must spawn through
        #    recover_crashed_runner (zap: "recover_crashed_runner never spawns").
        seen = []
        res = recover(r, spawn=lambda run: seen.append(run) or 424242)
        check("E: recover_crashed_runner spawns on the amended-legacy scene",
              res.get("respawned") is True, res)
        check("E: one runner_respawn receipt written on the confirmed spawn",
              any(json.loads(l).get("event") == "runner_respawn"
                  for l in (r / "events.jsonl").read_text().splitlines() if l.strip())
              if (r / "events.jsonl").exists() else False, "no receipt")
        check("E: guard written (exactly-once per fingerprint)",
              (r / "respawn_guard.json").exists(), "no guard")
        # and the valid scene A twin must still refuse to spawn
        rA = mk_scene(runs, "r237-legacy-valid-nospawn",
                      {"id": "build", "type": "agent", "goal": "original"},
                      {"status": "done", "def_hash": wc.def_hash(n),
                       "fp_rule_version": wc.FP_RULE_VERSION})
        resA = recover(rA, spawn=lambda run: 424242)
        check("E: valid legacy done never spawns (no signature)",
              resA.get("respawned") is False, resA)

    if FAILS:
        print(f"FAILED: {FAILS}")
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
