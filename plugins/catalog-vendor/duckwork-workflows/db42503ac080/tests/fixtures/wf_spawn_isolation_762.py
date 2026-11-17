"""est-2ek.1.762: the launch-env pin for every test that spawns `wf.py run`.

The runs-root resolver precedence (#42) is

    settings.runs_root  >  WF_RUNS_ROOT env  >  <duckwork_home>/workflows

so DUCKWORK_HOME alone is NOT a sandbox: a child that inherits the invoking
process's WF_RUNS_ROOT writes its run dir wherever the LANE was launched from.
On a production host that lane root IS the estate library — this is exactly how
774 of 1227 unique dirs under the estate production runs root
(~/.duckwork/workflows) ended up as zero-log test fixtures (feedback census spool key 9cfe87a0199e5e1b, est-2ek.1.762).

The law this helper enforces (same shape as merged test_wake_hermetic_env.py
#250 and est-aywd #257): a spawned runner child must carry BOTH
    DUCKWORK_HOME  == the test's scratch home
    WF_RUNS_ROOT == the SAME scratch root the test reads its runs from
so the two resolvers can never disagree and nothing can land outside the test.

Usage:

    sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
    from wf_spawn_isolation_762 import launch_env, pin_env

    env = launch_env(home, runs)                      # scrubbed, both pins
    env = pin_env(dict(os.environ, DUCKWORK_HOME=...), runs)   # explicit env builder

`pin_env` returns the mapping with WF_RUNS_ROOT force-set (a stray inherited
value is REPLACED, never respected — an inherited root is the leak), and strips
API_SERVER_* so a hostile parent can't steer the child's door either.

Stdlib-only. Referenced by the static audit in tests/test_suite_runs_root_762.py.
"""
import os

RUNS_PIN_KEY = "WF_RUNS_ROOT"
# Variables that outrank or bypass DUCKWORK_HOME/WF_RUNS_ROOT for a spawned child.
STRIP_KEYS = ("WF_RUNS_ROOT", "API_SERVER_KEY", "API_SERVER_HOST", "API_SERVER_PORT")


def pin_env(env, runs_root, home=None):
    """Force both pins into an explicit child-env mapping and return it.

    `runs_root` is the ONE root the spawning test reads its runs from; the pin
    is applied by assignment (an inherited WF_RUNS_ROOT from the lane env is
    overwritten — respecting it is the leak this file exists to kill). When
    `home` is given, DUCKWORK_HOME is pinned to it as well so the door and the
    runner resolve the same scratch home.
    """
    env = dict(env)
    for k in STRIP_KEYS:
        env.pop(k, None)
    env[RUNS_PIN_KEY] = str(runs_root)
    if home is not None:
        env["DUCKWORK_HOME"] = str(home)
    return env


def launch_env(home, runs_root, base=None, extra=None):
    """Build a scrubbed launch env with both pins from scratch (POSIX-safe:
    PATH/PYTHONPATH ride over, secrets and lane roots do not)."""
    base = os.environ if base is None else base
    env = {k: v for k, v in base.items()
           if k in ("PATH", "PYTHONPATH", "LANG", "TMPDIR") and v}
    env["DUCKWORK_HOME"] = str(home)
    env[RUNS_PIN_KEY] = str(runs_root)
    env.update(extra or {})
    return env
