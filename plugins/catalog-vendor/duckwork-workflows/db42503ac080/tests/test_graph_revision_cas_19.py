"""issue #19 (est-19k9w): the graph revision CAS — a caller that read the graph
at revision R may only write against R; a stale write is refused with
{error:'graph_revision_stale', yours, head} and ZERO mutations.

The 09-27 alternating-writers shape: two amends each read the old graph.json,
the later os.replace silently loses the earlier — last-writer-wins with no
conflict signal. The revision is DERIVED ("<seq>:<sha16>": amends-row count +
sha256 of the committed graph bytes) so there is nothing to migrate (R10) and
a token can never drift from the graph it names.

RED proof (before the fix): T1 fails because B's stale amend returns ok.
Pure door test: no runner spawn (_spawn_runner stubbed, _resume_after_action
stubbed); liveness ping stubbed (no network). Stdlib only.
"""
import importlib, json, os, shutil, sys, tempfile, threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
sys.path.insert(0, str(BUILD))

_tmp = tempfile.TemporaryDirectory(prefix=".tmp-cas19-", dir=HERE)
HOME = Path(_tmp.name)
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = "/bin/true"
(HOME / "config.yaml").write_text("model:\n  default: seat-default\n")

import hashlib
import wfcommon  # noqa: E402
sys.modules.pop("duckwork_cli.config", None)
door = importlib.import_module("__init__")

# RED-proof shim: at the pre-#19 base SHA the door has no _graph_revision, so
# compute the head the SAME way locally. The run then dies exactly where the
# bug lives — T1's B amend returns ok instead of the typed refusal.
def _head_local(r):
    try:
        data = (r / "graph.json").read_bytes()
    except OSError:
        return None
    seq = 0
    try:
        with (r / "amends.jsonl").open("r", encoding="utf-8") as f:
            seq = sum(1 for line in f if line.strip())
    except OSError:
        pass
    return f"{seq}:{hashlib.sha256(data).hexdigest()[:16]}"
head_of = getattr(door, "_graph_revision", None) or _head_local
import wf_test_isolation as _iso71; _iso71.install(door)   # #71 r5: pin settings.runs_root
door._spawn_runner = lambda r: 0                            # no runner, no children
door._resume_after_action = lambda r, consumed=None: "respawned"
door._route_liveness_ping = lambda routes: []               # no network

RUNS = Path(os.environ["WF_RUNS_ROOT"])
FAILS = []
def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)

def agent(nid, goal="g", **kw):
    n = {"id": nid, "type": "agent", "goal": goal}
    n.update(kw)
    return n

def fresh(run_id, nodes, with_amends_row=False):
    r = RUNS / run_id
    if r.exists():
        shutil.rmtree(r)
    for d in ("nodes", "gates", "logs"):
        (r / d).mkdir(parents=True)
    (r / "graph.json").write_text(json.dumps({"name": "cas19", "nodes": nodes}))
    (r / "run.json").write_text(json.dumps({"name": "cas19", "duckwork_bin": "/bin/true",
                                            "concurrency": 4}))
    if with_amends_row:   # a run that HAS amended: its head carries a nonzero seq
        (r / "amends.jsonl").write_text(json.dumps(
            {"at": "2026-10-08T00:00:00+00:00", "old": {"name": "cas19", "nodes": []},
             "new": {"name": "cas19", "nodes": nodes}}) + "\n")
    return r

def run_dir_bytes(r):
    """Every byte a refused CAS call must leave untouched."""
    snap = {}
    for p in sorted(r.rglob("*")):
        if p.is_file() and p.name != "graph.lock":
            snap[str(p.relative_to(r))] = p.read_bytes()
    return snap

A = lambda goal="g": {"name": "cas19", "nodes": [agent("a", goal),
                                                 {"id": "gate", "type": "gate",
                                                  "after": ["a"], "question": "go?",
                                                  "options": ["yes"]},
                                                 {"id": "gate2", "type": "gate",
                                                  "after": ["gate"], "question": "go2?",
                                                  "options": ["yes"]}]}

# ---------- T0: the head is derived and rides run/status ----------
r = fresh("20991009-000000-cas19-t0", A("g")["nodes"])
head0 = head_of(r)
check("T0 head is '<seq>:<sha16>' — fresh run is seq 0", 
      head0 and head0.split(":")[0] == "0" and len(head0.split(":")[1]) == 16, head0)
check("T0 head == sha256(graph bytes)[:16] under seq",
      head0 == "0:" + __import__("hashlib").sha256((r / "graph.json").read_bytes()).hexdigest()[:16], head0)
st = door.act_status({"run_id": r.name})
check("T0 status carries graph_revision", st.get("graph_revision") == head0, st.get("graph_revision"))

# ---------- T1 (RED before the fix): stale write refused, ZERO mutations ----------
r = fresh("20991009-000001-cas19-t1", A("g")["nodes"], with_amends_row=True)
head = head_of(r)
check("T1 amended run carries seq 1", head and head.startswith("1:"), head)
b1 = door.act_amend({"run_id": r.name, "graph": A("by-A"), "graph_revision": head})
check("T1 A's amend at the current head applies",
      b1.get("ok") is True and b1.get("error") is None, b1)
check("T1 applied amend echoes the NEW head (seq bumped)",
      b1.get("graph_revision") and b1.get("graph_revision").startswith("2:"), b1.get("graph_revision"))
snap = run_dir_bytes(r)
b2 = door.act_amend({"run_id": r.name, "graph": A("by-B"), "graph_revision": head})  # B still holds the OLD head
check("T1 B's stale amend is REFUSED with the typed error", b2.get("error") == "graph_revision_stale", b2)
check("T1 refusal names BOTH revisions (yours == B's token, head == current)",
      b2.get("yours") == head and b2.get("head") == b1["graph_revision"], b2)
check("T1 refused call wrote NOTHING (whole run-dir byte-for-byte identical)",
      run_dir_bytes(r) == snap,
      sorted(set(run_dir_bytes(r)) ^ set(snap)) or
      [k for k in snap if run_dir_bytes(r).get(k) != snap[k]])

# ---------- T2: the matching revision is accepted ----------
b3 = door.act_amend({"run_id": r.name, "graph": A("by-B"), "graph_revision": b1["graph_revision"]})
check("T2 amend at the CURRENT head applies", b3.get("ok") is True and b3.get("error") is None, b3)
check("T2 committed graph is B's (the refused write never landed, the accepted one did)",
      json.loads((r / "graph.json").read_text())["nodes"][0]["goal"] == "by-B",
      (r / "graph.json").read_text()[:120])
rows = [json.loads(l) for l in (r / "amends.jsonl").read_text().splitlines()]
check("T2 amends rows: two applied, none for the refusal",
      len(rows) == 3 and [bool(x.get("cas")) for x in rows] == [False, True, True], len(rows))
check("T2 CAS rows carry the head they were written against",
      rows[1].get("base_revision") == head and rows[2].get("base_revision") == b1["graph_revision"],
      [rows[1].get("base_revision"), rows[2].get("base_revision")])

# ---------- T3: tokenless call = today's semantics, byte-identical outcome ----------
rT = fresh("20991009-000002-cas19-tokenless", A("g")["nodes"])
rC = fresh("20991009-000003-cas19-cas", A("g")["nodes"])
headT = head_of(rT)
tl = door.act_amend({"run_id": rT.name, "graph": A("edit")})
cc = door.act_amend({"run_id": rC.name, "graph": A("edit"), "graph_revision": headT})
check("T3 tokenless amend still applies (opt-in only)", tl.get("ok") is True, tl)
check("T3 tokenless response equals the CAS response (the ONLY delta vs pre-#19 is the graph_revision key)",
      tl == cc, (sorted(set(tl) ^ set(cc)), {k: (tl.get(k), cc.get(k)) for k in set(tl) | set(cc) if tl.get(k) != cc.get(k)}))
check("T3 committed graph bytes identical tokenless vs CAS",
      (rT / "graph.json").read_bytes() == (rC / "graph.json").read_bytes())
check("T3 run.json bytes identical tokenless vs CAS",
      (rT / "run.json").read_bytes() == (rC / "run.json").read_bytes())
rowT = json.loads((rT / "amends.jsonl").read_text())
rowC = json.loads((rC / "amends.jsonl").read_text())
check("T3 amends rows share the pre-#19 fields identically (at/old/new) — #19 adds only base_revision/cas",
      {k: v for k, v in rowC.items() if k not in ("base_revision", "cas")}
      == {k: v for k, v in rowT.items() if k not in ("base_revision", "cas")}, [sorted(rowT), sorted(rowC)])
check("T3 the amends row records the pinned-ness: cas False tokenless, True CAS; base = the head written against",
      rowT["cas"] is False and rowC["cas"] is True
      and rowT["base_revision"] == rowC["base_revision"] == headT, [rowT.get("cas"), rowC.get("cas")])

# ---------- T4 (R10): a pre-token run dir keeps loading and amending ----------
r4 = fresh("20991009-000004-cas19-pretoken", A("g")["nodes"])
check("T4 fixture: no token file, no amends log (pre-token form)",
      not any(p.name.startswith("graph.revision") or p.name.startswith("revision")
              for p in r4.iterdir()) and not (r4 / "amends.jsonl").exists(),
      sorted(p.name for p in r4.iterdir()))
st4 = door.act_status({"run_id": r4.name})
check("T4 pre-token run still loads (status derives a head from the bytes it has)",
      st4.get("graph_revision") == "0:" + __import__("hashlib").sha256(
          (r4 / "graph.json").read_bytes()).hexdigest()[:16], st4.get("graph_revision"))
am4 = door.act_amend({"run_id": r4.name, "graph": A("v2")})
check("T4 pre-token run amends tokenless exactly as before", am4.get("ok") is True, am4)
check("T4 pre-token first applied amend reads as seq 0 -> 1",
      am4.get("graph_revision", "").startswith("1:"), am4.get("graph_revision"))

# ---------- T5 (R6): two writers, one head — the loser gets the typed refusal ----------
r5 = fresh("20991009-000005-cas19-race", A("g")["nodes"])
h5 = head_of(r5)                  # BOTH read the same head
results = {}
def writer(who, goal):
    results[who] = door.act_amend({"run_id": r5.name, "graph": A(goal), "graph_revision": h5})
tA, tB = threading.Thread(target=writer, args=("A", "by-A")), threading.Thread(target=writer, args=("B", "by-B"))
tA.start(); tB.start(); tA.join(timeout=60); tB.join(timeout=60)
ok_who = [w for w in ("A", "B") if results[w].get("ok")]
no_who = [w for w in ("A", "B") if results[w].get("error") == "graph_revision_stale"]
check("T5 both writers ran", len(results) == 2, results)
check("T5 exactly one writer won, the other got graph_revision_stale",
      len(ok_who) == 1 and len(no_who) == 1, {w: results[w].get("error") or "ok" for w in results})
loser = results[no_who[0]] if no_who else None
check("T5 the loser's error names the head the winner produced",
      loser is not None and loser["head"] == results[ok_who[0]]["graph_revision"] and loser["yours"] == h5,
      loser)
winner_goal = json.loads((r5 / "graph.json").read_text())["nodes"][0]["goal"]
check("T5 the committed graph is the WINNER's (no interleaved loss)",
      winner_goal == f"by-{ok_who[0]}", winner_goal)
check("T5 exactly one amends row — the refused write added none",
      len((r5 / "amends.jsonl").read_text().splitlines()) == 1,
      (r5 / "amends.jsonl").read_text())

# ---------- T6: steer + release obey the same law ----------
r6 = fresh("20991009-000006-cas19-steer", A("g")["nodes"])
h6 = head_of(r6)
door.act_amend({"run_id": r6.name, "graph": A("moved"), "graph_revision": h6})   # move the head
snap6 = run_dir_bytes(r6)
s_bad = door.act_steer({"run_id": r6.name, "node": "a", "text": "steer!", "graph_revision": h6})
check("T6 steer at a stale head is refused with both revisions",
      s_bad.get("error") == "graph_revision_stale" and s_bad.get("yours") == h6
      and s_bad.get("head") != h6, s_bad)
check("T6 refused steer wrote NOTHING (no inbox line, no steer event)",
      run_dir_bytes(r6) == snap6 and not (r6 / "inbox.jsonl").exists())
s_ok = door.act_steer({"run_id": r6.name, "node": "a", "text": "steer!",
                       "graph_revision": head_of(r6)})
check("T6 steer at the current head still queues",
      s_ok.get("ok") is True and (r6 / "inbox.jsonl").exists(), s_ok)

g_bad = door.act_release({"run_id": r6.name, "gate_id": "gate", "answer": "yes",
                          "graph_revision": h6})
check("T6 release at a stale head is refused with both revisions",
      g_bad.get("error") == "graph_revision_stale" and g_bad.get("yours") == h6
      and g_bad.get("head") == head_of(r6), g_bad)
check("T6 refused release wrote NOTHING (no gate answer file)",
      not (r6 / "gates" / "gate.json").exists())
g_ok = door.act_release({"run_id": r6.name, "gate_id": "gate", "answer": "yes",
                         "graph_revision": head_of(r6)})
check("T6 release at the current head answers the gate",
      g_ok.get("ok") is True and (r6 / "gates" / "gate.json").exists(), g_ok)
g_tok = door.act_release({"run_id": r6.name, "gate_id": "gate2", "answer": "again"})
check("T6 tokenless release keeps today's semantics", g_tok.get("ok") is True, g_tok)

# ---------- T7: a malformed token is stale, never accepted ----------
r7 = fresh("20991009-000007-cas19-garbage", A("g")["nodes"])
garbage = door.act_amend({"run_id": r7.name, "graph": A("z"), "graph_revision": "anything-not-a-head"})
check("T7 a garbage token is refused as stale (fail-closed), never crash",
      garbage.get("error") == "graph_revision_stale" and garbage.get("yours") == "anything-not-a-head"
      and garbage.get("head") == head_of(r7), garbage)

# ---------- T8: the schema advertises the arg ----------
props = door.WORKFLOW_SCHEMA["parameters"]["properties"]
check("T8 graph_revision is a documented tool param",
      "graph_revision" in props and "graph_revision_stale" in props["graph_revision"].get("description", ""),
      sorted(props))

print(f"\n{len(FAILS)} FAILS" if FAILS else "\nALL PASS")
sys.exit(1 if FAILS else 0)
