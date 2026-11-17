"""when-ref ancestry (2026-09-30): a gate `when` reading `out.<node>.<path>` must
reference a node in the gate's `after` ANCESTRY — the law `inputs` (head not in
ancestry → reject) and `fanout.items_from` (head not in `after` → reject) already
enforce at submit. Before the fix, `when_expr_ok` is parse-only (sentinel operands,
by design), so a non-ancestor head — a parallel sibling, a typo, a node that will
never commit before this gate fires — validates clean, then at fire time resolves
to None: the comparison is False and the gate silently SKIPS (`on_skip` default
prune ⇒ dead branch) or holds, depending on whether the unrelated node happened to
commit first. Stdlib only, no spawn, no network.
"""
import os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
os.environ.setdefault("DUCKWORK_HOME", str(HERE / ".suite-home"))
sys.path.insert(0, str(BUILD))
import wfcommon  # noqa: E402

V = wfcommon.validate_graph_errors
fails = []
def check(cond, msg, detail=""):
    print(("PASS " if cond else "FAIL ") + msg + (f"  << {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(msg)

# 1. the repro: gate_x's `when` reads a PARALLEL SIBLING (producer_b is not in its
#    ancestry — only producer_a is). Pre-fix: validates clean for gate_x.
repro = [{"id": "producer_a", "type": "agent", "goal": "x"},
         {"id": "producer_b", "type": "agent", "goal": "x"},
         {"id": "gate_x", "type": "gate", "after": ["producer_a"], "question": "q",
          "when": "out.producer_b.verdict == 'go'"}]
errs = V(repro)
check(any(e["node"] == "gate_x" and e["field"] == "when" for e in errs),
      "non-ancestor (sibling) when-head rejected at submit", str(errs))

# 2. the SAME ref via inputs errors today (the precedent this fix extends) — unchanged
inp = [{"id": "producer_a", "type": "agent", "goal": "x"},
       {"id": "producer_b", "type": "agent", "goal": "x"},
       {"id": "use", "type": "agent", "after": ["producer_a"], "goal": "y",
        "inputs": ["producer_b.verdict"]}]
check(any(e["node"] == "use" and "ancestry" in e["msg"] for e in V(inp)),
      "inputs non-ancestor head still rejected (precedent intact)", str(V(inp)))

# 3. a head that does not exist at all
ghost = [{"id": "producer_a", "type": "agent", "goal": "x"},
         {"id": "gate_x", "type": "gate", "after": ["producer_a"], "question": "q",
          "when": "out.nonexistent.zzz == 1"}]
errs = V(ghost)
check(any(e["node"] == "gate_x" and e["field"] == "when" for e in errs),
      "nonexistent when-head rejected at submit", str(errs))

# 4. self-reference is not a strict ancestor (mirrors the inputs rule)
self_ref = [{"id": "g", "type": "gate", "after": [], "question": "q",
             "when": "out.g.answer == 'yes'"}]
errs = V(self_ref)
check(any(e["node"] == "g" and e["field"] == "when" for e in errs),
      "self-referencing when-head rejected at submit", str(errs))

# 5. direct after: accepted, zero errors, byte-identical to pre-fix behaviour
direct = [{"id": "a", "type": "agent", "goal": "x"},
          {"id": "g", "type": "gate", "after": ["a"], "question": "q",
           "when": "out.a.verdict == 'go'", "on_skip": "prune"}]
check(V(direct) == [], "direct-after when-head accepted", str(V(direct)))

# 6. transitive ancestor: accepted (ancestry, not just direct `after` — the same
#    closure walk inputs uses)
trans = [{"id": "a", "type": "agent", "goal": "x"},
         {"id": "b", "type": "agent", "after": ["a"], "goal": "y"},
         {"id": "g", "type": "gate", "after": ["b"], "question": "q",
          "when": "out.a.verdict == 'go'"}]
check(V(trans) == [], "transitive-ancestor when-head accepted", str(V(trans)))

# 7. multiple heads in one expr: bad one named, good one not flagged; every
#    offending ref's head appears in its message
multi = [{"id": "a", "type": "agent", "goal": "x"},
         {"id": "sib", "type": "agent", "goal": "x"},
         {"id": "g", "type": "gate", "after": ["a"], "question": "q",
          "when": "out.a.ok == True or out.sib.ok == True"}]
errs = V(multi)
when_errs = [e for e in errs if e["node"] == "g" and e["field"] == "when"]
check(len(when_errs) == 1 and "sib" in when_errs[0]["msg"] and "'a'" not in when_errs[0]["msg"],
      "per-head error names only the offender", str(errs))

# 8. literal-only `when` carries no refs: accepted (test_v5_fixes S1b shape intact)
lit = [{"id": "g", "type": "gate", "after": [], "question": "q", "when": "1 > 'z'"}]
check(V(lit) == [], "literal-only when accepted", str(V(lit)))

# 9. parse errors keep when_expr_ok's message verbatim — no ancestry noise layered on
badparse = [{"id": "a", "type": "agent", "goal": "x"},
            {"id": "g", "type": "gate", "after": ["a"], "question": "q",
             "when": "out.judge.verdict == "}]
errs = V(badparse)
check(len(errs) == 1 and errs[0]["field"] == "when"
      and errs[0]["msg"] == wfcommon.when_expr_ok("out.judge.verdict == "),
      "malformed when reports the syntax error only", str(errs))

# 10. the agent-`when` rule (closed key set) owns agents untouched
agent_when = [{"id": "a", "type": "agent", "goal": "x", "when": "out.a.ok"}]
errs = V(agent_when)
check([e["field"] for e in errs] == ["when"] and "only gate" in errs[0]["msg"],
      "agent when still rejected by the closed-key rule alone", str(errs))

print(f"\nRESULT: {'ALL PASS' if not fails else str(len(fails)) + ' FAIL'}")
raise SystemExit(1 if fails else 0)
