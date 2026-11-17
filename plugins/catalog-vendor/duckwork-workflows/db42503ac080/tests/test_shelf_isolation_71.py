#!/usr/bin/env python3
"""#71 regression pin: the shelf is a live production surface — no test may write
it, and nothing may rely on DUCKWORK_HOME alone to sandbox door saves/runs.

Three parts, standalone (no pytest):
  S1 tripwire — snapshot the door's RESOLVED shelf + runs root, perform in-process
     door writes (save, run) under a pinned WF_RUNS_ROOT, assert the resolved
     production paths gained nothing and the writes landed in the sandbox.
  S2 leak-proof — simulate the accident that caused the 09-30 pollution: drop the
     WF_RUNS_ROOT pin and set the context-local home override (what a lane process
     carries). A save must then land under the OVERRIDE root, not where DUCKWORK_HOME
     points — the proof that DUCKWORK_HOME alone is not a sandbox and the pin is the
     only defense. The canary is cleaned up with the temp home.
  S3 static audit — every test file that calls door write verbs in-process must
     pin WF_RUNS_ROOT; a file reintroducing the leak pattern fails here RED.
"""
import importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
ok = True


def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)


sys.path.insert(0, "/opt/duckwork")
import duckwork_constants as hc  # noqa: E402

spec = importlib.util.spec_from_file_location("hw71", str(BUILD / "__init__.py"))
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)
import wf_test_isolation as _iso71
_iso71.install(door)

G = {"name": "shelf-pollution-probe", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]}

# Snapshot what the door resolves RIGHT NOW — in a lane/suite process this is the
# shared estate shelf; that is the surface nothing may gain entries on.
PROD_LIB = door.library_root()
PROD_RUNS = door.runs_root()
PROD_LIB_SNAP = {p.name: p.read_bytes() for p in PROD_LIB.glob("*.json")} if PROD_LIB.exists() else {}
PROD_RUNS_SNAP = {p.name for p in PROD_RUNS.iterdir()} if PROD_RUNS.exists() else set()

with tempfile.TemporaryDirectory(prefix="shelf71-") as td:
    sandbox = Path(td)
    saved_env = {k: os.environ.get(k) for k in ("WF_RUNS_ROOT", "DUCKWORK_HOME")}
    try:
        # ---- S1: pinned sandbox keeps the production shelf untouched ----
        os.environ["WF_RUNS_ROOT"] = str(sandbox / "runs")
        os.environ["DUCKWORK_HOME"] = str(sandbox / "home")

        r = json.loads(door.handle({"action": "save", "graph": G, "name": "shelf71-entry"}))
        check("S1a save succeeds under pin", r.get("saved") == "shelf71-entry", json.dumps(r))
        check("S1b save landed in sandbox", (sandbox / "runs" / "library" / "shelf71-entry.json").exists())
        lib_after = {p.name: p.read_bytes() for p in PROD_LIB.glob("*.json")} if PROD_LIB.exists() else {}
        runs_after = {p.name for p in PROD_RUNS.iterdir()} if PROD_RUNS.exists() else set()
        check("S1c production shelf gained NOTHING", lib_after == PROD_LIB_SNAP,
              f"new: {sorted(set(lib_after) - set(PROD_LIB_SNAP))}")
        stray_runs = {n for n in runs_after - PROD_RUNS_SNAP if "shelf71" in n or "pollution" in n}
        check("S1d no probe run dirs in the production runs root", not stray_runs, f"stray: {sorted(stray_runs)}")

        # ---- S2: without the pin, the context-local override outranks DUCKWORK_HOME ----
        override_home = sandbox / "override-home"
        override_home.mkdir()
        token = hc.set_duckwork_home_override(override_home)
        try:
            del os.environ["WF_RUNS_ROOT"]
            os.environ["DUCKWORK_HOME"] = str(sandbox / "decoy-home")  # the test's naive claim
            r = json.loads(door.handle({"action": "save", "graph": G, "name": "shelf71-canary"}))
            canary_override = override_home / "workflows" / "library" / "shelf71-canary.json"
            canary_decoy = sandbox / "decoy-home" / "workflows" / "library" / "shelf71-canary.json"
            check("S2a save resolves via the OVERRIDE, not DUCKWORK_HOME",
                  canary_override.exists() and not canary_decoy.exists(),
                  f"override={canary_override.exists()} decoy={canary_decoy.exists()} — "
                  "this is exactly how the 09-30 estate pollution happened")
        finally:
            hc.reset_duckwork_home_override(token)
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

# ---- S4 (r5): the owner-root escape is machine law. With the estate config
# carrying plugins.entries.duckwork-workflows.settings.runs_root (which the resolver
# checks BEFORE WF_RUNS_ROOT — owner design, unchanged), a door that pins only the
# env var writes straight into the owner's canary while exiting 0. A properly
# pinned door (wf_test_isolation.install → settings.runs_root resolves to the SAME
# scratch root, context-locally) must leave the canary byte-for-byte EMPTY.
with tempfile.TemporaryDirectory(prefix="shelf71b-") as td2:
    sb = Path(td2)
    canary = sb / "canary"                      # what the owner configured
    scratch = sb / "scratch"                    # what the test pins
    canary.mkdir(); scratch.mkdir()
    estate = sb / "estate"; prof = estate / "profiles" / "s4"
    prof.mkdir(parents=True)
    (estate / "config.yaml").write_text("")     # estate-home markers
    (estate / ".env").write_text("")
    (prof / "config.yaml").write_text(
        "plugins:\n  entries:\n   duckwork-workflows:\n    settings:\n"
        f"     runs_root: \"{canary}\"\n")

    def fresh_door(tag):
        s = importlib.util.spec_from_file_location(f"hw71_{tag}", str(BUILD / "__init__.py"))
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
        return m

    saved_env = {k: os.environ.get(k) for k in ("WF_RUNS_ROOT", "DUCKWORK_HOME")}
    token = hc.set_duckwork_home_override(prof)   # what a lane process carries
    try:
        os.environ["WF_RUNS_ROOT"] = str(scratch)
        os.environ["DUCKWORK_HOME"] = str(sb / "home")
        # (a) positive control: the unpinned door IS escaped — env pin loses to the
        # owner setting (r5 counter-probe baked in as a tripwire; if this ever
        # FAILS, the resolver precedence changed and this whole section must be
        # re-derived, not quietly deleted).
        d_un = fresh_door("unpinned")
        r = json.loads(d_un.handle({"action": "save", "graph": G, "name": "s4-leak"}))
        check("S4a control: unpinned door leaks into the settings canary",
              (canary / "library" / "s4-leak.json").exists()
              and not (scratch / "library" / "s4-leak.json").exists(),
              json.dumps(r))
        # (b) machine law: the pinned door — ZERO files in the owner canary.
        d_pin = fresh_door("pinned")
        import wf_test_isolation as _iso71
        _iso71.install(d_pin)
        r = json.loads(d_pin.handle({"action": "save", "graph": G, "name": "s4-pinned"}))
        check("S4b pinned save lands in the scratch root",
              r.get("saved") == "s4-pinned"
              and (scratch / "library" / "s4-pinned.json").exists(), json.dumps(r))
        leaked = sorted(p.relative_to(canary).as_posix() for p in canary.rglob("*") if p.is_file())
        check("S4c owner canary STAYS EMPTY under the pinned mechanism",
              leaked == ["library/s4-leak.json"], f"canary: {leaked}")
        # (c) the pinned door's own resolution proves the pin, not just the files
        check("S4d resolved runs_root == env pin despite settings.runs_root",
              str(d_pin.runs_root()) == str(scratch.resolve())
              or str(d_pin.runs_root()) == str(scratch), str(d_pin.runs_root()))
    finally:
        hc.reset_duckwork_home_override(token)
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

# ---- S5: execute the golden fixture's REAL save, not a token-presence audit. ----
# Its patch.dict(clear=True) must not lift the env pin at the actual save;
# otherwise the inherited core-home override's owner setting wins. Stop only
# AFTER the save so the regression is quick and never launches a runner.
with tempfile.TemporaryDirectory(prefix="shelf71-golden-") as td3:
    sb = Path(td3)
    canary = sb / "owner-canary"
    canary.mkdir()
    sentinel = canary / "sentinel.txt"
    sentinel.write_bytes(b"owner canary: unchanged\n")
    estate = sb / "estate"
    profile = estate / "profiles" / "golden"
    profile.mkdir(parents=True)
    (estate / "config.yaml").write_text("")
    (estate / ".env").write_text("")
    (profile / "config.yaml").write_text(
        "plugins:\n  entries:\n   duckwork-workflows:\n    settings:\n"
        f'     runs_root: "{canary}"\n')
    baseline = {p.relative_to(canary).as_posix(): p.read_bytes()
                for p in canary.rglob("*") if p.is_file()}
    golden_spec = importlib.util.spec_from_file_location("shelf71_golden", HERE / "11-golden-solo.py")
    golden = importlib.util.module_from_spec(golden_spec)
    golden_spec.loader.exec_module(golden)
    golden.SCENARIOS = {"legacy-ra-sample": golden.SCENARIOS["legacy-ra-sample"]}

    class SavedGolden(Exception):
        pass

    observed = {}
    def after_golden_save(scratch_runs):
        observed["scratch_save"] = (scratch_runs / "library" / "ra-review-golden.json").exists()
        observed["canary_files"] = {p.relative_to(canary).as_posix(): p.read_bytes()
                                    for p in canary.rglob("*") if p.is_file()}
        raise SavedGolden

    saved_env = {k: os.environ.get(k) for k in ("WF_RUNS_ROOT", "DUCKWORK_HOME")}
    token = hc.set_duckwork_home_override(profile)
    try:
        os.environ["WF_RUNS_ROOT"] = str(sb / "harness-pin")
        os.environ["DUCKWORK_HOME"] = str(sb / "decoy-home")
        try:
            golden.capture(BUILD, after_save=after_golden_save)
        except SavedGolden:
            pass
        check("S5a actual golden save callback ran", bool(observed))
        check("S5b golden save landed in its scratch runs root", observed.get("scratch_save"),
              str(observed))
        check("S5c owner canary gained no files and sentinel survived",
              observed.get("canary_files") == baseline,
              f"added: {sorted(set(observed.get('canary_files', {})) - set(baseline))}")
    finally:
        hc.reset_duckwork_home_override(token)
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

# ---- S3: static audit — in-process door writers must pin BOTH doors ----
# WF_RUNS_ROOT alone is not a sandbox: the plugin's settings.runs_root (raw-read
# from the estate profile's config.yaml when the door carries no ctx) outranks it
# — so every writer must also neutralize/pin the settings path via
# wf_test_isolation.install beside the env pin.
import re
pattern = re.compile(r"\b(\w+)\.(handle|act_save|act_run|act_delete|act_amend)\(")
leakers = []
for p in sorted(HERE.glob("*.py")):
    if p.name == Path(__file__).name or p.name == "fake_duckwork.py":
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    if pattern.search(t) and ("WF_RUNS_ROOT" not in t or "wf_test_isolation" not in t):
        leakers.append(p.name)
check("S3 every in-process door writer pins WF_RUNS_ROOT + settings.runs_root", not leakers, f"leakers: {leakers}")

print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
