#!/usr/bin/env python3
"""#37 lane hygiene — the RED-by-checkout ban rides the machine build-lane preamble
(prompt-side only, modeled on _resume_preamble) and is DEF-HASH-NEUTRAL.

Drives the real runner (`wf.py run <id>`) under a temp DUCKWORK_HOME with a
self-contained fake child CLI (the test_prompt_workdir shape) and asserts:
  - a `shape: "build"` node's spawned prompt file carries the preamble block, and
    so does a `repo:` lane node (the 64c6772b surface), solo AND fan-out items;
  - an undeclared node (no shape, no repo — the golden-solo law) gets NO block and
    its prompt bytes are exactly the pre-#37 composition;
  - the preamble precedes the goal (the child reads the law before the task);
  - the tokens are ABSENT from graph.json, nodes/*.json and run.json (the def hash
    covers graph.json bytes only; the machine preamble never leaks into a record);
  - efp() of the node def is identical whether or not the block renders;
  - the block composes WITH the resume preamble on a bounded resume (unit-level:
    run_child is the one seam; both preambles are prompt-side).
Plain script, no pytest: exits non-zero on the first red.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import wf  # noqa: E402
import wfcommon  # noqa: E402

FAILS = []


def check(name, cond, detail=None):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  ::  " + str(detail)[:600]))
    if not cond:
        FAILS.append(name)


FAKE = r'''#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
q = open(args[args.index("--query-file") + 1], encoding="utf-8").read() if "--query-file" in args else ""
if "LIST:" in q:
    print("```json\n" + json.dumps({"result": ["x", "y"]}) + "\n```")
else:
    print("```json\n" + json.dumps({"result": "ok"}) + "\n```")
'''

# the pre-#37 tokens a leak would carry (a subset is enough: any one of these in a
# record file is the bug)
TOKENS = ("Lane hygiene (machine preamble)", "git worktree add --detach", "lane_recover.py",
          "RED discipline", "git stash push", "curl -X POST /-/reload")


def home_and_fake(tmp):
    home = tmp / "home"
    home.mkdir(parents=True)
    fake_bin = tmp / "fake-duckwork"
    fake_bin.write_text(FAKE)
    fake_bin.chmod(fake_bin.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return home, fake_bin


def mk_run(home, name, graph, fake_bin):
    run = home / "workflows" / name
    (run / "nodes").mkdir(parents=True)
    (run / "gates").mkdir()
    (run / "graph.json").write_text(json.dumps(graph))
    (run / "run.json").write_text(json.dumps({"duckwork_bin": str(fake_bin), "concurrency": 4}))
    return run


def step(home, run_id, cwd):
    env = dict(os.environ, DUCKWORK_HOME=str(home), WF_RUNS_ROOT=str(home / "workflows"))
    env.pop("WF_RUNS_ROOT", None)
    p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                       env=env, text=True, capture_output=True, timeout=120, cwd=str(cwd))
    out = p.stdout + p.stderr
    check(f"{run_id}: lifecycle WORKFLOW_DONE", "WORKFLOW_DONE" in out and p.returncode == 0, out[:400])
    return out


def leaks(run):
    """Every (file, token) pair where a preamble token appears in a record file."""
    hits = []
    for p in [run / "graph.json", run / "run.json"] + sorted((run / "nodes").glob("*.json")):
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for t in TOKENS:
            if t in text:
                hits.append((p.name, t))
    return hits


def main():
    lane_git = None
    with tempfile.TemporaryDirectory(prefix="lane37-preamble-") as t:
        tmp = Path(t)
        home, fake_bin = home_and_fake(tmp)
        lane_git = tmp / "lane"
        lane_git.mkdir()
        subprocess.run(["git", "-C", str(lane_git), "init", "-q"], check=True)
        (lane_git / "tracked.txt").write_text("base\n")
        subprocess.run(["git", "-C", str(lane_git), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(lane_git), "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-q", "-m", "base"], check=True)

        graph = {"name": "lh", "nodes": [
            {"id": "plain", "type": "agent", "goal": "LIST: seed"},
            {"id": "build", "type": "agent", "goal": "implement it", "shape": "build", "after": ["plain"]},
            {"id": "lane", "type": "agent", "goal": "fix in the lane", "repo": str(lane_git), "after": ["plain"]},
            {"id": "review", "type": "agent", "goal": "review it", "shape": "review", "after": ["plain"]},
            {"id": "items", "type": "agent", "goal": "join", "shape": "build", "after": ["plain"],
             "fanout": {"items_from": "plain.result", "goal": "build item {item}"}},
        ]}
        run = mk_run(home, "lh", graph, fake_bin)
        step(home, "lh", tmp)

        def prompt(name):
            p = run / "logs" / f"{name}.a0.prompt.md"
            return p.read_text(encoding="utf-8") if p.exists() else ""

        pb, pl, pr, pp = prompt("build"), prompt("lane"), prompt("review"), prompt("plain")
        block = "\n".join(wf.LANE_HYGIENE_LINES)
        check("shape:build prompt carries the whole lane-hygiene block", block in pb, pb[:600])
        check("repo: lane prompt carries the block too (the 64c6772b surface)", block in pl, pl[:600])
        check("the block precedes the goal (law before task)",
              pb.find(wf.LANE_HYGIENE_TOKEN) < pb.find("implement it"), pb[:400])
        check("shape:review prompt has NO block", not any(t in pr for t in TOKENS), pr[:300])
        check("undeclared node prompt has NO block (golden-solo law)", not any(t in pp for t in TOKENS), pp[:300])
        check("undeclared node prompt bytes == pre-#37 composition (goal first)",
              pp.startswith("LIST: seed\n\n" + wf.WORK_DIR_NOTE.split("{WORK_DIR}")[0]), pp[:200])
        for i in (0, 1):
            pi = prompt(f"items.{i}")
            check(f"fan-out item {i} prompt carries the block", block in pi, pi[:300])
        i0, i1 = prompt("items.0"), prompt("items.1")
        check("fan-out identity law holds from '## Inputs' onward",
              i0.split("## Inputs", 1)[1] == i1.split("## Inputs", 1)[1] if "## Inputs" in i0 and "## Inputs" in i1 else False)
        check("the ban names both checkout forms",
              "git checkout <base> -- <paths>" in pb and "git restore --source=<base>" in pb)
        # ---- est-2ek.1.66: the ONE verified reload form ----
        check("the reload law is in the block: exactly one line mentions /-/reload",
              sum("/-/reload" in ln for ln in wf.LANE_HYGIENE_LINES) == 1)
        reload_line = next(ln for ln in wf.LANE_HYGIENE_LINES if "/-/reload" in ln)
        check("the reload line bans the unverified curl-as-SIGHUP-equivalent",
              "curl -X POST /-/reload" in reload_line and "SIGHUP" in reload_line
              and "web.enable-lifecycle=false" in reload_line and "403" in reload_line,
              reload_line)
        check("the reload line commands ONE sanctioned form per deployment, verified live",
              "ONE sanctioned reload form" in reload_line and "verified live" in reload_line,
              reload_line)
        check("the reload law rides the build prompt", "/-/reload" in pb and reload_line in pb)
        check("the reload law rides the repo: lane prompt", reload_line in pl)
        check("the reload law rides every fan-out item prompt",
              all(reload_line in prompt(f"items.{i}") for i in (0, 1)))
        check("the reload law is ABSENT from the review-shape prompt", "/-/reload" not in pr, pr[:300])
        check("the reload law is ABSENT from the undeclared (golden-solo) prompt",
              "/-/reload" not in pp, pp[:300])
        check("the reload law sits after the gate token and before the goal",
              0 <= pb.find(wf.LANE_HYGIENE_TOKEN) < pb.find("/-/reload") < pb.find("implement it"),
              (pb.find(wf.LANE_HYGIENE_TOKEN), pb.find("/-/reload"), pb.find("implement it")))
        records_text = ((run / "graph.json").read_text()
                        + (run / "run.json").read_text()
                        + "\n".join(x.read_text() for x in (run / "nodes").glob("*.json")))
        check("the reload law never enters a record file", "/-/reload" not in records_text)
        check("the exit is named: scripts/lane_recover.py", "scripts/lane_recover.py" in pb)
        check("turn-budget line: commit BEFORE the cap", "BEFORE the cap" in pb)

        # ---- def-hash neutrality: no leak into any record ----
        hits = leaks(run)
        check("tokens ABSENT from graph.json, nodes/*.json and run.json", not hits, hits)
        recs = {p.name: json.loads(p.read_text()) for p in (run / "nodes").glob("*.json")}
        merged = {k: v for k, v in recs.items() if "." not in k[:-5]}   # items.<i>.json = spawn records
        check("all five nodes committed done", len(merged) == 5 and all(r.get("status") == "done" for r in merged.values()),
              {k: v.get("status") for k, v in recs.items()})
        check("the commit record names the prompt FILE (prompt_path), never its text",
              recs["build.json"].get("prompt_path", "").endswith("build.a0.prompt.md")
              and wf.LANE_HYGIENE_TOKEN not in json.dumps(recs["build.json"]),
              recs["build.json"])
        byid = {n["id"]: n for n in graph["nodes"]}
        check("efp() is a function of the graph def only (same with/without rendering)",
              wfcommon.efp(byid, byid["build"]) == recs["build.json"].get("efp"), recs["build.json"].get("efp"))
        check("graph.json bytes untouched by the run",
              json.loads((run / "graph.json").read_text()) == graph)

    # ---- unit: the composition seam and the shape predicate ----
    check("_lane_hygiene_preamble('' for undeclared)", wf._lane_hygiene_preamble({"id": "x"}) == "")
    check("_lane_hygiene_preamble(shape build) == the block", wf._lane_hygiene_preamble({"id": "x", "shape": "build"}) == block)
    check("_lane_hygiene_preamble(repo) == the block", wf._lane_hygiene_preamble({"id": "x", "repo": "lane"}) == block)
    check("_lane_hygiene_preamble(shape recon) == ''", wf._lane_hygiene_preamble({"id": "x", "shape": "recon"}) == "")
    check("_is_build_lane honors an explicit empty repo as undeclared", not wf._is_build_lane({"repo": ""}))
    # the resume preamble still composes after it (bounded resume): drive run_child directly
    with tempfile.TemporaryDirectory(prefix="lane37-resume-") as t:
        tmp = Path(t)
        home, fake_bin = home_and_fake(tmp)
        graph = {"name": "rs", "nodes": [{"id": "b", "type": "agent", "goal": "again", "shape": "build"}]}
        run = mk_run(home, "rs", graph, fake_bin)
        import threading
        meta = {"_run": run, "duckwork_bin": str(fake_bin), "_stop": threading.Event(),
                "_procs": {}, "_procs_lock": threading.Lock(), "_spawn_n": {}, "_retries_left": 3}
        byid = {n["id"]: n for n in graph["nodes"]}
        try:
            r = wf.run_child(meta, byid["b"], byid, "again", "", None, resume_preamble="## Resume from a dead attempt (machine preamble)\nPrior attempt died: error_class=timeout")
        except Exception as e:   # the seam under test is the prompt file; a harness gap is reported, not hidden
            r = {"status": "exception", "error": repr(e)}
        pf = run / "logs" / "b.a0.prompt.md"
        text = pf.read_text() if pf.exists() else ""
        check("bounded resume: lane hygiene block, then the resume preamble, then the goal",
              text.find(wf.LANE_HYGIENE_TOKEN) < text.find("## Resume from a dead attempt") < text.find("again\n"),
              (r, text[:500]))
        check("bounded resume: exactly one lane-hygiene block", text.count(wf.LANE_HYGIENE_TOKEN) == 1)

    print(("ALL PASS" if not FAILS else f"FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
