"""est-2ek.1.318 (zap repro, feedback ca7063bb815cf679): a node pinned to a seat
alias ('bigseat' -> example-provider/example-model-1) must PING and REPORT the alias TARGET
id, not the bare alias (which answered 'route DEAD at submit (HTTP 404 model: bigseat)').
The node def keeps model:'bigseat' verbatim (house contract); non-alias literals are
unchanged. Stdlib only, no network (_ping_route_once is stubbed)."""
import importlib, atexit, os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
tmp_dir = tempfile.TemporaryDirectory(prefix=".tmp-alias318-", dir=HERE / "tests")
atexit.register(tmp_dir.cleanup)
tmp = tmp_dir.name
os.environ["DUCKWORK_HOME"] = tmp
os.environ.setdefault("WF_RUNS_ROOT", str(Path(tmp) / "workflows"))
door = importlib.import_module("__init__")
import wf_test_isolation as _iso71; _iso71.install(door)

fails = 0
def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + (f"  -- {detail}" if detail and not cond else ""))
    fails += 0 if cond else 1

class Ctx:
    def __init__(self, tiers): self.t = tiers
    def get_config(self, k, d=None): return self.t if k == "models" else d

door._CTX = Ctx({})
door._seat_model_cfg = lambda: {"default": "seat-default",
                                "aliases": {"bigseat": "example-provider/example-model-1"}}
pinged = []
def _fake_ping(p, m):
    pinged.append((p, m))
    return {"liveness": "alive"}
door._ping_route_once = _fake_ping

# 1. alias node: resolved route speaks the TARGET id; node def keeps the alias
nodes = [{"id": "a", "type": "agent", "goal": "x", "model": "bigseat"}]
err, table, routes = door._resolve_models(nodes)
check("alias resolves without error", err is None, err)
res = (routes or {}).get("a", {}).get("resolved", {})
check("routes[a].resolved.model is the alias TARGET id",
      res.get("model") == "example-model-1", res)
check("routes[a].resolved.provider is the alias provider",
      res.get("provider") == "example-provider", res)
check("routes[a].requested.model stays the alias",
      (routes or {}).get("a", {}).get("requested", {}).get("model") == "bigseat", routes)
check("node def keeps model:'bigseat' verbatim", nodes[0]["model"] == "bigseat", nodes[0])
door._route_liveness_ping(routes or {})
check("_route_liveness_ping is handed the TARGET id, not the bare alias",
      pinged == [("example-provider", "example-model-1")], pinged)

# 1b. the proof receipt names what the ping PROVED (the target id), not the bare
# alias (ra-review observation on the route_verified bake; runner _route_hold still
# accepts the served model via its alias-map candidates).
door._route_enforcement({"nodes": nodes}, routes)
check("alive proof route_verified bakes the TARGET id the ping proved",
      nodes[0].get("route_verified") == "example-provider/example-model-1",
      nodes[0].get("route_verified"))
check("node def STILL keeps model:'bigseat' after the bake",
      nodes[0]["model"] == "bigseat", nodes[0])

# 2. non-alias literal (explicit provider) is unchanged
pinged.clear()
nodes = [{"id": "b", "type": "agent", "goal": "x",
          "provider": "example-provider", "model": "example-model-2"}]
err, table, routes = door._resolve_models(nodes)
res = (routes or {}).get("b", {}).get("resolved", {})
check("literal resolves without error", err is None, err)
check("literal resolved route unchanged",
      res == {"provider": "example-provider", "model": "example-model-2"}, res)
check("literal node def unchanged", nodes[0]["model"] == "example-model-2", nodes[0])
door._route_liveness_ping(routes or {})
check("literal pinged verbatim", pinged == [("example-provider", "example-model-2")], pinged)

print(f"{'FAILED' if fails else 'OK'}: {fails} failure(s)")
sys.exit(1 if fails else 0)
