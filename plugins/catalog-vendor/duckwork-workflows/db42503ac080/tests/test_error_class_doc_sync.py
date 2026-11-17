#!/usr/bin/env python3
"""Doc-side closed-set pin: AGENTS.md §3d must name EXACTLY wf.ERROR_CLASSES.

The est-vb65 lesson, one notch further. A previous pin made the frozenset
exhaustive over COMMITTED classes (a class whose code path a fake never walks
could not go unlisted); that pin lives in tests/test_error_classes_exhaustive_vb65.py.
But AGENTS.md §3d cites its backtick pipe-list as *the* closed set every
`node.failed` carries, and nothing pinned THAT to the code — adding a class to
the frozenset while forgetting the doc was buyable (observed at head e505158:
`malformed_turn` in code, zero doc hits outside generated files). This pin
closes the doc half of the same drift class: a rename or addition that does
not update the doc fails the build.

`unknown` is exempted from the pipe-list deliberately — §3d carries it in the
following prose as the harvest-time default, not in the pipe-list — so the
law asserted is: pipe-list ∪ {unknown} == ERROR_CLASSES, exactly, both ways.

grammar.md is NOT pinned: its only 'closed set' sentence is the fanout-key
law, and it has no error-class enumeration to drift (recorded here so the
next reader does not hunt for it).

Run: PYTHONPATH=/opt/duckwork /opt/duckwork/.venv/bin/python tests/test_error_class_doc_sync.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wf  # noqa: E402

fails = total = 0


def check(name, cond, detail=""):
    global fails, total
    total += 1
    print(("PASS " if cond else "FAIL " + name) + (f" :: {detail[:260]}" if detail and not cond else ""),
          flush=True)
    if not cond:
        fails += 1


doc = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
sec = doc.split("### 3d.", 1)
check("AGENTS.md has the §3d section", len(sec) == 2, "split anchor drifted")
body = sec[1].split("### 3", 1)[0] if len(sec) == 2 else ""

# the backtick pipe-list that FOLLOWS the `wf.py ERROR_CLASSES` citation —
# anchor there, not on any earlier pipe-list in the same section.
anchor = "ERROR_CLASSES`) — `"
ai = body.find(anchor)
check("§3d cites the code set with the anchored intro", ai >= 0, "anchor phrase drifted")
rest = body[ai + len(anchor):] if ai >= 0 else ""
m = re.match(r"([a-z0-9_]+(?:\s*\|\s*[a-z0-9_]+)*)`", rest)
check("the anchored backtick pipe-list parses", m is not None, "no pipe-list after the anchor")
raw = m.group(1) if m else ""
doc_list = [t.strip() for t in raw.split("|") if t.strip()]
doc_set = set(doc_list)

code_set = set(wf.ERROR_CLASSES)
check("pipe-list ∪ {unknown} == ERROR_CLASSES (nothing in code missing from the doc)",
      doc_set | {"unknown"} == code_set,
      f"in code, missing from doc: {sorted(code_set - doc_set - {'unknown'})}; "
      f"in doc, not in code: {sorted(doc_set - code_set)}")
check("pipe-list names no duplicate token", len(doc_list) == len(doc_set) if m else False,
      "a token is listed twice — the list is verbatim law, it must read clean")
check("pipe-list is sorted (release-time grep ergonomics)",
      doc_list == sorted(doc_list) if m else False,
      f"doc order: {doc_list}")

print(f"TOTAL {total - fails} PASS {fails} FAIL", flush=True)
raise SystemExit(1 if fails else 0)
