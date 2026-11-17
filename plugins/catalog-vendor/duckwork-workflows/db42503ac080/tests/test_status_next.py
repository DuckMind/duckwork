"""A2 + A3 + O1 acceptance (L6): failed/partial nodes ship node_facts beside the
error line; every status/wait carries the derived `next` and the `card` line.

Hand-built run dirs (records written the way wf.py commits them). Stdlib-only +
the plugin's own imports. The read-model lock: `next` never contradicts the
payload it rides in — every amend row names a failed node, the release row names
the held gate, wait appears only for unfinished states, terminal states are [].
"""
# Ledger 95d7010295d70102: stamped fixtures verify under their own rule; ambiguous unstamped records fail closed.
import importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wfcommon

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

HOME = Path(tempfile.mkdtemp(prefix="home-status-next-", dir=str(ROOT)))
os.environ["DUCKWORK_HOME"] = str(HOME)
door = load("status_next_door", ROOT / "__init__.py")

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg} — {detail}" if detail else msg
    ok += 1; print("PASS", msg)

def CARD(rid):
    return f'::workflow{{id="{rid}"}}'

def mk(rid, nodes, records=None, events=None, runner_exit=None):
    r = HOME / "workflows" / rid
    (r / "nodes").mkdir(parents=True)
    (r / "logs").mkdir()
    (r / "gates").mkdir()
    graph = {"name": rid, "nodes": nodes}
    (r / "graph.json").write_text(json.dumps(graph))
    (r / "run.json").write_text(json.dumps({"name": rid, "duckwork_bin": "/bin/true"}))
    byid = {n["id"]: n for n in nodes}
    for nid, rec in (records or {}).items():
        d = dict(rec)
        n = byid[nid]
        d.setdefault("efp", wfcommon.efp(byid, n))
        d.setdefault("fp_rule_version", wfcommon.FP_RULE_VERSION)
        (r / "nodes" / f"{nid}.json").write_text(json.dumps(d))
    if events is not None:
        (r / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    if runner_exit is not None:
        (r / "runner_exit.json").write_text(json.dumps(runner_exit))
    return r

payloads = {}  # status -> payload, for the cross-check sweep at the end

try:
    # ---------- fixture F: failed run — the fake child's last words ------------
    fa = {"id": "solo", "type": "agent", "goal": "do it"}
    fb = {"id": "die", "type": "agent", "goal": "print one line then die", "after": ["solo"]}
    FINAL = "I printed my final line and I know I did not finish"
    LOGF = HOME / "workflows" / "sn-fail" / "logs" / "die.a1.log"
    PF = HOME / "workflows" / "sn-fail" / "logs" / "die.a1.prompt.md"
    rf = mk("sn-fail", [fa, fb], records={
        "solo": {"status": "done", "output": {"ok": True}, "ms": 10, "attempts": 1},
        "die": {"status": "failed", "error": "child exit 1", "error_class": "child_exit",
                "output": None, "ms": 4200, "attempts": 2,
                "attempts_log": [{"attempt": 0, "error_class": "timeout"},
                                 {"attempt": 1, "error_class": "child_exit"}],
                "final": FINAL, "log_path": str(LOGF), "prompt_path": str(PF)},
    }, events=[{"event": "node.done", "node": "solo"}])
    LOGF.write_bytes(b"child stderr tail\n")
    PF.write_text("# prompt\n")
    pf = door.act_status({"run_id": "sn-fail"}); payloads["failed"] = pf
    check(pf["status"] == "failed", "failed fixture: run status failed", str(pf)[:160])
    nf = pf["nodes"]["die"].get("node_facts")
    check(isinstance(nf, dict), "A2 ACCEPT: status.nodes[die] carries node_facts", repr(pf["nodes"]["die"])[:200])
    check(nf and nf["final"] == FINAL, "A2 ACCEPT: final == the fake child's last line", repr(nf)[:120])
    check(nf and nf["error_class"] == "child_exit", "A2 ACCEPT: error_class set", repr(nf)[:120])
    check(nf and isinstance(nf["attempts"], int) and nf["attempts"] >= 1, "A2 ACCEPT: attempts >= 1", repr(nf)[:120])
    check(nf and str(nf["log_path"]).endswith(".log"), "A2 ACCEPT: log_path ends in .log", repr(nf)[:160])
    check(nf and [a["attempt"] for a in nf["attempts_log"]] == [0, 1], "A2: attempts_log rides verbatim", repr(nf.get("attempts_log"))[:120])
    check(nf and nf["prompt_path"] == str(PF),
          "A2: prompt_path rides verbatim (honest unknown if the record lacks it)", repr(nf)[:160])
    check(set(nf) == {"error_class", "attempts", "attempts_log",
          "final", "log_path", "prompt_path"}, "A2: closed key set only", str(sorted(nf)))
    check(pf["nodes"]["die"].get("error") == "child exit 1",
          "A2: facts ride BESIDE the error line (error still shipped)", repr(pf["nodes"]["die"])[:200])
    check("node_facts" not in pf["nodes"]["solo"], "A2: a done node ships no node_facts", "")
    # A3: failed -> one amend row per failed node, naming it with its error_class
    check(pf.get("next") == [{"action": "amend", "node": "die", "error_class": "child_exit"}],
          "A3 ACCEPT: failed next names each failed node with error_class",
          json.dumps(pf.get("next")))
    wf = door.act_wait({"run_id": "sn-fail", "timeout": 0})
    check(wf.get("next") == pf.get("next"), "wait on a failed run answers the same next", json.dumps(wf.get("next")))

    # ---------- fixture P: partial node keeps its facts ----------------------
    pp = mk("sn-partial", [{"id": "harv", "type": "agent", "goal": "die after json"}], records={
        "harv": {"status": "partial", "output": {"result": "harvested"}, "error": "died late",
                 "error_class": "timeout", "harvest": {"declared_status": None},
                 "attempts": 1, "attempts_log": [{"attempt": 0, "error_class": "timeout"}],
                 "final": "most of the way", "log_path": str(HOME / "workflows" / "sn-partial" / "logs" / "harv.a0.log")},
    }, events=[{"event": "node.partial", "node": "harv"}])
    pst = door.act_status({"run_id": "sn-partial"}); payloads["partial-done"] = pst
    check(pst["nodes"]["harv"].get("node_facts") and pst["nodes"]["harv"]["node_facts"]["final"] == "most of the way"
          and pst["nodes"]["harv"]["harvest"] == {"declared_status": None},
          "A2: a partial node ships node_facts beside harvest",
          repr(pst["nodes"]["harv"])[:200])
    check(pst["status"] == "done" and pst["next"] == [],
          "partial closes the run: done, next empty", json.dumps(pst.get("next")))

    # ---------- fixture H: held human gate ------------------------------------
    mk("sn-held", [fa, {"id": "approve", "type": "gate", "after": ["solo"],
                        "question": "publish?", "options": ["yes", "no"]}],
       records={"solo": {"status": "done", "output": {"ok": True}, "attempts": 1}})
    ph = door.act_status({"run_id": "sn-held"}); payloads["held"] = ph
    check(ph["status"] == "held", "held fixture: run status held", str(ph)[:160])
    n0 = (ph.get("next") or [{}])[0]
    check(n0.get("action") == "release" and n0.get("gate_id") == "approve"
          and n0.get("options") == ["yes", "no"],
          "A3 ACCEPT: held next[0] is release on the held gate with options", json.dumps(ph.get("next")))
    wh = door.act_wait({"run_id": "sn-held", "timeout": 0})
    check(wh.get("next") == ph.get("next"), "wait on a held run answers the same next", "")

    # ---------- fixture D: done run ---------------------------------------------
    mk("sn-done", [fa, {"id": "second", "type": "agent", "after": ["solo"]}],
       records={"solo": {"status": "done", "output": {"ok": True}, "attempts": 1},
                "second": {"status": "done", "output": {"ok": True}, "attempts": 1}},
       events=[{"event": "node.done", "node": "second"}])
    pd = door.act_status({"run_id": "sn-done"}); payloads["done"] = pd
    check(pd["status"] == "done" and pd["next"] == [], "A3 ACCEPT: a done run gives next == []", json.dumps(pd)[:200])
    wd = door.act_wait({"run_id": "sn-done", "timeout": 0})
    check(wd["next"] == [], "wait on a done run: next == []", "")

    # ---------- fixture S: stopped run ------------------------------------------
    mk("sn-stopped", [fa, fb], records={"solo": {"status": "done", "output": {}, "attempts": 1}},
       events=[{"event": "node.done", "node": "solo"}, {"event": "run.stopped"}])
    ps = door.act_status({"run_id": "sn-stopped"}); payloads["stopped"] = ps
    check(ps["status"] == "stopped" and ps["next"] == [], "A3: a stopped run gives next == []", json.dumps(ps)[:200])

    # ---------- fixture P2: fresh pending run ------------------------------------
    mk("sn-pending", [fa, fb])
    ppd = door.act_status({"run_id": "sn-pending"}); payloads["pending"] = ppd
    check(ppd["status"] == "pending" and ppd["next"] == [{"action": "wait"}], "A3: pending run says wait", json.dumps(ppd)[:200])

    # ---------- fixture I: interrupted (work left, no runner, events exist) ------
    mk("sn-int", [fa, fb], records={"solo": {"status": "done", "output": {}, "attempts": 1}},
       events=[{"event": "node.done", "node": "solo"}])
    pi = door.act_status({"run_id": "sn-int"}); payloads["interrupted"] = pi
    check(pi["status"] == "interrupted" and pi["next"] == [{"action": "wait"}], "A3: interrupted run says wait", json.dumps(pi.get("next")))

    # ---------- fixture C: crashed runner -> failed with no failed node ----------
    graph_c_nodes = [fa, fb]
    mk("sn-crash", graph_c_nodes,
       records={"solo": {"status": "done", "output": {}, "attempts": 1}},
       events=[{"event": "node.done", "node": "solo"}],
       runner_exit={"reason": "crashed: fatal in runner",
                    "graph_fingerprint": wfcommon.graph_fingerprint({"name": "sn-crash", "nodes": graph_c_nodes}), "fp_rule_version": wfcommon.FP_RULE_VERSION})
    pc = door.act_status({"run_id": "sn-crash"}); payloads["crashed"] = pc
    check(pc["status"] == "failed" and pc["next"] == [{"action": "amend", "node": None, "error_class": "unknown"}],
          "A3: a crashed-runner failure still says amend (never silence)",
          json.dumps(pc.get("next")))

    # ---------- O1 (critic fix): every status AND wait payload carries card ------
    for rid in ("sn-fail", "sn-partial", "sn-held", "sn-done", "sn-stopped", "sn-pending", "sn-int", "sn-crash"):
        s = door.act_status({"run_id": rid})
        w = door.act_wait({"run_id": rid, "timeout": 0})
        check(s.get("card") == CARD(rid), f"O1: status payload of {rid} carries the card", repr(s.get("card")))
        check(w.get("card") == CARD(rid), f"O1: wait payload of {rid} carries the card", repr(w.get("card")))
    check(pd["card"] == '::workflow{id="sn-done"}',
          "O1: card is exactly ::workflow{id=\"<run_id>\"}", repr(pd["card"]))

    # ---------- read-model lock: next never contradicts the payload --------------
    def lock(payload):
        st, nodes = payload["status"], payload["nodes"]
        for row in payload.get("next", []):
            a = row["action"]
            if a == "amend":
                assert row["node"] is None or nodes[row["node"]]["status"] == "failed", (st, row)
            elif a == "release":
                assert st == "held" and payload["gate"]["id"] == row["gate_id"], (st, row)
            elif a == "wait":
                assert st in ("running", "pending", "interrupted"), (st, row)
            else:
                raise AssertionError(row)
        if st in ("done", "stopped"):
            assert payload.get("next") == [], (st, payload.get("next"))
    for tag, p in payloads.items():
        lock(p)
    check(True, "read-model lock: no next row contradicts the status/nodes it rides with",
          json.dumps({k: v.get("next") for k, v in payloads.items()})[:200])

    # ---------- derive-only: no state, no next -----------------------------------
    bad = door.act_status({"run_id": "sn-does-not-exist"})
    check("error" in bad and "next" not in bad,
          "unreadable run: error, no next, never a guess", json.dumps(bad)[:120])
finally:
    shutil.rmtree(HOME, ignore_errors=True)

print("ALL PASS" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
