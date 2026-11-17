#!/usr/bin/env python3
"""error-class closed set — ERROR_CLASSES is the closed set AGENTS.md cites; it must actually be
EXHAUSTIVE over committed classes.

Blind spot (PR #155 deep review, first-read P1): the runner commits
error_class="forbidden_model" (seat floor / policy, wf.py ~126/3624) and
error_class="precondition" (unmet input deps, wf.py ~3745) on node.failed
records and events, but the frozenset omitted both members. The B1-class pin
(test_sprint101w2_B1-classes.py) only checks classes OBSERVED in a fake run
tree — a class whose path the fake never walks slips through silently. This
pin closes that gap statically: every error_class literal the source commits
must be a member.

Red-proof (run before the fix): FAILS with
  forbidden_model/precondition missing from ERROR_CLASSES; green after.
"""
import re, sys
sys.path.insert(0, ".")
import wf

fails = total = 0
def check(name, ok, detail=""):
    global fails, total
    total += 1
    print(("PASS " if ok else "FAIL ") + name + ((" :: " + detail[:220]) if detail and not ok else ""), flush=True)
    if not ok: fails += 1

src = open("wf.py").read()

# every statically-committed error class: error_class="X" / error_class: "X"
committed = set(re.findall(r"""error_class\s*[=:]\s*["']([a-z_]+)["']""", src))
check("scanner finds the known committed set (guards the scanner itself)",
      {"forbidden_model", "precondition", "incomplete_work", "quorum"} <= committed,
      f"scanner saw {sorted(committed)}")

missing = sorted(committed - set(wf.ERROR_CLASSES))
check("every committed error_class is a member of the closed set", not missing,
      f"missing from ERROR_CLASSES: {missing}")

# the two historically-missing classes, explicitly (a rename of either
# literal must trip the scanner check above)
check("forbidden_model is a member", "forbidden_model" in wf.ERROR_CLASSES)
check("precondition is a member", "precondition" in wf.ERROR_CLASSES)

# closed-set hygiene: members are lowercase tokens and ERROR_CLASSES stays a frozenset
check("ERROR_CLASSES is a frozenset of plain tokens",
      isinstance(wf.ERROR_CLASSES, frozenset)
      and all(re.fullmatch(r"[a-z0-9_]+", t) for t in wf.ERROR_CLASSES))

print(f"TOTAL {total - fails} PASS {fails} FAIL", flush=True)
raise SystemExit(1 if fails else 0)
