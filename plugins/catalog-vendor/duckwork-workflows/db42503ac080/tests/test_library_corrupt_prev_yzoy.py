#!/usr/bin/env python3
"""#146 item 1 (est-yzoy): corrupt-prev RETAIN PROTECTION — the whole invalid
image class, not just unparseable bytes.

75c9a9d fail-closed the jload-None case (`{not json`). The retain branch still
walks past every VALID-JSON-BUT-INVALID-SHAPE prev: library_entry returns the
{invalid: ...} shape, `prev.get("meta")` is absent, the branch concludes
"no previous envelope", and the save SUCCEEDS — collapsing the entry to bare
bytes and wiping tags/description exactly when the stored image is damaged.
Peer review (issue #146 item 1) called this out as the same wipe: corrupt JSON
OR ambiguous (envelope+bare). Law asserted here: if the prev file EXISTS and
library_entry says INVALID, a retain-needing save refuses (repair-or-delete),
the bytes stay untouched, and the documented escape hatch stays open — an
explicit save naming tags+description overwrites the damaged entry.
"""
import json, os, shutil, sys
from pathlib import Path
BUILD = Path(os.environ.get("WF_TEST_BUILD") or Path(__file__).parent)
HOME = BUILD / "home_yzoyprev"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
shutil.rmtree(HOME, ignore_errors=True)
sys.path.insert(0, str(BUILD))
import importlib.util
spec = importlib.util.spec_from_file_location("hw", str(BUILD.parent / "__init__.py"))
hw = importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)
import wf_test_isolation as iso; iso.install(hw)
os.environ["DUCKWORK_WF_DUCKWORK_BIN"] = str(BUILD / "fake")
def call(**a): return json.loads(hw.handle(a))
ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond

G = {"name": "Yzoy Prev", "nodes": [{"id": "a", "type": "agent", "goal": "go"}]}
call(action="save", graph=G, name="p", tags=["domain:net"], description="keep me")
P = hw.library_root() / "p.json"

def poison(body):
    raw = body if isinstance(body, str) else json.dumps(body)
    P.write_text(raw)
    return raw

def refuse(label, body, needle, tag):
    """Retain-needing save over a damaged image must fail closed with the
    typed reason and leave the bytes EXACTLY as poisoned."""
    raw = poison(body)
    r = call(action="save", graph=G, name="p")          # no tags/description -> retain branch
    check(label, "error" in r and needle in r["error"] and "retain" in r["error"],
          json.dumps(r)[:220])
    check(label.replace("fails closed", "bytes untouched") + f" ({tag})",
          P.read_text() == raw, "refused save mutated the damaged file")

# D1 ambiguous image: valid JSON carrying BOTH envelope (graph:) and bare (nodes:)
refuse("D1 ambiguous envelope+bare prev fails closed (no silent wipe)",
       {"meta": {"tags": ["domain:net"], "description": "keep me"},
        "graph": G, "nodes": G["nodes"]}, "ambiguous", "D1b")

# D2 neither-shape: parses as JSON, is neither a bare graph nor an envelope
refuse("D2 neither-shape prev fails closed (no silent wipe)",
       {"junk": 1}, "neither", "D2b")

# D3 envelope whose graph has an empty nodes[] list — library_entry invalid shape
refuse("D3 empty-nodes prev fails closed (no silent wipe)",
       {"meta": {"tags": ["domain:net"]}, "graph": {"name": "p", "nodes": []}},
       "no non-empty nodes", "D3b")

# D4 control (regression pin of the 75c9a9d law): unparseable bytes stay refused
refuse("D4 unparseable prev still fails closed", "{not json!!", "corrupt", "D4b")

# D5 escape hatch: an EXPLICIT save (tags + description named) over the damaged
# entry is the documented repair route — it must SUCCEED and rebuild the envelope.
poison({"junk": 1})
r = call(action="save", graph=G, name="p", tags=["domain:net"], description="rebuilt")
check("D5 explicit save over damaged entry is the repair route",
      r.get("saved") == "p", json.dumps(r)[:220])
_e = json.loads(P.read_text())
check("D5b the rebuilt entry is a clean envelope",
      _e.get("meta", {}).get("tags") == ["domain:net"]
      and _e.get("meta", {}).get("description") == "rebuilt" and "graph" in _e,
      json.dumps(_e)[:220])

# D6 control: a HEALTHY envelope prev still retains normally (no over-refusal)
r = call(action="save", graph=G, name="p")
check("D6 healthy prev retains normally", r.get("saved") == "p", json.dumps(r)[:220])
_e2 = json.loads(P.read_text())
check("D6b retained tags/description ride the new envelope",
      _e2.get("meta", {}).get("tags") == ["domain:net"]
      and _e2.get("meta", {}).get("description") == "rebuilt", json.dumps(_e2)[:220])

print("ALL PASS" if ok else "FAILURES PRESENT"); sys.exit(0 if ok else 1)
