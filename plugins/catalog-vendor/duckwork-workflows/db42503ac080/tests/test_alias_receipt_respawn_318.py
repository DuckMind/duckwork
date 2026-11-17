#!/usr/bin/env python3
"""est-2ek.1.318 (ra-review observation 2 / zap marker 6068266252, verdict=changes):
the TARGET-shaped route_verified bake must not false-deny the same-alias respawn.

The #318 fix bakes the door's alive-proof as the resolved alias TARGET
(`route_verified: "example-provider/example-model-1"` for a node pinned to
model 'bigseat'), while the node DEF keeps the alias. The 641 pre-submit refusal
holds the lane's later spawns against that receipt — but its alias-map expansion
loops the seat config on `alias.lower() in (v, v_model)` ONLY: with a
TARGET-shaped receipt the key side never matches, so the alias NEVER enters the
candidate set. A same-alias ladder respawn / resume (same 'bigseat' ask, same
route) therefore dies BEFORE submit typed route_substitution_denied — a permfail
no retry ladder re-drives. CI's test_route_substitution_641.py B3 uses literals
only (ask == receipt verbatim) and is blind to this shape.

Law pinned here (RED at cc088db on legs A2, GREEN on the widened refusal loop):
  A1  spawn 1 of an alias-pinned node under the door's TARGET-shaped bake runs
      normally; the durable receipt names the TARGET (the #318 bake), and the
      seat stub billed the alias once.
  A2  the SAME-alias respawn (retry/resume — the identical def) is NOT refused:
      alias and receipt-TARGET are the same route seen through the seat's alias
      map. RED at head: DENIED before Popen, zero extra billing.
  B   the widening must not open the door: an alias whose TARGET differs from
      the receipt (alias-to-other-model substitution) stays DENIED, zero billing.
  C   a non-alias model substitution stays DENIED (the 641 core law intact).
  D   a spawn at the literal verified TARGET passes (the #25 identity law
      unchanged — ask == receipt verbatim).
Harness: the repo's own in-process run_child harness (test_11_runner_profile /
test_route_substitution_641.py shape) with a recording seat stub; the seat
config's alias map is injected at the runner seam (stdlib only, no network).
"""
import json, os, shutil, sys, tempfile, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wf  # noqa: E402

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " + label + ("  " + str(detail)[:400] if detail else "")))
    ok = ok and bool(cond)

HOME = Path(tempfile.mkdtemp(prefix="wf-aliasresp-"))
RUNS = HOME / "runs"
RUN = RUNS / "ralias"
(RUN / "nodes").mkdir(parents=True)
(RUN / "gates").mkdir()

# The recording seat stub: every spawn appends the -m/--provider it billed.
STUB = HOME / "duckwork_stub.py"
STUB.write_text(
    "#!/usr/bin/env python3\n"
    "import sys, os\n"
    "a = sys.argv[1:]\n"
    "m = a[a.index('-m') + 1] if '-m' in a else 'seat-default'\n"
    "p = a[a.index('--provider') + 1] if '--provider' in a else ''\n"
    "with open(os.environ['WFAR_LEDGER'], 'a') as f:\n"
    "    f.write(p + '/' + m + '\\n')\n"
    "print('```json\\n{\"result\": \"ok\"}\\n```')\n"
)
STUB.chmod(0o755)
LEDGER = HOME / "attempts.ledger"

os.environ["WFAR_LEDGER"] = str(LEDGER)
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(RUNS)

# The seat's alias map (neutral placeholders, scrub-safe): 'bigseat' resolves to
# the TARGET the door baked; 'otherseat' is a DIFFERENT route used for the
# substitution guards that must stay closed.
ALIAS_MAP = {"bigseat": "example-provider/example-model-1",
             "otherseat": "example-provider/example-model-2"}
wf._seat_alias_map = lambda home: dict(ALIAS_MAP)

ALIAS, TARGET = "bigseat", "example-provider/example-model-1"

node = {"id": "work", "type": "agent", "goal": "do the work",
        "model": ALIAS,                              # the house contract: def keeps the alias
        "route_verified": TARGET}                     # the #318 door bake: the TARGET the ping proved
(RUN / "graph.json").write_text(json.dumps({"name": "ralias", "nodes": [node]}))

meta = {"_run": RUN, "duckwork_bin": str(STUB), "_spawn_n": {},
        "_procs_lock": threading.Lock(), "_procs": {},
        "_stop": threading.Event(), "node_timeout": 15}

def attempts_for(route):
    try:
        return LEDGER.read_text().splitlines().count(route)
    except OSError:
        return 0

# ---- A1: first spawn under the TARGET-shaped bake runs; receipt names TARGET ----
r1 = wf.run_child(meta, node, {"work": node}, "do the work", "", None,
                  skey="wf:ralias:work")
check("A1 alias-pinned spawn under the TARGET bake: runs normally",
      r1.get("status") == "done", r1)
check("A1 the durable receipt names the TARGET the door proved (#318 bake shape)",
      (RUN / "route_receipts.json").is_file()
      and json.loads((RUN / "route_receipts.json").read_text()).get("work") == TARGET,
      (RUN / "route_receipts.json").read_text() if (RUN / "route_receipts.json").exists() else "missing")
check("A1 the seat stub billed the alias exactly once",
      attempts_for("/" + ALIAS) == 1, LEDGER.read_text() if LEDGER.exists() else "<no ledger>")

# ---- A2: the SAME-alias respawn (ladder retry / resume) is NOT refused ----------
# RED at cc088db: ask='bigseat' is held against receipt 'example-provider/example-model-1'
# with an alias map that expands only alias->verified, so the alias never reaches
# the candidate set and this spawn dies BEFORE Popen typed route_substitution_denied.
r2 = wf.run_child(meta, node, {"work": node}, "do the work", "", None,
                  skey="wf:ralias:work#2")
check("A2 same-alias respawn is NOT refused (receipt != alias lock) — RED at head",
      r2.get("status") == "done" and r2.get("error_class") != "route_substitution_denied",
      r2)
check("A2 the same-alias respawn billed the alias again (2 total)",
      attempts_for("/" + ALIAS) == 2, LEDGER.read_text())

# ---- B: alias-to-OTHER-route substitution stays DENIED (widening guard) ---------
b_node = dict(node, model="otherseat")
r3 = wf.run_child(meta, b_node, {"work": b_node}, "do the work", "", None,
                  skey="wf:ralias:work#3")
check("B substitution to a different alias (different TARGET): still DENIED",
      r3.get("status") == "failed" and r3.get("error_class") == "route_substitution_denied",
      r3)
check("B ZERO attempts against the substituted alias",
      attempts_for("/otherseat") == 0, LEDGER.read_text())

# ---- C: non-alias model substitution stays DENIED (the 641 core law intact) -----
c_node = dict(node, model="example-model-9")
r4 = wf.run_child(meta, c_node, {"work": c_node}, "do the work", "", None,
                  skey="wf:ralias:work#4")
check("C substitution to an unrelated model: still DENIED, zero attempts",
      r4.get("status") == "failed" and r4.get("error_class") == "route_substitution_denied"
      and attempts_for("/example-model-9") == 0, r4)

# ---- D: a spawn at the literal verified TARGET passes (#25 identity law) ---------
LEDGER.write_text("")                      # fresh ledger: D bills in isolation
d_node = dict(node, provider="example-provider", model="example-model-1")
# D changes the authored definition, not a queued spawn's route. Materialize
# that definition so the launch-instant staleness guard sees the same graph.
(RUN / "graph.json").write_text(json.dumps({"name": "ralias", "nodes": [d_node]}))
r5 = wf.run_child(meta, d_node, {"work": d_node}, "do the work", "", None,
                  skey="wf:ralias:work#5")
check("D spawn at the literal verified TARGET: NOT refused (full-route identity)",
      r5.get("status") == "done" and attempts_for("example-provider/example-model-1") == 1,
      r5)

shutil.rmtree(HOME, ignore_errors=True)
print("RESULT", "GREEN" if ok else "RED")
raise SystemExit(0 if ok else 1)
