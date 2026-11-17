"""#71 (r5): the in-process door-writer isolation mechanism — a resolver-level pin.

`WF_RUNS_ROOT` alone is NOT a sandbox. The resolver's precedence (#42 — owner design
for real users, deliberately UNCHANGED here) is:

    settings.runs_root  >  WF_RUNS_ROOT env  >  <duckwork_home>/workflows

`WF_RUNS_ROOT` outranks only the home-derived DEFAULT — it does NOT outrank an
owner-configured `plugins.entries.duckwork-workflows.settings.runs_root`. A lane
process carries core's context-local home override (`set_duckwork_home_override`,
invisible to `os.environ`), so a ctx-less door raw-reads the ESTATE profile's
config.yaml; when that file carries the owner setting, every write goes THROUGH
the env pin into the owner's real library — and the test still prints ALL PASS.

A writer is sandboxed only when BOTH doors resolve to the same scratch root:

  * `WF_RUNS_ROOT` — the env pin (already in every writer test);
  * the plugin's `settings.runs_root` — neutralised here at the RESOLVER, not the
    ctx. The door publishes its owner-settings reader (`_owner_setting_read`) into
    wfcommon via `set_owner_setting_reader`; install() wraps THAT function,
    intercepting ONLY the `runs_root` lookup: it answers the CURRENT
    `os.environ["WF_RUNS_ROOT"]` lazily at call time (so the two pins can never
    drift), and when the env pin is unset every key — `runs_root` included — rides
    through to the untouched original reader, i.e. exactly today's raw config.yaml
    fallback answer.

Why the resolver and not `door._CTX`: the door guards its ctx call sites on
truthiness (`if not _CTX: return NO_READER` in `_owner_setting_read`;
`_CTX.get_config("models", {}) if _CTX else {}` in `model_tiers`). A truthy
placeholder ctx flips EVERY ctx-less site into get_config calls and leaks the
NO_READER sentinel into model code (`'object' has no attribute 'items'`). The
resolver wrap leaves `_CTX` — and every ctx-less truthiness path — byte-identical
to an untouched door, and a later `_CTX = …` reassignment still takes full effect
(the original reader reads the module global at call time). Stdlib-only.

Usage, directly after the door module is exec'd:

    import wf_test_isolation as _iso71
    _iso71.install(door)

For a door exec'd inside a SUBPROCESS source string whose env already pins
WF_RUNS_ROOT (claim/team children, tool-bridge probes), bootstrap this file by
explicit path in the child — `importlib.util.spec_from_file_location(..., ROOT /
"tests" / "wf_test_isolation.py")` — then call `install(door)` on the child's
door. The S3 audit is text-based, so a string-embedded door counts as a writer
and its pin must live inside that string.
"""
import os
import sys
from pathlib import Path

try:  # the suite runs tests as scripts; make the repo root importable anyway
    _root = str(Path(__file__).resolve().parents[1])
    if _root not in sys.path:
        sys.path.insert(0, _root)
except Exception:
    pass


def _wrap_resolver(inner, env_key="WF_RUNS_ROOT"):
    """Wrap the door's owner-settings reader: the `runs_root` lookup answers the
    CURRENT env pin (lazy — one root, whichever door the resolver takes); every
    other key, and `runs_root` itself when the env pin is unset, rides through to
    the untouched original reader."""
    def resolver(key):
        if key == "runs_root":
            root = os.environ.get(env_key, "")
            if root:
                return root
        return inner(key)
    resolver._iso71_pinned = True
    resolver._iso71_inner = inner
    return resolver


def install(door, env_key="WF_RUNS_ROOT"):
    """Pin the door's `settings.runs_root` to whatever `WF_RUNS_ROOT` says at call
    time — call it right after the door module is exec'd. Binds the door's OWN
    `_owner_setting_read` (which reads the door's `_CTX` at call time, so a later
    `door._CTX = …` still takes full effect) and publishes the wrapper through the
    same `set_owner_setting_reader` path the door itself uses at exec — the same
    last-writer-wins process policy an untouched exec has. The door's truthiness
    call sites and the ctx-less raw fallback stay byte-identical.
    Idempotent: re-installing the same door is a no-op."""
    common = getattr(door, "_common", None)
    if getattr(common, "NO_READER", None) is None:
        raise AttributeError("door exposes no _common.NO_READER — wrong module?")
    inner = getattr(door, "_owner_setting_read", None)
    if not callable(inner):
        raise AttributeError("door exposes no _owner_setting_read — wrong module?")
    cur = common._OWNER_SETTING_READER
    if getattr(cur, "_iso71_pinned", False) and getattr(cur, "_iso71_inner", None) is inner:
        return cur  # already pinned for this door
    pinned = _wrap_resolver(inner, env_key)
    common.set_owner_setting_reader(pinned)
    return pinned
