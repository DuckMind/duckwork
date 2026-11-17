#!/usr/bin/env python3
"""#41 / #42 — owner settings `runs_root` + `profile` (tool-bridge first-class).

Subprocess-launched resolver matrix: every case is a FRESH interpreter with its own
environment and its own fake estate, so nothing leaks between cases and the door
module's import-time state is exactly what a real host would see. Cases:

  (a) no settings, no env            -> byte-identical to the pre-fix resolver (main's
                                        wfcommon run in the same env answers the same path)
  (b) settings.runs_root             -> door runs_root(), act_list (handle('list')) and
                                        run_state all resolve the SAME root, via the
                                        plugin ctx (door) AND via the raw config fallback
  (c) settings + WF_RUNS_ROOT        -> settings wins
  (d) relative runs_root             -> fail-closed error on every action, no fallback
  (e) profiles/<other>/workflows     -> refused (own profile home stays legal)
  (f) env profile + settings.profile -> env wins
  (g) no env + settings.profile      -> consent gate accepts a target that lists it
  (h) no env, no setting             -> 'default', byte-identical
  (+) no model-settable launcher arg exists on the tool schema

Stdlib-only, prints PASS/FAIL lines, exit 0 = green.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
failures = []

def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  " + str(detail)[:600]))
    if not ok:
        failures.append(name)

# ---------------------------------------------------------------- harness ----
PROBE = r'''
import importlib.util, json, os, sys
from pathlib import Path
ROOT = Path(sys.argv[1]); MODE = sys.argv[2]; SETTINGS = json.loads(sys.argv[3])
spec = importlib.util.spec_from_file_location("tb_door", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)
common = door._common

RESERVED = {"model", "plugins", "security", "settings"}
class CoreFaithfulCtx:
    """PluginContext.get_config with core's exact plugin-relative key rules."""
    def __init__(self, settings): self.settings = settings
    def get_config(self, key, default=None):
        if not isinstance(key, str) or "/" in key or key.split(".")[0].lower() in RESERVED:
            raise ValueError("Expected a plugin-relative config key")
        cur = self.settings
        for seg in key.split("."):
            if not isinstance(cur, dict) or seg not in cur:
                return default
            cur = cur[seg]
        return cur
if MODE == "ctx":
    door._CTX = CoreFaithfulCtx(SETTINGS)          # the live door: settings via plugin ctx
# MODE == "raw": no ctx; settings (if any) sit in <duckwork_home>/config.yaml on disk

out = {}
def _try(name, fn):
    try:
        v = fn(); out[name] = str(v) if isinstance(v, Path) else v
    except ValueError as e:
        out[name] = {"error": str(e)}
_try("runs_root", door.runs_root)
_try("common_runs_root", common.runs_root)
_try("effective", lambda: common.effective_runs_root({k: v for k, v in os.environ.items()
                                                       if k in ("DUCKWORK_HOME", "WF_RUNS_ROOT")}))
_try("launcher", common.launcher_profile)
_try("duckwork_bin", door._duckwork_bin)
out["list"] = json.loads(door.handle({"action": "list"}))
out["status_missing"] = json.loads(door.handle({"action": "status", "run_id": "nope"}))
if os.environ.get("TB_PROFILE_GATE"):
    # (g): drive profile_errors the way the door does — launcher from launcher_profile(),
    # profiles dir = the fake estate's profiles/ — no graph arg anywhere.
    nodes = [{"id": "n", "type": "agent", "prompt": "x", "after": [], "profile": os.environ["TB_PROFILE_GATE"]}]
    out["gate"] = common.profile_errors(nodes, launcher=common.launcher_profile(),
                                        profiles_dir=common.profiles_root())
out["schema_props"] = sorted(door.WORKFLOW_PARAMS["properties"])
# Only this separate writer leg is pinned; the resolver-precedence probes above
# intentionally use the untouched door and must continue to prove settings > env.
if os.environ.get("TB_PIN_WRITER"):
    iso_spec = importlib.util.spec_from_file_location("wf_test_isolation", ROOT / "tests" / "wf_test_isolation.py")
    iso = importlib.util.module_from_spec(iso_spec); iso_spec.loader.exec_module(iso)
    iso.install(door)
    graph = {"name": "tb-pin", "nodes": [{"id": "n", "type": "agent", "goal": "go"}]}
    out["pinned_save"] = json.loads(door.handle({"action": "save", "name": "tb-pin", "graph": graph}))
print("@@" + json.dumps(out, default=str))
'''

def yaml_settings(settings):
    lines = ["plugins:", "  entries:", "    duckwork-workflows:", "      settings:"]
    for k, v in settings.items():
        lines.append(f"        {k}: {json.dumps(v)}")
    return "\n".join(lines) + "\n"

def probe(home, settings=None, mode="ctx", env=None, root=ROOT):
    """Fresh interpreter. mode 'ctx' -> settings through a core-faithful plugin ctx;
    mode 'raw' -> settings written to <home>/config.yaml, no ctx at all."""
    settings = settings or {}
    home = Path(home)
    if mode == "raw":
        home.mkdir(parents=True, exist_ok=True)
        (home / "config.yaml").write_text(yaml_settings(settings) if settings else "{}\n")
    e = {k: v for k, v in os.environ.items()
         if k not in ("DUCKWORK_HOME", "WF_RUNS_ROOT", "DUCKWORK_WF_DUCKWORK_BIN", "TB_PROFILE_GATE")}
    e["DUCKWORK_HOME"] = str(home)
    e.update(env or {})
    if e.get("DUCKWORK_HOME") is None:
        e.pop("DUCKWORK_HOME", None)
    p = subprocess.run([PY, "-c", PROBE, str(root), mode, json.dumps(settings if mode == "ctx" else {})],
                       capture_output=True, text=True, env=e, timeout=60, cwd=str(home))
    line = [l for l in p.stdout.splitlines() if l.startswith("@@")]
    if p.returncode != 0 or not line:
        raise AssertionError(f"probe died rc={p.returncode}\n{p.stdout[-1500:]}\n{p.stderr[-1500:]}")
    return json.loads(line[0][2:])

def fake_run(root, rid):
    r = Path(root) / rid
    (r / "nodes").mkdir(parents=True, exist_ok=True)
    (r / "graph.json").write_text(json.dumps({"name": "tb", "nodes": [
        {"id": "a", "type": "echo", "output": "ok", "after": []}]}))
    (r / "run.json").write_text(json.dumps({"name": "tb"}))
    return r

TMP = Path(tempfile.mkdtemp(prefix="tb-4142-", dir=str(ROOT / "tests")))
try:
    # ---- (a) no settings, no env: today's bytes ----------------------------
    # Reference = main's UNPATCHED wfcommon resolving in the identical env.
    ref_dir = TMP / "ref"; ref_dir.mkdir()
    base = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD~0:wfcommon.py"],
                          capture_output=True, text=True)
    try:
        # prefer the merge-base main copy when this is a branch; fall back to HEAD
        mb = subprocess.run(["git", "-C", str(ROOT), "merge-base", "HEAD", "origin/main"],
                            capture_output=True, text=True)
        ref = mb.stdout.strip() or "HEAD"
        base = subprocess.run(["git", "-C", str(ROOT), "show", f"{ref}:wfcommon.py"],
                              capture_output=True, text=True)
    except Exception:
        pass
    have_ref = base.returncode == 0 and "def runs_root" in base.stdout
    if have_ref:
        (ref_dir / "wfcommon.py").write_text(base.stdout)
    home_a = TMP / "a-home"; home_a.mkdir()
    fake_home = TMP / "a-HOME"; fake_home.mkdir()
    env_a = {"DUCKWORK_HOME": None, "HOME": str(fake_home)}
    got = probe(home_a, mode="ctx", env=env_a)
    exp_default = str(Path(fake_home) / ".duckwork" / "workflows")
    if have_ref:
        rp = subprocess.run([PY, "-c",
            "import importlib.util,sys;s=importlib.util.spec_from_file_location('c',sys.argv[1]);"
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
            "print(m.runs_root());print(m.launcher_profile())", str(ref_dir / "wfcommon.py")],
            capture_output=True, text=True, timeout=60,
            env={k: v for k, v in os.environ.items() if k not in ("DUCKWORK_HOME", "WF_RUNS_ROOT")} | {"HOME": str(fake_home)})
        ref_root, ref_launch = rp.stdout.strip().splitlines()[-2:]
        check("(a) no settings/no env: runs_root == pre-fix resolver's answer (today's bytes)",
              got["runs_root"] == ref_root == got["common_runs_root"], (got["runs_root"], ref_root))
        check("(a) launcher == pre-fix 'default'", got["launcher"] == ref_launch == "default", (got["launcher"], ref_launch))
    else:
        check("(a) no settings/no env: $HOME/.duckwork/workflows", got["runs_root"] == exp_default, got["runs_root"])
        check("(a) launcher 'default'", got["launcher"] == "default", got["launcher"])
    check("(a) no settings: list is the plain empty answer", got["list"].get("runs") == [], got["list"])

    # ---- (b) settings.runs_root -> door, act_list, run_state agree ---------
    shared = TMP / "shared-runs"
    rid = "20260929-000000-tb"
    fake_run(shared, rid)
    for mode in ("ctx", "raw"):
        home_b = TMP / f"b-home-{mode}"; home_b.mkdir()
        (home_b / "workflows").mkdir()
        fake_run(home_b / "workflows", "20260929-000000-wrongroot")   # must NOT be listed
        got = probe(home_b, {"runs_root": str(shared)}, mode=mode)
        check(f"(b/{mode}) runs_root() == settings.runs_root", got["runs_root"] == str(shared), got["runs_root"])
        check(f"(b/{mode}) wfcommon.runs_root agrees with door.runs_root", got["common_runs_root"] == got["runs_root"])
        check(f"(b/{mode}) effective_runs_root(env) agrees (single root)", got["effective"] == got["runs_root"], got["effective"])
        listed = [r["run_id"] for r in got["list"].get("runs", [])]
        check(f"(b/{mode}) handle('list') lists the run under settings.runs_root (resolver root first)",
              listed and listed[0] == rid, listed)
        check(f"(b/{mode}) legacy launch-root run stays listed (F1 #14 merge law unchanged)",
              "20260929-000000-wrongroot" in listed, listed)
        check(f"(b/{mode}) run_state read the run (status derived, not None)",
              got["list"]["runs"][0].get("status") in ("pending", "interrupted", "done", "running", "held"), got["list"])
    # no restart: same process, setting appears mid-life -> resolver follows at call time
    home_b2 = TMP / "b-home-live"; home_b2.mkdir()
    live = subprocess.run([PY, "-c", r'''
import importlib.util, sys, json
from pathlib import Path
ROOT = Path(sys.argv[1]); shared = sys.argv[2]
spec = importlib.util.spec_from_file_location("tb_live", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)
class Ctx:
    s = {}
    def get_config(self, k, d=None): return self.s.get(k, d)
door._CTX = Ctx()
before = str(door.runs_root())
Ctx.s["runs_root"] = shared
after = str(door.runs_root())
print("@@" + json.dumps({"before": before, "after": after}))
''', str(ROOT), str(shared)], capture_output=True, text=True, timeout=60,
        env={**{k: v for k, v in os.environ.items() if k not in ("WF_RUNS_ROOT",)}, "DUCKWORK_HOME": str(home_b2)})
    lv = json.loads([l for l in live.stdout.splitlines() if l.startswith("@@")][0][2:])
    check("(b) call-time read: setting appearing mid-process flips the resolver without restart",
          lv["before"] == str(home_b2 / "workflows") and lv["after"] == str(shared), lv)

    # ---- (c) settings + WF_RUNS_ROOT -> settings wins -----------------------
    envroot = TMP / "env-runs"; envroot.mkdir()
    for mode in ("ctx", "raw"):
        home_c = TMP / f"c-home-{mode}"; home_c.mkdir()
        got = probe(home_c, {"runs_root": str(shared)}, mode=mode, env={"WF_RUNS_ROOT": str(envroot)})
        check(f"(c/{mode}) settings.runs_root beats WF_RUNS_ROOT", got["runs_root"] == str(shared), got["runs_root"])
        check(f"(c/{mode}) effective_runs_root also prefers settings", got["effective"] == str(shared), got["effective"])
    # and WF_RUNS_ROOT still wins over the home default when no setting (precedence tail intact)
    home_c2 = TMP / "c-home-tail"; home_c2.mkdir()
    got = probe(home_c2, {}, mode="ctx", env={"WF_RUNS_ROOT": str(envroot)})
    check("(c) no setting: WF_RUNS_ROOT > DUCKWORK_HOME/workflows (unchanged)", got["runs_root"] == str(envroot), got["runs_root"])
    # A distinct writer child installs the resolver-level test pin. Unlike the
    # unpinned (c) controls, its save must not touch settings.runs_root.
    writer_home = TMP / "c-home-writer"; writer_home.mkdir()
    writer_scratch = TMP / "c-writer-scratch"; writer_scratch.mkdir()
    got = probe(writer_home, {"runs_root": str(shared)}, mode="raw",
                env={"WF_RUNS_ROOT": str(writer_scratch), "TB_PIN_WRITER": "1"})
    check("(c) pinned writer uses scratch despite owner setting",
          got["pinned_save"].get("saved") == "tb-pin"
          and (writer_scratch / "library" / "tb-pin.json").exists()
          and not (shared / "library" / "tb-pin.json").exists(), got["pinned_save"])

    # ---- (d) relative runs_root -> fail-closed -----------------------------
    for mode in ("ctx", "raw"):
        home_d = TMP / f"d-home-{mode}"; home_d.mkdir()
        got = probe(home_d, {"runs_root": "relative/runs"}, mode=mode)
        check(f"(d/{mode}) resolver raises (no silent fallback)",
              isinstance(got["runs_root"], dict) and "absolute" in got["runs_root"]["error"], got["runs_root"])
        check(f"(d/{mode}) handle('list') is an error naming the setting",
              "error" in got["list"] and "runs_root" in got["list"]["error"] and "absolute" in got["list"]["error"], got["list"])
        check(f"(d/{mode}) every action fails closed (status too)",
              "error" in got["status_missing"] and "runs_root" in got["status_missing"]["error"], got["status_missing"])
    # expanduser: '~/x' is accepted as absolute after expansion
    home_d2 = TMP / "d-home-tilde"; home_d2.mkdir()
    fake_home2 = TMP / "d-HOME"; fake_home2.mkdir()
    got = probe(home_d2, {"runs_root": "~/wf-runs"}, mode="ctx", env={"HOME": str(fake_home2)})
    check("(d) '~/x' expands to an absolute root", got["runs_root"] == str(fake_home2 / "wf-runs"), got["runs_root"])

    # ---- (e) profiles/<other>/workflows -> refused --------------------------
    estate = TMP / "estate"
    for n in ("p1", "other"):
        (estate / "profiles" / n).mkdir(parents=True)
        (estate / "profiles" / n / "config.yaml").write_text("{}\n")
    for mode in ("ctx", "raw"):
        got = probe(estate / "profiles" / "p1", {"runs_root": str(estate / "profiles" / "other" / "workflows")}, mode=mode)
        check(f"(e/{mode}) another profile's home is refused",
              isinstance(got["runs_root"], dict) and "other" in got["runs_root"]["error"], got["runs_root"])
        check(f"(e/{mode}) door action errors, never falls back", "error" in got["list"] and "profile" in got["list"]["error"], got["list"])
    got = probe(estate, {"runs_root": str(estate / "profiles" / "other" / "workflows")}, mode="ctx")
    check("(e) base home: any profiles/<name>/ subtree refused", isinstance(got["runs_root"], dict), got["runs_root"])
    got = probe(estate / "profiles" / "p1", {"runs_root": str(estate / "profiles" / "p1" / "workflows")}, mode="ctx")
    check("(e) own profile home stays legal", got["runs_root"] == str(estate / "profiles" / "p1" / "workflows"), got["runs_root"])
    got = probe(estate / "profiles" / "p1", {"runs_root": str(estate / "shared")}, mode="ctx")
    check("(e) estate-level shared dir legal from a profile", got["runs_root"] == str(estate / "shared"), got["runs_root"])

    # ---- (f) env profile + settings.profile -> env wins ----------------------
    for mode in ("ctx", "raw"):
        got = probe(estate / "profiles" / "p1", {"profile": "other"}, mode=mode)
        check(f"(f/{mode}) env-derived identity wins over settings.profile", got["launcher"] == "p1", got["launcher"])

    # ---- (g) no env + settings.profile -> consent gate sees the real launcher --
    # R1 (#46): settings.profile must name an EXISTING profile home -> bridge-seat is
    # a real seat here, the env-blind-bridge shape the owner actually runs.
    bridge = estate / "profiles" / "bridge-seat"
    bridge.mkdir()
    (bridge / "config.yaml").write_text("{}\n")
    tgt = estate / "profiles" / "target"
    tgt.mkdir()
    (tgt / "config.yaml").write_text("{}\n")
    (tgt / "workflow_team.json").write_text(json.dumps({"accept_from": ["bridge-seat"]}))
    for mode in ("ctx", "raw"):
        got = probe(estate, {"profile": "bridge-seat"}, mode=mode, env={"TB_PROFILE_GATE": "target"})
        check(f"(g/{mode}) env-blind launch: launcher_profile() == settings.profile", got["launcher"] == "bridge-seat", got["launcher"])
        check(f"(g/{mode}) consent gate accepts (target lists bridge-seat, not default)", got["gate"] == [], got["gate"])
    got = probe(estate, {}, mode="ctx", env={"TB_PROFILE_GATE": "target"})
    check("(g) same gate WITHOUT the setting rejects 'default' (the #41 repro)",
          len(got["gate"]) == 1 and "default" in got["gate"][0]["msg"], got["gate"])
    for bad in ("../evil", "a/b", ".hidden", "x\x01y"):
        got = probe(estate, {"profile": bad}, mode="ctx")
        check(f"(g) unsafe settings.profile {bad!r} fails closed",
              isinstance(got["launcher"], dict) and "error" in got["list"], (got["launcher"], got["list"]))

    # ---- (h) no env, no setting -> 'default' byte-identical -----------------
    for mode in ("ctx", "raw"):
        home_h = TMP / f"h-home-{mode}"; home_h.mkdir()
        got = probe(home_h, {}, mode=mode)
        check(f"(h/{mode}) launcher 'default'", got["launcher"] == "default", got["launcher"])
        check(f"(h/{mode}) runs_root = DUCKWORK_HOME/workflows", got["runs_root"] == str(home_h / "workflows"), got["runs_root"])

    # ---- (+) no model-settable launcher/root arg ----------------------------
    check("(+) tool schema exposes no launcher/profile/runs_root argument",
          not ({"launcher", "profile", "runs_root", "dispatched_by", "duckwork_home"} & set(got["schema_props"])),
          got["schema_props"])
    # duckwork_bin still reads through the same helper (ctx path)
    home_i = TMP / "i-home"; home_i.mkdir()
    got = probe(home_i, {"duckwork_bin": "/cfg/duckwork"}, mode="ctx")
    check("(+) duckwork_bin reads through the same owner-settings helper", got["duckwork_bin"] == "/cfg/duckwork", got["duckwork_bin"])
finally:
    shutil.rmtree(TMP, ignore_errors=True)

# ================= round 2: READER-PARITY matrix (F2f / F2h / R1 / R2) =====
# The door reads owner settings through core's loader (env-expanded, PER-KEY legacy
# `config` fallback — duckwork_cli/plugins.py get_config); the runner (wf.py) and the
# dashboard (plugin_api._root) have no plugin ctx and read config.yaml raw. Any value
# core transforms — `${VAR}` / `${env:VAR}`, a key living under legacy `config` next
# to a `settings` mapping — made the door write runs the runner could not find
# (adversary hunts 2f/2h). The raw reader must now mirror core's semantics so ALL
# THREE readers answer the identical value (or the identical error) for every shape,
# with core importable AND without.
PARITY_PROBE = r'''
import importlib.util, json, os, sys, types
from pathlib import Path
ROOT = Path(sys.argv[1]); MODE = sys.argv[2]   # 'core-ctx' | 'core-raw' | 'nocore'
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
core_importable = False
try:
    import duckwork_cli.config  # noqa: F401
    core_importable = True
except Exception:
    pass
out = {"core_importable": core_importable}
def snap(fn):
    try:
        return {"value": str(fn())}
    except ValueError as e:
        return {"error": str(e)}
spec = importlib.util.spec_from_file_location("tb_parity_door", ROOT / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)
import wf                                                  # the runner's reader
spec2 = importlib.util.spec_from_file_location("tb_parity_api", ROOT / "dashboard" / "plugin_api.py")
api = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(api)   # the dashboard's
if MODE == "core-ctx":
    from duckwork_cli.plugins import PluginContext           # THE real core reader
    ctx = PluginContext.__new__(PluginContext)
    ctx.manifest = types.SimpleNamespace(name="duckwork-workflows", plugin_id="duckwork-workflows",
                                         key="duckwork-workflows")
    door._CTX = ctx
else:
    door._CTX = None
out["door"] = snap(door.runs_root)
out["runner"] = snap(wf.runs_root)            # same function find_run() resolves with
out["dashboard"] = snap(api._root)
out["door_launcher"] = snap(door._common.launcher_profile)
out["runner_launcher"] = snap(lambda: wf.wfcommon.launcher_profile())  # the runner's PRIVATE binding (import hygiene #133387: no bare 'wfcommon' in sys.modules)
out["dash_launcher"] = snap(lambda: api._workflow_common().launcher_profile())
print("@@" + json.dumps(out))
'''

PY_CORE = "/opt/duckwork/.venv/bin/python"
if not Path(PY_CORE).exists():
    PY_CORE = PY

# The venv python imports core via its .pth no matter what, so the NO-CORE leg runs
# the same interpreter with a sitecustomize that hard-blocks the core namespaces
# (duckwork_cli / duckwork_constants / agent / duckwork_yaml): the probe then exercises the
# raw reader exactly as a host without core would, with ruamel still available.
BLOCK_HOME = None
def _blocker_home():
    global BLOCK_HOME
    if BLOCK_HOME is None:
        BLOCK_HOME = Path(tempfile.mkdtemp(prefix="tb-nocore-", dir=str(ROOT / "tests")))
        (BLOCK_HOME / "sitecustomize.py").write_text(
            "import sys\n"
            "_BLOCKED = {'duckwork_cli', 'duckwork_constants', 'agent', 'duckwork_yaml', "
            "'duckwork_platform', 'duckwork_bootstrap'}\n"
            "class _Blocker:\n"
            "    def find_spec(self, fullname, path=None, target=None):\n"
            "        if fullname.split('.')[0] in _BLOCKED:\n"
            "            raise ImportError('%s blocked (nocore test mode)' % fullname)\n"
            "        return None\n"
            "sys.meta_path.insert(0, _Blocker())\n")
    return BLOCK_HOME

def parity_probe(home, cfg_text, mode, env=None):
    """Fresh interpreter; cfg_text is the RAW config.yaml (settings + legacy config)."""
    home = Path(home); home.mkdir(parents=True, exist_ok=True)
    (home / "config.yaml").write_text(cfg_text)
    base = {k: v for k, v in os.environ.items()
            if k not in ("DUCKWORK_HOME", "WF_RUNS_ROOT", "DUCKWORK_WF_DUCKWORK_BIN",
                         "TB_PROFILE_GATE", "PYTHONPATH")}
    base["DUCKWORK_HOME"] = str(home)
    py = PY_CORE
    if mode == "nocore":
        base["PYTHONPATH"] = str(_blocker_home())   # sitecustomize blocks core imports
    else:
        base["PYTHONPATH"] = "/opt/duckwork"
    base.update(env or {})
    p = subprocess.run([py, "-c", PARITY_PROBE, str(ROOT), mode],
                       capture_output=True, text=True, env=base, timeout=90, cwd=str(home))
    line = [l for l in p.stdout.splitlines() if l.startswith("@@")]
    if p.returncode != 0 or not line:
        raise AssertionError(f"parity probe died ({mode}) rc={p.returncode}\n{p.stdout[-1200:]}\n{p.stderr[-1200:]}")
    return json.loads(line[0][2:])

def yaml_block(key, mapping, indent):
    lines = [" " * indent + key + ":"]
    for k, v in mapping.items():
        lines.append(" " * (indent + 2) + f"{k}: {json.dumps(v)}")
    return lines

def parity_cfg(settings=None, legacy=None):
    lines = ["plugins:", "  entries:", "    duckwork-workflows:"]
    if settings is not None:
        lines += yaml_block("settings", settings, 6)
    if legacy is not None:
        lines += yaml_block("config", legacy, 6)
    return "\n".join(lines) + "\n"

def parity_case(name, home, cfg_text, env, expect):
    """All three readers × {core-ctx, core-raw, nocore} answer `expect` (a
    {key: {"value"|"error": ...}} dict). Values compare EXACTLY; an expected "error"
    is a substring the real message must contain (the refuse wording carries paths —
    only its reason is stable across readers). Cross-reader AND cross-interpreter."""
    def match(got_v, want):
        if "value" in want:
            return got_v == want
        return (isinstance(got_v, dict) and "error" in got_v
                and want["error"] in got_v["error"])
    seen = {}
    for mode in ("core-ctx", "core-raw", "nocore"):
        got = parity_probe(home, cfg_text, mode, env=env)
        if mode == "nocore" and got.get("core_importable"):
            print(f"SKIP {name} [nocore] — core importable without PYTHONPATH on this host")
            continue
        for k, v in expect.items():
            ok = match(got.get(k), v)
            check(f"{name} [{mode}] {k}", ok, (got.get(k), v))
        seen[mode] = got
    # cross-interpreter agreement on the compared keys (door/runner/dashboard triples)
    modes = [m for m in seen if m != "nocore" or not seen["nocore"].get("core_importable")]
    for a in range(len(modes)):
        for b in range(a + 1, len(modes)):
            ga, gb = seen[modes[a]], seen[modes[b]]
            def norm(g):   # errors collapse to their expected reason for agreement
                out = {}
                for k in expect:
                    v = g.get(k) or {}
                    out[k] = {"error": expect[k]["error"]} if "error" in expect[k] and "error" in v \
                        else v
                return out
            check(f"{name} readers agree across interpreters ({modes[a]} vs {modes[b]})",
                  all(ga[k] == gb[k] for k in expect) or
                  all(norm(ga)[k] == norm(gb)[k] for k in expect),
                  [(modes[a], {k: ga[k] for k in expect}), (modes[b], {k: gb[k] for k in expect})])

TMP2 = Path(tempfile.mkdtemp(prefix="tb-parity-", dir=str(ROOT / "tests")))
try:
    # ---- F2f: ${VAR} / ${env:VAR} expansion — door/runner/dashboard identical ----
    fake_home = TMP2 / "HOME"; fake_home.mkdir()
    home_f = TMP2 / "f-home"; (home_f / "workflows").mkdir(parents=True)
    advx = TMP2 / "advx"; advx.mkdir()
    parity_case("F2f ${VAR}", home_f,
                parity_cfg({"runs_root": "${HOME}/wf-runs"}),
                {"HOME": str(fake_home)},
                {"door": {"value": str(fake_home / "wf-runs")},
                 "runner": {"value": str(fake_home / "wf-runs")},
                 "dashboard": {"value": str(fake_home / "wf-runs")}})
    parity_case("F2f ${env:VAR}", home_f,
                parity_cfg({"runs_root": "${env:ADV_X}"}),
                {"HOME": str(fake_home), "ADV_X": str(advx)},
                {"door": {"value": str(advx)},
                 "runner": {"value": str(advx)},
                 "dashboard": {"value": str(advx)}})
    # UNRESOLVED ref: every reader refuses with the SAME error (never a door-only view)
    unresolved_err = {"error": "unresolved"}
    parity_case("F2f unresolved ${VAR} refuses on ALL readers", home_f,
                parity_cfg({"runs_root": "${TB_NO_SUCH_VAR_9C41}/x"}),
                {"HOME": str(fake_home)},
                {"door": unresolved_err, "runner": unresolved_err, "dashboard": unresolved_err})
    # profile shape too — the seat lives under the probe's OWN DUCKWORK_HOME root
    # (R1 #46: settings.profile must name an existing profile home)
    prof = TMP2 / "f-home-prof" / "profiles" / "stamped"
    prof.mkdir(parents=True)
    (prof / "config.yaml").write_text("{}\n")
    parity_case("F2f ${VAR} settings.profile", TMP2 / "f-home-prof",
                parity_cfg({"profile": "${env:ADV_PROF}"}),
                {"HOME": str(fake_home), "DUCKWORK_HOME": str(TMP2 / "f-home-prof"),
                 "ADV_PROF": "stamped"},
                {"door_launcher": {"value": "stamped"},
                 "runner_launcher": {"value": "stamped"},
                 "dash_launcher": {"value": "stamped"}})

    # ---- F2h: per-key legacy `config` fallback — settings key wins, else config ----
    legacy_root = TMP2 / "legacy-root"; legacy_root.mkdir()
    # R1 (#46) applies to the legacy subtree too: legacyprof must be a real seat
    (TMP2 / "h-home" / "profiles" / "legacyprof").mkdir(parents=True)
    (TMP2 / "h-home" / "profiles" / "legacyprof" / "config.yaml").write_text("{}\n")
    # env-blind launcher (DUCKWORK_HOME is NOT <root>/profiles/<name>)
    parity_case("F2h mixed settings+config (hunt5h shape)", TMP2 / "h-home",
                parity_cfg({"duckwork_bin": "/bin/true"},
                           {"runs_root": str(legacy_root), "profile": "legacyprof"}),
                {"HOME": str(fake_home), "DUCKWORK_HOME": str(TMP2 / "h-home")},
                {"door": {"value": str(legacy_root)},
                 "runner": {"value": str(legacy_root)},
                 "dashboard": {"value": str(legacy_root)},
                 "door_launcher": {"value": "legacyprof"},
                 "runner_launcher": {"value": "legacyprof"},
                 "dash_launcher": {"value": "legacyprof"}})
    # settings key PRESENT wins over legacy config for THAT key; missing key falls back
    est = TMP2 / "estate2"
    # env-blind seat home (DUCKWORK_HOME=estate2/seat, NOT under profiles/) -> estate root
    # = the seat home itself, so the R1-checked seat lives at estate2/seat/profiles/realprof
    (est / "seat" / "profiles" / "realprof").mkdir(parents=True)
    (est / "seat" / "profiles" / "realprof" / "config.yaml").write_text("{}\n")
    parity_case("F2h per-key: settings.profile wins, config.runs_root fills", est / "seat",
                parity_cfg({"profile": "realprof"},
                           {"profile": "ghostlegacy", "runs_root": str(legacy_root)}),
                {"HOME": str(fake_home)},
                {"door": {"value": str(legacy_root)},
                 "runner": {"value": str(legacy_root)},
                 "dashboard": {"value": str(legacy_root)},
                 "door_launcher": {"value": "realprof"},
                 "runner_launcher": {"value": "realprof"},
                 "dash_launcher": {"value": "realprof"}})
    parity_case("F2h settings.runs_root wins over config.runs_root", est / "seat2",
                parity_cfg({"runs_root": str(advx)},
                           {"runs_root": str(legacy_root)}),
                {"HOME": str(fake_home)},
                {"door": {"value": str(advx)},
                 "runner": {"value": str(advx)},
                 "dashboard": {"value": str(advx)}})

    # ---- R1: ghost settings.profile fails closed on every reader ----
    parity_case("R1 ghost settings.profile refuses on ALL readers", TMP2 / "g-home",
                parity_cfg({"profile": "ghost"}),
                {"HOME": str(fake_home), "DUCKWORK_HOME": str(TMP2 / "g-home")},
                {"door_launcher": {"error": "does not exist"},
                 "runner_launcher": {"error": "does not exist"},
                 "dash_launcher": {"error": "does not exist"}})
    # an EXISTING profile passes (control) — under this probe's DUCKWORK_HOME
    gok = TMP2 / "g-home-ok"
    (gok / "profiles" / "stamped").mkdir(parents=True)
    (gok / "profiles" / "stamped" / "config.yaml").write_text("{}\n")
    parity_case("R1 existing settings.profile accepted", gok,
                parity_cfg({"profile": "stamped"}),
                {"HOME": str(fake_home), "DUCKWORK_HOME": str(TMP2 / "g-home-ok")},
                {"door_launcher": {"value": "stamped"},
                 "runner_launcher": {"value": "stamped"},
                 "dash_launcher": {"value": "stamped"}})

    # ---- R2: runs_root == <estate>/profiles exactly refuses ----
    est3 = TMP2 / "estate3"
    (est3 / "profiles" / "A").mkdir(parents=True)
    (est3 / "profiles" / "A" / "config.yaml").write_text("{}\n")
    parity_case("R2 runs_root == <estate>/profiles refuses on ALL readers",
                est3 / "profiles" / "A",
                parity_cfg({"runs_root": str(est3 / "profiles")}),
                {"HOME": str(fake_home)},
                {"door": {"error": "profiles"},
                 "runner": {"error": "profiles"},
                 "dashboard": {"error": "profiles"}})
    # control: a dir UNDER the shared root that is not a profile home stays legal
    parity_case("R2 estate-level shared dir still legal (control)", est3 / "profiles" / "A",
                parity_cfg({"runs_root": str(est3 / "shared")}),
                {"HOME": str(fake_home)},
                {"door": {"value": str(est3 / "shared")},
                 "runner": {"value": str(est3 / "shared")},
                 "dashboard": {"value": str(est3 / "shared")}})
finally:
    shutil.rmtree(TMP2, ignore_errors=True)
    if BLOCK_HOME is not None:      # the blocker dir is per-run, never left behind
        shutil.rmtree(BLOCK_HOME, ignore_errors=True)


print(("ALL PASS" if not failures else f"FAILED {len(failures)}: {failures}") + " test_tool_bridge_settings_9c41e2b7")
sys.exit(1 if failures else 0)
