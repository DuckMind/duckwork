"""v0.8.0 routing regression + v0.7.3 contracts: (1) literal ids that target a seat alias
stay literal; explicit provider/model pairs route through the child command;
(2) every child spawn carries a deterministic session key `wf:<run>:<node>[:<i>]:<efp8>`
on node.started / item.started / item.finished and in the committed record;
(3) child_metrics joins those keys against state.db sessions rows and folds attempts."""
import json, os, sqlite3, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
home = HERE / "home7"
if home.exists():
    import shutil; shutil.rmtree(home)
home.mkdir()
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
(home / "config.yaml").write_text("model:\n  default: qwen38-next\n  aliases:\n    sol: openai-codex/gpt-6-sol\n    fable: anthropic/claude-fable-5.1\n")
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402
sys.modules.pop("duckwork_cli.config", None)
import importlib.util
spec = importlib.util.spec_from_file_location("door7", BUILD / "__init__.py")
door = importlib.util.module_from_spec(spec); spec.loader.exec_module(door)

ok = 0
def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1; print("PASS", msg)

# --- (1) explicit literals and aliases are not rewritten ---
nodes = [{"id": "a", "type": "agent", "goal": "x", "model": "openai-codex/gpt-6-sol"},
         {"id": "b", "type": "agent", "goal": "x", "model": "sol"},
         {"id": "c", "type": "agent", "goal": "x", "model": "anthropic/claude-opus-5-5"},
         {"id": "g", "type": "gate", "question": "q", "options": ["y"]}]
err, table = door.resolve_models(nodes)
check(err is None, "resolve_models accepts alias targets + unknown literal")
# est-2ek.1.46: a literal whose prefix is a provider the seat routes through bakes that provider
# (a bare `-m openai-codex/...` died HTTP 400 on the seat default route); the table row keeps the full route.
check((nodes[0].get("provider"), nodes[0]["model"]) == ("openai-codex", "gpt-6-sol"), "literal alias-target bakes its provider")
check(table["a"] == "openai-codex/gpt-6-sol", "routing table preserves explicit literal")
check(nodes[1]["model"] == "sol", "alias untouched")
check((nodes[2].get("provider"), nodes[2]["model"]) == ("anthropic", "claude-opus-5-5"), "seat-routed vendor literal bakes its provider")

# --- (2) keys on events + record, via the real runner and fake duckwork ---
fake = str(HERE / "fake")  # the executable shim (fake_duckwork.py is not +x)
runs = home / "workflows"; runs.mkdir()
graph = {"name": "keys", "nodes": [
    {"id": "solo", "type": "agent", "goal": "OK"},
    {"id": "fan", "type": "agent", "after": ["solo"], "fanout": {"items": ["p", "q"], "goal": "OK {item}"}}]}
run = runs / "20990101-000000-keys"; (run / "nodes").mkdir(parents=True); (run / "gates").mkdir()
(run / "graph.json").write_text(json.dumps(graph))
(run / "run.json").write_text(json.dumps({"name": "keys", "duckwork_bin": fake, "concurrency": 4, "node_timeout": 30, "started": "2099-01-01T00:00:00+00:00"}))
p = subprocess.run([sys.executable, str(BUILD / "wf.py"), "run", run.name], capture_output=True, text=True, timeout=120,
                   env={**os.environ, "DUCKWORK_HOME": str(home), "WF_RUNS_ROOT": str(runs), "FAKE_LOG": str(home / "fake.log"), "FAKE_ARGV_LOG": str(home / "fake_duckwork_argv.log")})
assert (run / "events.jsonl").exists(), p.stdout + p.stderr
ev = [json.loads(l) for l in (run / "events.jsonl").read_text().splitlines()]
byid = {n["id"]: n for n in graph["nodes"]}
started = {e["node"]: e for e in ev if e["event"] == "node.started"}
pre_solo = f"wf:{run.name}:solo:{wfcommon.efp(byid, byid['solo'])[:8]}."
exp_solo = started["solo"].get("skey")
check(exp_solo and exp_solo.startswith(pre_solo) and len(exp_solo) == len(pre_solo) + 6, "node.started carries wf:<run>:<node>:<efp8>.<nonce>")
check(started["fan"].get("skey") is None, "fan-out node.started has no key (items carry theirs)")
istart = sorted((e for e in ev if e["event"] == "item.started"), key=lambda e: e["index"])
pre_fan1 = f"wf:{run.name}:fan:1:{wfcommon.efp(byid, byid['fan'])[:8]}."
exp_fan1 = istart[1]["skey"] if len(istart) == 2 else ""
check(exp_fan1.startswith(pre_fan1), "item.started per item with :<i>: key")
fin1 = next(e for e in ev if e["event"] == "item.finished" and e["index"] == 1)
check(fin1["skey"] == exp_fan1, "item.finished carries the SAME key as item.started (one nonce per spawn)")
ifin = [e for e in ev if e["event"] == "item.finished"]
check(all(e.get("skey") and e.get("ms") is not None for e in ifin), "item.finished carries skey + ms")
rec = json.loads((run / "nodes" / "solo.json").read_text())
check(rec.get("skey") == exp_solo and rec.get("attempts") == 1, "committed record carries skey + attempts")
argv = (home / "fake_duckwork_argv.log").read_text()
check(f"--continue {exp_solo}#a0 --create-if-missing" in argv, "child spawned with --continue <key>#a0 --create-if-missing")

# --- (3) child_metrics join + fold ---
db = home / "state.db"
c = sqlite3.connect(db)
c.execute("create table sessions (id text primary key, title text, model text, billing_provider text, input_tokens int, output_tokens int, "
          "cache_read_tokens int, reasoning_tokens int, api_call_count int, tool_call_count int, estimated_cost_usd real, "
          "last_activity_at real, last_activity_description text, ended_at real, started_at real)")
now = time.time()
rows = [("s1", exp_solo + "#a0", "qwen38-next", "provider-a", 100, 10, 0, 0, 1, 0, 0.0, now - 30, "", now - 29, now - 40),
        ("s2", exp_solo + "#a1", "qwen38-next", "provider-b", 120, 20, 0, 0, 2, 1, 0.0, now - 10, "", now - 9, now - 28),   # retry attempt
        ("s3", exp_fan1 + "#a0", "sol", "provider-sol", 500, 50, 400, 0, 3, 4, 0.0123, now - 2, "terminal: ls", None, now - 20),  # live
        ("s4", "wf:OTHER-run:solo:deadbeef.aaaaaa#a0", "x", None, 9999, 9, 0, 0, 9, 9, 9.0, now, "", now, now),
        ("s5", pre_fan1 + "zzzzzz#a0", "sol", None, 1, 1, 0, 0, 1, 1, 0.0, now - 60, "", now - 55, now - 70)]  # earlier crashed spawn of item 1
c.executemany("insert into sessions values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows); c.commit(); c.close()
cm = wfcommon.child_metrics(run.name, home)
check(set(cm) == {exp_solo, exp_fan1, pre_fan1 + "zzzzzz"}, "join scoped to this run's keys, attempts folded under base key, spawns distinct")
check(cm[exp_solo]["tokens_in"] == 220 and cm[exp_solo]["attempts"] == 2 and cm[exp_solo]["ended"] is not None,
      "solo: two attempts summed, ended")
check(cm[exp_fan1]["ended"] is None and cm[exp_fan1]["tool_calls"] == 4 and cm[exp_fan1]["last_desc"] == "terminal: ls",
      "fan item 1: live (ended None), tool_calls + last activity surfaced")
check(cm[exp_solo]["billing_provider"] == "provider-b", "last non-null billing provider wins across attempts")
check(abs(cm[exp_fan1]["cost"] - 0.0123) < 1e-9 and cm[exp_fan1]["model"] == "sol", "cost + model carried")

# read model folds per node + run
sys.path.insert(0, str(BUILD / "dashboard"))
import plugin_api  # noqa: E402
os.environ["DUCKWORK_HOME"] = str(home)
os.environ["WF_RUNS_ROOT"] = str(Path(os.environ["DUCKWORK_HOME"]) / "workflows")  # est-2ek.1.762 pin: DUCKWORK_HOME alone is not a sandbox
view = plugin_api._view(run, full=True)
check(view["nodes"]["solo"]["metrics"]["tokens_in"] == 220, "read model: node metrics folded")
check(view["nodes"]["fan"]["item_metrics"][1]["tool_calls"] == 5 and view["nodes"]["fan"]["item_metrics"][1]["live"] == 0, "read model: item spend folds respawns but an unended DB row is not a live process")
check(view["metrics"]["children"] == 3 and view["metrics"]["live"] == 0, "read model: old unended session without verified process is not live")

# act_status compact line
st = door.act_status({"run_id": run.name})
check(st["metrics"]["tokens"] == "721▸81" and st["nodes"]["solo"]["metrics"]["children"] == 1, "act_status: compact tokens line + per-node")
print(f"\nALL PASS ({ok})")
