#!/usr/bin/env python3
"""_duckwork_bin must never raise under a live door ctx (09-28 launch blocker).

Core's get_config rejects reserved-root keys ('model','plugins','security',
'settings') with ValueError (duckwork_cli/plugins_state.py
_PLUGIN_SETTING_RESERVED_ROOTS). The launcher-only change read
get_config('plugins') unguarded at __init__.py:167, so EVERY workflow launch
died at the door: 'Expected a plugin-relative config key...'. get_config is
already plugin-scoped (it resolves plugins.entries.<id>.settings.<key> with a
legacy 'config' fallback), so the cross-plugin read was both illegal and
redundant. This test mirrors core's rejection rules in the fake ctx.
"""
import importlib.util
import os
import shutil
import sys
from pathlib import Path

BUILD = Path(__file__).parent.parent
HOME = BUILD / "home_duckwork_bin_0928"
shutil.rmtree(HOME, ignore_errors=True)
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ.pop("DUCKWORK_WF_DUCKWORK_BIN", None)

spec = importlib.util.spec_from_file_location("hb_door", str(BUILD / "__init__.py"))
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)

failures = []
def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else " " + str(detail)))
    if not ok:
        failures.append(name)

RESERVED = frozenset({"model", "plugins", "security", "settings"})  # core: plugins_state.py:17

class CoreFaithfulCtx:
    """get_config with core's exact plugin-relative key rules (plugins_state.py)."""
    def __init__(self, settings=None):
        self.settings = settings or {}
    def get_config(self, key, default=None):
        if not isinstance(key, str) or "/" in key or "\\" in key \
                or key.split(".")[0].lower() in RESERVED:
            raise ValueError(
                "Expected a plugin-relative config key such as 'endpoint' or "
                "'retry.policy'; global, cross-plugin, and traversal paths are forbidden")
        cur = self.settings
        for seg in key.split("."):
            if not isinstance(cur, dict) or seg not in cur:
                return default
            cur = cur[seg]
        return cur

# 1. Live ctx, empty settings: must NOT raise (the launch-killing repro).
hw._CTX = CoreFaithfulCtx({})
try:
    got = hw._duckwork_bin()
    check("live-ctx-no-raise", isinstance(got, str) and bool(got), repr(got))
except Exception as e:
    check("live-ctx-no-raise", False, f"raised {type(e).__name__}: {e}")

# 2. Direct plugin setting still wins.
hw._CTX = CoreFaithfulCtx({"duckwork_bin": "/test/bin/duckwork"})
check("direct-setting", hw._duckwork_bin() == "/test/bin/duckwork", hw._duckwork_bin())

# 3. Env fallback under a live ctx (settings empty, env set).
hw._CTX = CoreFaithfulCtx({})
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = "/env/bin/duckwork"
try:
    check("env-fallback-live-ctx", hw._duckwork_bin() == "/env/bin/duckwork", hw._duckwork_bin())
finally:
    os.environ.pop("DUCKWORK_WF_DUCKWORK_BIN", None)

# 4. Env fallback without any ctx (no door loaded).
hw._CTX = None
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = "/noctx/bin/duckwork"
try:
    check("env-fallback-no-ctx", hw._duckwork_bin() == "/noctx/bin/duckwork", hw._duckwork_bin())
finally:
    os.environ.pop("DUCKWORK_WF_DUCKWORK_BIN", None)

# 5. The door must never ASK for a reserved-root key at all: recording ctx proves
#    the illegal read is gone rather than merely caught.
class RecordingCtx(CoreFaithfulCtx):
    def __init__(self):
        super().__init__({})
        self.seen = []
    def get_config(self, key, default=None):
        self.seen.append(key)
        return super().get_config(key, default)

hw._CTX = RecordingCtx()
hw._duckwork_bin()
bad = [k for k in hw._CTX.seen if k.split(".")[0].lower() in RESERVED]
check("no-reserved-root-queries", not bad, f"door asked for {bad} (seen {hw._CTX.seen})")

print("TOTAL 5 FAIL %d" % len(failures))
sys.exit(1 if failures else 0)
