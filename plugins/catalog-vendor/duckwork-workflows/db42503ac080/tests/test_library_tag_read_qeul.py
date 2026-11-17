#!/usr/bin/env python3
"""est-qeul: the library tag READ path is canonical — pre-change API-written and
file-editor-written raw bytes cannot break the discovery readers.

The save API normalizes (lowercase-trim, dedupe, fail-closed grammar) but the
shared read model (wfcommon.library_entry) preserved meta.tags VERBATIM: the
1.1-era filter only dropped non-strings and whitespace-only tokens. A clean-base
save (before the save-side normalizer landed) accepted ["review","review"] and
["Review\\n"], so the estate shelf carries raw shapes that broke readers the
save API could never produce:
  Q1 the `library` row echo (and every reader) shows the raw stored list
  Q2 tag_vocab counts a raw duplicate TWICE for one entry (entry-count law)
  Q3 the newline row is unselectable even by passing its echoed token verbatim
     (the query side folds through the save grammar; the stored side never did)

The fix is ONE grammar: wfcommon.norm_tags is the single source; the door's
_norm_tags delegates to it, and library_entry folds every stored token through
the same function at read time (invalid-under-grammar tokens drop from the READ,
never error — quarantine is for whole-entry shape, F-2 #62).

Deterministic: scratch WF_RUNS_ROOT, stdlib only, no network, no estate shelf.
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_home = tempfile.mkdtemp(prefix="qeul-")
os.environ["WF_RUNS_ROOT"] = _home
os.environ.pop("DUCKWORK_WF_RUN_DIR", None)

_spec = importlib.util.spec_from_file_location("wfcommon_qeul", ROOT / "wfcommon.py")
wc = importlib.util.module_from_spec(_spec)
sys.modules["wfcommon_qeul"] = wc
_spec.loader.exec_module(wc)

_ispec = importlib.util.spec_from_file_location("door_qeul", ROOT / "__init__.py")
door = importlib.util.module_from_spec(_ispec)
sys.modules["door_qeul"] = door
_ispec.loader.exec_module(door)

LIB = Path(_home) / "library"
GRAPH = {"nodes": [{"id": "a", "kind": "solo"}]}

def write_entry(name, tags):
    LIB.mkdir(parents=True, exist_ok=True)
    (LIB / f"{name}.json").write_text(
        json.dumps({"meta": {"description": "d", "tags": tags}, "graph": GRAPH}))

# raw shapes exactly as a clean-base save API wrote them (PR136 evidence)
write_entry("dup", ["review", "review"])
write_entry("nl", ["Review\n"])

FAILS = []
CHECKS = []

def check(label, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + label + (("  -- " + str(detail)[:160]) if not cond and detail else ""))
    CHECKS.append(label)
    if not cond:
        FAILS.append(label)

# ---- Q1: the reader echo is canonical ----
rows = door._library_rows()[0]
by = {r["name"]: (r.get("tags") or []) for r in rows}
check("Q1 duplicate stored raw echoes ONE token", by.get("dup") == ["review"], by.get("dup"))
check("Q1 newline/uppercase stored raw echoes canonical", by.get("nl") == ["review"], by.get("nl"))

# ---- Q2: tag_vocab is an ENTRY count, duplicates never double-count ----
vocab = door.act_library({}).get("tag_vocab", {})
check("Q2 tag_vocab counts review as 2 entries (not 3 tokens)", vocab.get("review") == 2, vocab)

# ---- Q3: selection consistency across spellings ----
for label, q in (("canonical", ["review"]),
                 ("echoed verbatim (raw newline)", ["Review\n"]),
                 ("uppercase", ["REVIEW"])):
    names = sorted(r["name"] for r in door.act_library({"tags": q}).get("library", []))
    check(f"Q3 filter {label} selects both rows", names == ["dup", "nl"], names)

# ---- Q4: the READ fold uses the SAME grammar the save enforces (no drift) ----
# facet rules ride the read: unknown facet drops, valid facet canonicalizes.
write_entry("facets", ["task:x", "Repo:duckwork-workflows"])
rows = door._library_rows()[0]
fac = next(r["tags"] for r in rows if r["name"] == "facets")
check("Q4 unknown-facet token drops from the read", "task:x" not in fac, fac)
check("Q4 valid facet canonicalizes (lowercase)", fac == ["repo:duckwork-workflows"], fac)

# ---- Q5: the deliberate erase (meta.tags: []) still reads as [] ----
write_entry("erased", [])
rows = door._library_rows()[0]
er = next(r["tags"] for r in rows if r["name"] == "erased")
check("Q5 meta.tags [] reads back as [] (erase state intact)", er == [], er)

# ---- Q6: junk elements drop from the read WITHOUT quarantining the entry ----
write_entry("junk", ["good", 5, None, "", " also-good \n"])
rows = door._library_rows()[0]
jk = next(r["tags"] for r in rows if r["name"] == "junk")
check("Q6 junk drops, valid tokens survive canonicalized", jk == ["good", "also-good"], jk)

print("TOTAL", len(CHECKS), "FAIL", len(FAILS))
sys.exit(1 if FAILS else 0)
