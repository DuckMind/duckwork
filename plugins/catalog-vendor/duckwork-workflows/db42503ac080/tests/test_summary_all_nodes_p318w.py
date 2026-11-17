"""est-p318w: summary.md must list EVERY node's status + output.

Repro of run 20261008-111700-ra-release-peer: prepare -> peer_review (verdict
'decision') -> peer_gate (when verdict == 'merge', on_skip: prune) -> publish.
The gate skips, publish (the only leaf) is pruned, the runner closes the run
`done` -- and finalize() rendered only leaf nodes whose status was done/partial,
so summary.md was the bare header line while nodes/*.json held real outputs.

Real runner + tests/fake (goal 'JSON:{...}' makes the fake emit that block)."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
FAKE = HERE / "fake"
RUNS = Path(os.environ.get("WF_RUNS_ROOT") or tempfile.mkdtemp(prefix="p318w-runs-"))
HOME = Path(tempfile.mkdtemp(prefix="p318w-home-"))
ENV = {**os.environ, "DUCKWORK_HOME": str(HOME), "WF_RUNS_ROOT": str(RUNS), "WF_DUCKWORK_BIN": str(FAKE),
       "PATH": f"{FAKE.parent}:{os.environ.get('PATH', '')}"}
for k in ("FAKE_MODE", "WF_RUN_ID", "WF_NODE_ID"):
    ENV.pop(k, None)
FAILS = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def agent(id, out, after=()):
    return {"id": id, "type": "agent", "after": list(after), "timeout": 30,
            "goal": "JSON:" + json.dumps(out)}


PREP = {"pr": 95, "pr_url": "https://example.invalid/pull/95", "base_green": True}
REVIEW = {"verdict": "decision", "why": "peer seat unavailable p318w"}
graph = [
    agent("prepare", PREP),
    agent("peer_review", REVIEW, ["prepare"]),
    {"id": "peer_gate", "type": "gate", "after": ["peer_review"],
     "when": "out.peer_review.verdict == 'merge'", "on_skip": "prune", "question": "merge?"},
    agent("publish", {"result": "shipped"}, ["peer_gate"]),
]

rid = "20990101-000000-p318w-peer"
r = RUNS / rid
if r.exists():
    shutil.rmtree(r)
for d in ("nodes", "gates", "logs"):
    (r / d).mkdir(parents=True)
(r / "graph.json").write_text(json.dumps({"name": "p318w-peer", "nodes": graph}))
(r / "run.json").write_text(json.dumps({"name": "p318w-peer", "duckwork_bin": str(FAKE), "concurrency": 4,
                                        "started": "2099-01-01T00:00:00+00:00", "owner": "test"}))

p = subprocess.run([sys.executable, str(PLUGIN / "wf.py"), "run", rid], env=ENV,
                   capture_output=True, text=True, timeout=300)
check("runner closes the run done", "WORKFLOW_DONE" in p.stdout, (p.stdout + p.stderr)[-400:])

recs = {n["id"]: json.loads((r / "nodes" / f"{n['id']}.json").read_text())
        for n in graph if (r / "nodes" / f"{n['id']}.json").exists()}
check("shape reproduced: prepare+peer_review done, gate+publish skipped",
      {k: v.get("status") for k, v in recs.items()}
      == {"prepare": "done", "peer_review": "done", "peer_gate": "skipped", "publish": "skipped"},
      str({k: v.get("status") for k, v in recs.items()}))

summary = (r / "summary.md").read_text() if (r / "summary.md").exists() else ""
print("--- summary.md ---\n" + summary + "--- end ---")
check("summary is more than the bare header line", len(summary.strip().splitlines()) > 1, repr(summary))
for nid, rec in recs.items():
    check(f"summary names node {nid} with its status {rec.get('status')}",
          f"## {nid} — {rec.get('status')}" in summary)
    out = rec.get("output")
    if out is not None:
        check(f"summary carries node {nid}'s output JSON",
              json.dumps(out, ensure_ascii=False, indent=2, default=str) in summary)
check("prepare's pr_url is readable from the summary", PREP["pr_url"] in summary)
check("peer_review's verdict is readable from the summary", '"verdict": "decision"' in summary)

shutil.rmtree(HOME, ignore_errors=True)
print("TOTAL FAIL", len(FAILS))
sys.exit(1 if FAILS else 0)
