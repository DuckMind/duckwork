#!/usr/bin/env python3
"""Core-10 exchange-run regression: the leaf verifies by RE-READING its committed
## Inputs, never from chat memory, and the file itself stays byte-portable.

The teaching pair: an echo commits a constant token (zero spawns, zero tokens); the
courier copies it as pure data from its declared input; the leaf re-reads BOTH
committed records from its own ## Inputs section and reports the verdict of a
character-for-character comparison. The save/library/replay-skip/fingerprint proofs
live in the author receipt — node prose must never ask a child to prove them, and
the leaf must never be told to assume what a committed record holds.

Regression laws asserted on the committed bytes:
- hand-off law: prepare declares inputs:["manifest.token"] and a schema that
  requires the carried token; its goal forbids exploration and demands a
  character-for-character copy.
- re-read law: verify declares inputs:["manifest","prepare"], its goal demands the
  comparison be made FROM the ## Inputs blocks (never from memory), and its schema
  teeth are {token, byte_equal, input_labels, notes} — byte_equal is required, so a
  leaf that skips the check fails contract instead of silently passing.
- run-dir legibility: the leaf's notes field carries the run-dir layout law, naming
  nodes/<id>.json, run.json and runner_exit.json as the engine's records, so a cold
  reader learns the run-dir from the file itself.
- model-naming law: no `model` field anywhere in the graph and no vendor model id
  appears in the file; children ride seat defaults (seat-fast / judge are prose
  role names only).
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import wfcommon  # noqa: E402

RAW = (ROOT / "examples" / "basics" / "exchange-run.workflow.json").read_text(encoding="utf-8")
g = json.loads(RAW)
nodes = {n["id"]: n for n in g["nodes"]}

TOKEN = "exchange-roundtrip-v1"

ok = 0
def check(cond, msg, detail=""):
    global ok
    assert cond, f"{msg}" + (f"  << {detail}" if detail and cond is not True else "")
    ok += 1

# --- grammar: the shared validator stays clean on the committed bytes
check(g.get("grammar") == "wf/1", "grammar is wf/1")
check(g.get("name") == "exchange-run", "graph name matches the file stem")
check(wfcommon.validate_graph_errors(g["nodes"]) == [], "shared validator clean",
      str(wfcommon.validate_graph_errors(g["nodes"])))

# --- echo transport: the token is committed by the engine, not typed by a model
man = nodes["manifest"]
check(man["type"] == "echo", "manifest is an echo node (zero spawns, zero tokens)")
check(man["output"].get("token") == TOKEN, "manifest commits the token VERBATIM")
check("after" not in man and "inputs" not in man, "the echo is the root: no after, no inputs")

# --- courier hand-off law: declared input + schema teeth + data-only directive
pre = nodes["prepare"]
check(pre["type"] == "agent" and pre["after"] == ["manifest"], "prepare runs after the echo")
check(pre.get("inputs") == ["manifest.token"],
      "prepare declares the dotted input manifest.token (the only source of truth)")
check("character-for-character" in pre["goal"], "courier goal demands a verbatim copy")
check("STRICTLY as data" in pre["goal"], "courier goal binds the payload as data, not reasoning")
check("Do NOT explore" in pre["goal"], "courier goal forbids exploration")
check("token" in pre.get("schema", {}).get("required", []),
      "prepare schema makes the carried token required")

# --- leaf re-read law: proof from ## Inputs, never from memory
ver = nodes["verify"]
check(ver["after"] == ["prepare"], "verify runs after the courier")
check(ver.get("inputs") == ["manifest", "prepare"],
      "verify declares BOTH committed records as inputs")
check("## Inputs" in ver["goal"], "verify must prove from its ## Inputs section")
check("never from memory" in ver["goal"], "verify is forbidden from proving via chat memory")
check("Do not use any tool" in ver["goal"],
      "verify is told not to explore: it reads its prompt and answers once")
req = ver.get("schema", {}).get("required", [])
for f in ("token", "byte_equal", "input_labels", "notes"):
    check(f in req, f"verify schema requires {f}")

# --- run-dir legibility law: the leaf's notes carry WHERE the engine keeps its facts
notes = ver["schema"]["properties"]["notes"]
goal = ver["goal"]
check("nodes/<id>.json" in goal, "leaf must name nodes/<id>.json as the per-node committed record")
check("run.json" in goal and "runner_exit.json" in goal,
      "leaf must name run.json and runner_exit.json as run-level records")
check(isinstance(notes.get("type"), str) and notes["type"] == "string",
      "notes is a plain string field (one-sentence layout law, no prose drift)")

# --- model-naming law: role words are prose only; no model field, no vendor id
def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield path, k
            yield from walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")
check(not any(k == "model" for _, k in walk(g)),
      "no model field anywhere: every child rides the seat default")
# The ban is NOT hand-copied here: the template must pass the peer-agreed committed
# scrub list (scripts/scrub-list.txt, Core-10 contract) end to end — hosts, LAN IPs,
# snowflakes, estate vocabulary, model aliases. Binding to the contract file keeps
# this guard honest when the peer list grows and keeps no banned token in this file.
_scrub_lines = [ln.strip() for ln in
                (ROOT / "scripts" / "scrub-list.txt").read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
scrub_hits = [ln for ln in _scrub_lines if re.search(ln, RAW, re.I)]
check(_scrub_lines and not scrub_hits,
      "template bytes match ZERO lines of the committed scrub list", ";".join(scrub_hits))

print(f"test_example_exchange_run: {ok} checks PASS")
