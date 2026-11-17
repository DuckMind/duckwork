"""fb b3c98b2a0518a8f0: the submit door validates routes and survives absent core.
Stdlib-only targeted regression; PASS/FAIL lines and nonzero exit on failure.
"""
import atexit
from contextlib import contextmanager
import importlib
import os
from pathlib import Path
import sys
import tempfile
import types

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
home = tempfile.TemporaryDirectory(prefix=".tmp-route-efforts-", dir=HERE / "tests")
atexit.register(home.cleanup)
os.environ["DUCKWORK_HOME"] = home.name
import wfcommon

door = importlib.import_module("__init__")

class Ctx:
    def get_config(self, key, default=None):
        return {} if key == "models" else default

door._CTX = Ctx()
door._seat_model_cfg = lambda: {"default": "seat-default", "aliases": {}}

fails = 0
def check(label, condition, detail=""):
    global fails
    print(("PASS " if condition else "FAIL ") + label + (" -- " + str(detail) if not condition else ""))
    fails += not condition

LADDER = ("none", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
COMPAT = LADDER[:-1]
CODEX = ("none", "low", "medium", "high", "xhigh")

@contextmanager
def core(module):
    """Isolate both parent package and child module, including poisoned imports."""
    missing = object()
    old = {k: sys.modules.get(k, missing) for k in ("agent", "agent.reasoning_effort")}
    try:
        if old["agent"] is missing or old["agent"] is None:
            parent = types.ModuleType("agent")
            parent.__path__ = []
            sys.modules["agent"] = parent
        sys.modules["agent.reasoning_effort"] = module
        yield
    finally:
        for key, prior in old.items():
            if prior is missing:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = prior

def fake(route=False, raises=False):
    mod = types.ModuleType("agent.reasoning_effort")
    mod.EFFORT_LADDER = LADDER
    mod.codex_supported_efforts = lambda model: CODEX
    if route:
        def supported(provider, model):
            if raises:
                raise RuntimeError("route API unavailable")
            return CODEX if provider == "openai-codex" else COMPAT
        mod.route_supported_efforts = supported
    return mod

def submit(provider, model, reasoning):
    node = {"id": "a", "type": "agent", "goal": "x", "provider": provider,
            "model": model, "reasoning": reasoning}
    return door._resolve_models([node])[0]

def rejected(error, level, supported, nearest):
    return (error is not None and repr(level) in error and
            "supported: " + repr(list(supported)) in error and
            "nearest supported level: " + repr(nearest) in error)

# (a), (b): full core, fake first; then the actual installed core if capable.
with core(fake(route=True)):
    err = submit("anthropic", "claude-opus-5-5", "ultra")
    check("a: anthropic ultra rejected by route with supported list", rejected(err, "ultra", COMPAT, "max"), err)
    err = submit("openai-codex", "gpt-5.3-codex", "minimal")
    check("b: codex minimal rejected with supported list", rejected(err, "minimal", CODEX, "low"), err)
try:
    from agent.reasoning_effort import route_supported_efforts
except Exception:
    print("SKIP real core a/b: route_supported_efforts unavailable")
else:
    err = submit("anthropic", "claude-opus-5-5", "ultra")
    check("a: real core anthropic ultra rejected", rejected(err, "ultra", COMPAT, "max"), err)
    err = submit("openai-codex", "gpt-5.3-codex", "minimal")
    check("b: real core codex minimal rejected", rejected(err, "minimal", CODEX, "low"), err)

# (c): missing module must never throw at the door; fallback is the global set.
with core(None):
    for level in ("high", "minimal"):
        try:
            err = submit("openai-codex", "gpt-5.3-codex", level)
            efforts = door._route_efforts("openai-codex", "gpt-5.3-codex")
        except Exception as exc:
            check("c: coreless codex " + level + " does not crash", False, repr(exc))
        else:
            check("c: coreless codex " + level + " uses global set", err is None and efforts == wfcommon.reasoning_levels(), (err, efforts))

# (d): older core exposes only the codex API; retain its specific validation.
with core(fake()):
    err = submit("openai-codex", "gpt-5.3-codex", "minimal")
    check("d: codex-only core rejects minimal", rejected(err, "minimal", CODEX, "low"), err)
    err = submit("anthropic", "claude-opus-5-5", "ultra")
    check("d: codex-only core non-codex global fallback", err is None and door._route_efforts("anthropic", "claude-opus-5-5") == wfcommon.reasoning_levels(), err)

# (e): a broken route API degrades to codex-specific or global vocabulary.
with core(fake(route=True, raises=True)):
    err = submit("openai-codex", "gpt-5.3-codex", "minimal")
    check("e: raised route API retains codex validation", rejected(err, "minimal", CODEX, "low"), err)
    err = submit("anthropic", "claude-opus-5-5", "ultra")
    check("e: raised route API non-codex global fallback", err is None and door._route_efforts("anthropic", "claude-opus-5-5") == wfcommon.reasoning_levels(), err)

print(f"RESULT {fails} FAIL")
raise SystemExit(bool(fails))
