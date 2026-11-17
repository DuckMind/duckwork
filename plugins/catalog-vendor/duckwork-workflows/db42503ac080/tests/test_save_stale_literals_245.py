#!/usr/bin/env python3
"""est-2ek.1.245 regression pin: `save` must WARN when a reusable library graph has
ZERO {run.KEY} binding points but its operative text hard-codes launch-varying
literals (ledger keys, branch names, lane paths). Such graphs silently replay
stale values on every `run from=<name>` — 1.0.13's run_context exists but nothing
forced authors to add binding points, so shelved fb-fix-shaped graphs froze the
launch that produced them.

Law: the warning is NON-FATAL (save still lands the entry — warn-and-surface,
same family as include_notes); a clean save's response keys stay byte-identical
(no empty save_warnings key — golden-solo asserts on the saved response shape).

Four parts, standalone (no pytest), house style. Pinned per #71 law:
WF_RUNS_ROOT + wf_test_isolation so nothing here can touch the real estate shelf.
"""
import importlib.util, json, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
ok = True


def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " if cond is False else "SKIP ") + label
          + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)


sys.path.insert(0, "/opt/duckwork")
spec = importlib.util.spec_from_file_location("hw245", str(BUILD / "__init__.py"))
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso  # noqa: E402
_iso.install(door)

# The stale shape: fb-fix-style goal text frozen from one launch — ledger key,
# branch name, and a lane path, and NOT a single {run.KEY} placeholder.
# The lane path is assembled at runtime, never one literal byte: this module
# SHIPS (pack ZIP + export audit) and an operator's absolute home path in
# shipped bytes is exactly the R9 category scripts/scrub-list.txt gained in
# est-2ek.1.867 — the test must not become its own offender.
_USER = "duckwork"
LANE_PATH = "/home/" + _USER + "/" + ".duckwork/cache/scratch/lane-a"

STALE = {"name": "stale-fbfix-probe", "nodes": [
    {"id": "recon", "type": "agent",
     "goal": f"Fix ledger key fb8b91ad22a9b48b on branch fix/fb8b91-repro in "
             f"{LANE_PATH}; report root cause."},
    {"id": "impl", "type": "agent", "after": ["recon"],
     "goal": f"Implement on fix/fb8b91-repro; write findings to "
             f"{LANE_PATH}/out.md first."}]}

# Same work, bound: every launch-varying value arrives as {run.KEY}.
BOUND = {"name": "bound-fbfix-probe", "nodes": [
    {"id": "recon", "type": "agent",
     "goal": "Fix ledger key {run.key} on branch {run.branch} in {run.lane}; "
             "report root cause."},
    {"id": "impl", "type": "agent", "after": ["recon"],
     "goal": "Implement on {run.branch}; write findings to {run.lane}/out.md first."}]}

# No literals, no bindings — clean graph (a `from` replay is genuinely safe).
CLEAN = {"name": "clean-probe", "nodes": [
    {"id": "a", "type": "agent", "goal": "Read the target and return findings."}]}

LANE_ENV_KEYS = ("WF_RUNS_ROOT", "DUCKWORK_WF_RUN_ID", "DUCKWORK_WF_RUN_DIR")

with tempfile.TemporaryDirectory(prefix="stale245-") as td:
    sandbox = Path(td)
    saved_env = {k: os.environ.get(k) for k in LANE_ENV_KEYS}
    try:
        os.environ["WF_RUNS_ROOT"] = str(sandbox / "runs")
        # A test process is a parent/owner save (est-2ek.1.599): shed any lane
        # identity it inherited so the shelf guard lets the save through.
        os.environ.pop("DUCKWORK_WF_RUN_ID", None)
        os.environ.pop("DUCKWORK_WF_RUN_DIR", None)
        (sandbox / "runs" / "library").mkdir(parents=True)

        # ---- T1: stale graph saves AND warns, naming every literal class ----
        r = json.loads(door.handle({"action": "save", "graph": STALE,
                                    "name": "stale-fbfix-probe"}))
        check("T1a stale graph still saves (warn-only, non-fatal)",
              r.get("saved") == "stale-fbfix-probe", json.dumps(r)[:200])
        w = r.get("save_warnings")
        check("T1b save_warnings present", isinstance(w, list) and len(w) >= 1,
              json.dumps(r)[:300])
        joined = json.dumps(w)
        check("T1c warning names the ledger key", "fb8b91ad22a9b48b" in joined, joined[:300])
        check("T1d warning names the branch literal", "fix/fb8b91-repro" in joined, joined[:300])
        check("T1e warning names the lane path",
              LANE_PATH in joined, joined[:300])
        check("T1f warning points at run_context as the fix",
              "run_context" in joined or "{run." in joined, joined[:300])
        check("T1g the graph landed on the shelf anyway (never blocks)",
              (sandbox / "runs" / "library" / "stale-fbfix-probe.json").exists())

        # ---- T2: bound graph (same content, {run.KEY} everywhere) -> NO warning ----
        r2 = json.loads(door.handle({"action": "save", "graph": BOUND,
                                     "name": "bound-fbfix-probe"}))
        check("T2a bound graph saves", r2.get("saved") == "bound-fbfix-probe",
              json.dumps(r2)[:200])
        check("T2b bound graph earns NO save_warnings key",
              "save_warnings" not in r2, json.dumps(r2)[:300])

        # ---- T3: literal-free graph -> response byte-shape unchanged ----
        r3 = json.loads(door.handle({"action": "save", "graph": CLEAN,
                                     "name": "clean-probe"}))
        check("T3a clean graph saves", r3.get("saved") == "clean-probe", json.dumps(r3)[:200])
        check("T3b clean save response keys unchanged (no save_warnings key)",
              "save_warnings" not in r3, json.dumps(r3)[:300])
        check("T3c clean response is exactly {saved,nodes,hint}",
              set(r3) == {"saved", "nodes", "hint"}, json.dumps(sorted(r3)))

        # ---- T4: provenance/meta cold bytes NEVER fire (attribution dates are cold) ----
        STALE4 = {"name": "stale-prov-probe",
                  "nodes": [{"id": "a", "type": "agent",
                             "goal": "Read the target; findings to your workdir."}],
                  "provenance": {"owner": "seat-agent", "source": "est-2ek.1.245",
                                 "saved_at": "2026-10-05T00:00:00+00:00",
                                 "source_digest": "0123456789abcdef0123456789abcdef"}}
        r4 = json.loads(door.handle({"action": "save", "graph": STALE4,
                                     "name": "stale-prov-probe"}))
        check("T4 cold provenance bytes never warn", "save_warnings" not in r4,
              json.dumps(r4)[:300])
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

print()
print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
