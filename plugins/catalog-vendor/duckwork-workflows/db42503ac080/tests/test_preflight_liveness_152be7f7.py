"""FEEDBACK #152be7f7: preflight LIVENESS ping — warn-and-surface contract.

model_preflight proves RESOLUTION, not liveness: a live-but-quota-dead seat used to
first fail hours later, at the first child spawn, as transport_exhausted. The submit
ping (task='wf-preflight-ping', explicit provider+model, ONE attempt, no ladder of
ours) now annotates the existing routes entries at BOTH submit paths and NEVER blocks
the launch. This test pins the matrix — 429/401/403/404 dead, timeout/5xx/import-missing/
parse-failure/fallback-surprise ALL map to liveness='unknown' AND the run still launches
— with the core import stubbed: a real provider is NEVER called here. Stdlib only.
"""
import importlib, atexit, json, os, sys, tempfile, types
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
tmp_dir = tempfile.TemporaryDirectory(prefix=".tmp-liveness-152be7f7-", dir=HERE / "tests")
atexit.register(tmp_dir.cleanup)
# #71: DUCKWORK_HOME alone does NOT sandbox the shelf — the context-local home
# override outranks the env in lane processes; WF_RUNS_ROOT is checked first and
# pins runs/library wherever the door resolves. Without it, saves pollute prod.
os.environ["DUCKWORK_HOME"] = tmp_dir.name
os.environ["WF_RUNS_ROOT"] = str(Path(tmp_dir.name) / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = "offline"

# ---- stub the core seam BEFORE the door's ping code can reach it ------------------
# `agent` is faked in sys.modules so agent.retry_utils resolves here (and a stray
# agent.reasoning_effort import fails like a non-core host); agent.auxiliary_client is
# NEVER imported — door._import_call_llm is stubbed per case instead. No network.
_fake_agent = types.ModuleType("agent")
_fake_agent.__path__ = []
_fake_ru = types.ModuleType("agent.retry_utils")

def _fake_parse_retry_after(value_or_headers):
    """Mirrors core's parse contract: headers mapping (both casings) or raw value ->
    float seconds, None absent/unparseable."""
    raw = value_or_headers
    if raw is not None and not isinstance(raw, (str, int, float)):
        getter = getattr(raw, "get", None)
        if not callable(getter):
            return None
        try:
            raw = getter("Retry-After")
            if raw is None:
                raw = getter("retry-after")
        except Exception:
            return None
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return max(0.0, float(str(raw).strip()))
    except (TypeError, ValueError):
        return None

_fake_ru.parse_retry_after_seconds = _fake_parse_retry_after
sys.modules["agent"] = _fake_agent
sys.modules["agent.retry_utils"] = _fake_ru

door = importlib.import_module("__init__")
import wf_test_isolation as _iso71; _iso71.install(door)  # #71 r5: pin settings.runs_root alongside WF_RUNS_ROOT
door._CTX = None
door._seat_model_cfg = lambda: {"default": "seat-default", "aliases": {"bare": "bare-model"}}
door._seat_aliases = lambda: ["bare"]
door._seat_default = lambda: "seat-default"
_spawned = []
door._spawn_runner = lambda r: _spawned.append(r.name)

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  -- {detail}" if detail and not cond else ""))
    fails += 0 if cond else 1

# ---- ping double: records every call; behavior per case ----------------------------
CALLS = []

class FakeHTTPError(Exception):
    """Openai-shaped error: status attr + response.headers carry Retry-After; str() is
    the escape-line format (the header value is NOT in str — recon p0 proved that)."""
    def __init__(self, status, headers=None):
        super().__init__(f"Error code: {status} - {{'error': {{'message': 'quota exhausted'}}}}")
        self.status_code = status
        self.response = types.SimpleNamespace(headers=headers) if headers is not None else None

class EscapeLineOnly(Exception):
    """No status attr — str() alone is the oneshot.py:322 escape line (regex path)."""

def fake_call_llm(behavior):
    def call_llm(task=None, provider=None, model=None, messages=None, max_tokens=None,
                 timeout=None, route_info=None, **kw):
        CALLS.append({"task": task, "provider": provider, "model": model,
                      "messages": messages, "max_tokens": max_tokens, "timeout": timeout})
        if route_info is not None:
            route_info.update(behavior.get("record",
                                {"provider": str(provider or ""), "model": str(model or "")}))
        exc = behavior.get("raise_")
        if callable(exc):  # per-route double: exc(provider, model) -> exception or None
            exc = exc(provider, model)
        if exc is not None:
            raise exc
        return "pong"
    return call_llm

def set_ping(behavior):
    """behavior=None restores the non-core host (import raises); dict stubs the import.
    The seam is _import_call_llm — it must RETURN the double (the door calls it, then
    calls what it got back); handing the double to the door directly misrepresents the
    seam and the call site's TypeError gets blamed for the ping."""
    if behavior is None:
        door._import_call_llm = _raise_import_error
    else:
        double = fake_call_llm(behavior)
        door._import_call_llm = lambda: double

def _raise_import_error():
    raise ImportError("No module named 'agent'")

def graph_two_routes():
    """a+b share openai/m-1 (distinct-route dedupe), c rides openai-codex/m-2,
    d is seat default (no provider+model to pin), e is a bare alias (provider None).
    #25 moved this fixture to require_route:false on the pinned nodes: this file
    pins the ping's ANNOTATION matrix (liveness/retry_after/hint), which must hold
    whatever the verdict does; test_require_route_25.py pins the default-on gate."""
    return {"name": "live", "nodes": [
        {"id": "a", "type": "agent", "goal": "x", "provider": "openai", "model": "m-1", "require_route": False},
        {"id": "b", "type": "agent", "goal": "x", "provider": "openai", "model": "m-1", "require_route": False},
        {"id": "c", "type": "agent", "goal": "x", "provider": "openai-codex", "model": "m-2", "require_route": False},
        {"id": "d", "type": "agent", "goal": "x"},
        {"id": "e", "type": "agent", "goal": "x", "model": "bare"},
    ]}

PASTE = "PASTE this line alone in your reply, then call wait: "

def submit_run(g=None):
    CALLS.clear()
    out = door.act_run({"graph": g or graph_two_routes()})
    return out

# ---- 1. happy path: alive annotation, pinned call args, ONE ping per distinct route
set_ping({})
out = submit_run()
r = out.get("routes", {})
check("run launches (run_id + spawn)", bool(out.get("run_id")) and len(_spawned) == 1, out)
check("alive annotated", r.get("a", {}).get("liveness") == "alive"
      and r.get("b", {}).get("liveness") == "alive" and r.get("c", {}).get("liveness") == "alive", r)
check("one ping per DISTINCT route (dedupe: 3 pinned nodes -> 2 pings)",
      len(CALLS) == 2, CALLS)
check("pinned args: task/provider/model/max_tokens=1/timeout, single attempt",
      all(c["task"] == "wf-preflight-ping" and c["max_tokens"] == 1
          and c["timeout"] == door.PING_TIMEOUT_S and c["provider"] and c["model"]
          and c["messages"] == [{"role": "user", "content": "ping"}] for c in CALLS)
      and {(c["provider"], c["model"]) for c in CALLS} ==
          {("openai", "m-1"), ("openai-codex", "m-2")}, CALLS)
check("unpinnable routes: liveness='unknown', ping skipped",
      r.get("d", {}).get("liveness") == "unknown" and r.get("e", {}).get("liveness") == "unknown", r)
check("hint stays the copy-exact paste line (no dead copy)",
      out.get("hint", "").startswith(PASTE) and "preflight liveness" not in out.get("hint", ""), out)
check("annotation rides the EXISTING routes dict (requested/resolved kept)",
      set(("requested", "resolved", "liveness")) <= set(r["a"]) and
      r["a"]["resolved"] == {"provider": "openai", "model": "m-1"}, r["a"])
check("no new door schema keys (params speak no liveness)",
      "liveness" not in json.dumps(door.WORKFLOW_PARAMS)
      and "retry_after_s" not in json.dumps(door.WORKFLOW_PARAMS))

# ---- 2. 429 WITH Retry-After: dead + retry_after_s + hint copy; run STILL launches -
# Per-route failure: the quota is the openai/m-1 seat's — the codex route answers pong
# (the check below pins "other route's verdict kept"; a shared raise_ would fake a
# two-route outage and erase that assertion's meaning).
def _quota_dead_429(provider, model):
    if (provider, model) == ("openai", "m-1"):
        return FakeHTTPError(429, {"Retry-After": "3600"})
    return None

set_ping({"raise_": _quota_dead_429})
out = submit_run()
r = out.get("routes", {})
check("429 -> dead (both sharing nodes annotated)",
      r.get("a", {}).get("liveness") == "dead" and r.get("b", {}).get("liveness") == "dead", r)
check("Retry-After survives: retry_after_s == 3600.0",
      r["a"].get("retry_after_s") == 3600.0, r["a"])
check("dead run LAUNCHES anyway (run_id + spawn + other route's verdict kept)",
      bool(out.get("run_id")) and len(_spawned) == 2
      and r.get("c", {}).get("liveness") == "alive", out)
h = out.get("hint", "")
check("hint: paste prefix copy-exact, dead copy rides behind it",
      h.startswith(PASTE) and "preflight liveness:" in h
      and "route openai/m-1: dead (retry after 3600s)" in h
      and "repoint node(s) a, b" in h, h)

# ---- 3. 429 WITHOUT the header: retry_after_s None — honest, never fabricated ------
set_ping({"raise_": FakeHTTPError(429, None)})
out = submit_run()
a = out["routes"]["a"]
check("429 no header -> dead + retry_after_s None (not fabricated)",
      a.get("liveness") == "dead" and "retry_after_s" in a and a["retry_after_s"] is None, a)
check("hint says retry-after absent", "retry-after absent" in out.get("hint", ""), out.get("hint"))

# ---- 4. escape-line-only 429 (status lives ONLY in str): still dead -----------------
exc = EscapeLineOnly("Error code: 429 - {'error': {'message': 'Rate limit reached'}}")
set_ping({"raise_": exc})
out = submit_run()
check("escape-line-only 429 classified dead (str regex path)",
      out["routes"]["a"].get("liveness") == "dead", out["routes"]["a"])

# ---- 5. auth-ish dead statuses: 401 (and 403/404) -> dead --------------------------
for st in (401, 403, 404):
    set_ping({"raise_": FakeHTTPError(st)})
    out = submit_run()
    check(f"{st} -> dead", out["routes"]["a"].get("liveness") == "dead", out["routes"]["a"])

# ---- 6. THE FAIL-OPEN CONTRACT: every failure path -> unknown AND the run launches -
def contract(label, behavior, expect_note=None):
    n_before = len(_spawned)
    set_ping(behavior)
    out = submit_run()
    ok = ("error" not in out and bool(out.get("run_id"))
          and len(_spawned) == n_before + 1
          and all((out.get("routes", {}).get(k) or {}).get("liveness") in ("unknown", "alive")
                  and (out.get("routes", {}).get(k) or {}).get("liveness") != "dead"
                  for k in ("a", "b", "c")))
    if expect_note:
        ok = ok and expect_note in str(out.get("routes", {}).get("a", {}).get("note", ""))
    check(label, ok, out)

contract("timeout -> unknown + LAUNCHES", {"raise_": TimeoutError("read timed out")})
contract("transient 500 -> unknown (never dead) + LAUNCHES", {"raise_": FakeHTTPError(500)})
contract("429 on an UNATTRIBUTED route (fallback answered) -> unknown + LAUNCHES",
         {"raise_": FakeHTTPError(429, {"Retry-After": "60"}),
          "record": {"provider": "main-agent(other-co)", "model": "someone-else"}})
contract("fallback answered OK cross-route -> unknown, NOT alive + LAUNCHES",
         {"record": {"provider": "fallback_chain[0](other)", "model": "other-model"}},
         expect_note="not counted as alive")
contract("core import missing (non-core host) -> unknown + LAUNCHES, zero pings",
         None, expect_note="not importable")
# submit_run() cleared CALLS at entry; the import-missing ping must have added none.
check("import-missing path made no call_llm attempt", len(CALLS) == 0, CALLS)
contract("weird raise (parse failure flavor) -> unknown + LAUNCHES",
         {"raise_": RuntimeError("attempt to parse the unparsable")})

# ---- 7. credential-looking str scrubbed out of the note -----------------------------
class KeyLeak(Exception):
    pass
set_ping({"raise_": KeyLeak(
    "Error code: 429 - leak: sk-ABCDEFGHIJKLMNOP and api_key = hunter2hunter2")})
out = submit_run()
note = out["routes"]["a"].get("note", "")
check("note scrubs key-shaped strings (never echoes credentials)",
      "sk-ABCDEFGHIJKLMNOP" not in note and "hunter2hunter2" not in note
      and "[redacted]" in note and "429" in note, note)

# ---- 8. amend submit pings too: dead annotates, amend APPLIES anyway ---------------
set_ping({"raise_": FakeHTTPError(429, {"Retry-After": "3600"})})
root = Path(os.environ["DUCKWORK_HOME"]) / "workflows"
rdir = root / "amend-live"
(rdir / "nodes").mkdir(parents=True)
(rdir / "gates").mkdir()
old_graph = {"name": "amend-live", "nodes": [{"id": "a", "type": "agent", "goal": "old"}]}
(rdir / "graph.json").write_text(json.dumps(old_graph))
CALLS.clear()
am = door.act_amend({"run_id": "amend-live",
                     "graph": graph_two_routes()})
check("amend APPLIES despite dead ping (ok, applies, spawned/restart requested)",
      am.get("ok") is True and "applies" in am, am)
check("amend pings BOTH submit-time routes",
      {(c["provider"], c["model"]) for c in CALLS} == {("openai", "m-1"), ("openai-codex", "m-2")},
      CALLS)
check("amend echoes the annotated routes (dead + retry_after_s)",
      am["routes"]["a"].get("liveness") == "dead" and am["routes"]["a"]["retry_after_s"] == 3600.0,
      am["routes"]["a"])
check("amend hint carries the dead copy behind its own copy",
      "preflight liveness:" in am.get("hint", "") and "route openai/m-1: dead" in am.get("hint", ""),
      am.get("hint"))

# ---- 9. amend dry_run previews the verdict WITHOUT writing anything -----------------
CALLS.clear()
# Baseline = what section 8's APPLIED amend wrote; "nothing written" means unchanged
# from the moment before the dry_run, not from the pre-amend graph.
_on_disk_before = (rdir / "graph.json").read_text()
dr = door.act_amend({"run_id": "amend-live", "dry_run": True, "graph": graph_two_routes()})
check("dry_run previews liveness (dead annotated, hint carries copy, nothing written)",
      dr.get("dry_run") is True and dr["routes"]["a"].get("liveness") == "dead"
      and "preflight liveness:" in dr.get("hint", "")
      and (rdir / "graph.json").read_text() == _on_disk_before, dr)

# ---- 10. ping outcome NEVER turns into an error return: raw helper never raises -----
class HostileStr(Exception):
    def __str__(self):
        raise RuntimeError("str() itself explodes")

for label, behavior in (("hostile __str__", {"raise_": HostileStr()}),
                        ("healthy", {}),
                        ("no route_info support", {"raise_": TypeError("call_llm() got an "
                                                                        "unexpected keyword argument 'route_info'")})):
    # set_ping keeps the seam honest: _import_call_llm RETURNS the double; the door
    # then calls it. (A direct assignment here made the "healthy" case secretly the
    # import-error path and skipped the real call site entirely.)
    set_ping(behavior)
    try:
        ann = door._ping_route_once("openai", "m-9")
        ok = ann.get("liveness") in ("alive", "unknown", "dead")
    except BaseException as e:
        ok = False
        ann = {"raised": repr(e)}
    check(f"_ping_route_once never raises ({label})", ok, ann)

print(f"\n{'ALL PASS' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
