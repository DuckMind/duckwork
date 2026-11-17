#!/usr/bin/env python3
"""PR #237 r3 review (fixes 2 + 3): the lane_recover.py CLI contract.

  * fix 2: PluginResolutionError carries code=2 (module docstring: "2 no
    session / no db") — the __main__ handler must exit 2 with the message on
    stderr, never a traceback + exit 1.
  * fix 3: `--watchdog RUN --home X` must resolve the run (and the plugin
    dir) from X — --home is applied BEFORE the watchdog branch returns.

Both cases drive the real script in a subprocess under an EMPTY DUCKWORK_HOME
(what scripts/suite.py / CI does). The scenes are synthetic crashed-no-exit
runs with NO live plugin, so the production revive refuses before any spawn.

Plain script, no pytest: exits non-zero on any red.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPT = ROOT / "scripts" / "lane_recover.py"
DEAD_PID = 999_998 if sys.maxsize > 2**16 else 32_766

FAILS = []


def check(name, cond, detail=None):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  ::  " + str(detail)[:800]))
    if not cond:
        FAILS.append(name)


def mk_crashed_run(runs, run_id):
    r = runs / run_id
    (r / "nodes").mkdir(parents=True)
    (r / "gates").mkdir()
    (r / "graph.json").write_text(json.dumps(
        {"name": run_id, "nodes": [{"id": "build", "type": "agent", "goal": "ship it"}]}))
    (r / "run.json").write_text(json.dumps({"duckwork_bin": "python3", "concurrency": 1}))
    (r / "nodes" / "build.json").write_text(json.dumps(
        {"status": "running", "pid": DEAD_PID + 1,
         "skey": f"wf:{run_id}:build:deadbeef.000001", "attempt": 1}))
    (r / "wf.pid").write_text(str(DEAD_PID))
    return r


def run(argv, env):
    p = subprocess.run([sys.executable, str(SCRIPT), *argv], capture_output=True,
                       text=True, timeout=60, env=env)
    return p.returncode, p.stdout, p.stderr


def base_env(home):
    env = {k: v for k, v in os.environ.items() if k != "WF_RUNS_ROOT"}
    env["DUCKWORK_HOME"] = str(home)
    return env


def main():
    with tempfile.TemporaryDirectory(prefix="lr237r3-") as td:
        td = Path(td)
        empty_home = td / "empty-home"
        empty_home.mkdir()

        # fix 2: PluginResolutionError -> exit 2, message, no traceback.
        runs = td / "shared-runs"
        r2 = mk_crashed_run(runs, "r237-plugin-absent")
        env = base_env(empty_home)
        env["WF_RUNS_ROOT"] = str(runs)
        rc, out, err = run(["--watchdog", r2.name], env)
        check("fix2: PluginResolutionError exits 2 (documented code), not 1",
              rc == 2, f"rc={rc} stderr={err!r}")
        check("fix2: no traceback on stderr", "Traceback" not in err, err)
        check("fix2: stderr names the refused live plugin dir",
              "live plugin dir duckwork-workflows" in err, err)
        check("fix2: no receipt / guard written on the refused revive",
              not (r2 / "respawn_guard.json").exists(), sorted(p.name for p in r2.iterdir()))

        # fix 3: --watchdog honors --home (env DUCKWORK_HOME points elsewhere).
        flag_home = td / "flag-home"
        r3 = mk_crashed_run(flag_home / "workflows", "r237-home-flag")
        rc, out, err = run(["--watchdog", r3.name, "--home", str(flag_home)],
                           base_env(empty_home))
        check("fix3: --watchdog --home finds the run under <home>/workflows",
              "no run dir" not in err, f"rc={rc} stderr={err!r}")
        check("fix3: plugin dir resolved from --home, not the env home",
              str(flag_home / "plugins" / "duckwork-workflows") in err,
              f"rc={rc} stderr={err!r}")
        check("fix3: refused cleanly (exit 2, no traceback)",
              rc == 2 and "Traceback" not in err, f"rc={rc} stderr={err!r}")

    if FAILS:
        print(f"FAILED: {FAILS}")
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
