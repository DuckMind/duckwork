"""L7 — A1 durable prompt file + A4 durable child work dir.

A1: the prompt as sent lives beside the spawn log (`logs/<id>[.<i>].a<n>.prompt.md`),
    is named by the spawn record's `prompt_path`, and `spawn_cmd` carries the real
    path (no `<prompt>` redaction, no temp file, no unlink).
A4: every child starts in <run>/work/<node>[.<i>]/ (absolute), stated in CONTRACT,
    and the node completes when the runner's own cwd (the plugin install dir) is
    renamed away mid-run — the child never inherits it.

Self-contained fake CLI (written to the temp dir): this lane must not touch the
shared tests/fake_duckwork.py. Plain script: exits non-zero on the first red.
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

FAILS = []


def check(name, cond, detail=None):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  ::  " + str(detail)[:400]))
    if not cond:
        FAILS.append(name)

# ---------- the fake child CLI ----------
# Modes (chosen by a marker in the prompt):
#   PRINTCWD -> commits {"cwd": os.getcwd()} and echoes the query-file path
#   otherwise -> commits {"result": "ok"}
FAKE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
q = ""
qp = args[args.index("--query-file") + 1] if "--query-file" in args else None
if qp:
    q = open(qp, encoding="utf-8").read()
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(q.splitlines()[0] if q else "" + "\n")
if qp:  # prove --query-file was actually readable at spawn time
    assert os.path.exists(qp), "query-file vanished before the child read it"
print("progress line", flush=True)
if "PRINTCWD" in q:
    print("```json\n" + json.dumps({"cwd": os.getcwd(), "query_file": qp}) + "\n```")
else:
    print("```json\n" + json.dumps({"result": "ok"}) + "\n```")
'''


def home_and_fakes(tmp):
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


def step(home, run_id, cwd, fake_log, expected="WORKFLOW_DONE"):
    env = dict(os.environ, DUCKWORK_HOME=str(home), WF_RUNS_ROOT=str(home / "workflows"), FAKE_LOG=str(fake_log))
    p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", run_id],
                       env=env, text=True, capture_output=True, timeout=90, cwd=str(cwd))
    out = p.stdout + p.stderr
    check(f"{run_id}: lifecycle {expected}", expected in out and p.returncode == 0, out[:300])
    return out


def main():
    # ---------------- A1: prompt beside the log, named by the record ----------------
    with tempfile.TemporaryDirectory(prefix="l7-prompt-") as t:
        tmp = Path(t)
        home, fake_bin = home_and_fakes(tmp)
        fake_log = tmp / "fake.log"
        graph = {"name": "a1", "nodes": [
            {"id": "parent", "type": "agent", "goal": "produce something"},
            {"id": "child", "type": "agent", "goal": "consume it", "after": ["parent"]}]}
        run = mk_run(home, "a1", graph, fake_bin)
        step(home, "a1", tmp, fake_log)
        pf = run / "logs" / "child.a0.prompt.md"
        check("A1 logs/child.a0.prompt.md exists next to the log",
              pf.exists() and (run / "logs" / "child.a0.log").exists(),
              sorted(p.name for p in (run / "logs").iterdir()))
        text = pf.read_text() if pf.exists() else ""
        check("A1 the prompt as sent carries ## Inputs from the parent",
              "## Inputs" in text, text[:200])
        check("A1 the CONTRACT sentence names the child's durable work dir",
              "durable" in text and str((run / "work" / "child").resolve()) in text, text[-400:])
        check("A1 prompt carries NO single-query repackaging instruction (catalog review 133387 ask 2)",
              all(s not in text for s in ("Single-query approvals", "write a script file in your work", "run it instead")), text[:400])
        check("A1 the absence holds for the first-wave child too",
              "Single-query approvals" not in (run / "logs" / "parent.a0.prompt.md").read_text())
        check("A1 approval advice removed from every child prompt, not just the fan-out",
              text.count("Single-query approvals") == 0, text)
        check("A1 advice is prompt-only, not graph data",
              "Single-query approvals" not in (run / "graph.json").read_text())
        rec = json.loads((run / "nodes" / "child.json").read_text())
        check("A1 record prompt_path names the file",
              rec.get("prompt_path") == str(pf), json.dumps(rec)[:200])
        sc = rec.get("spawn_cmd") or []
        check("A1 spawn_cmd is unredacted: --query-file IS the prompt file",
              "--query-file" in sc and sc[sc.index("--query-file") + 1] == str(pf),
              json.dumps(sc)[:260])
        check("A1 spawn_cmd holds no <prompt> literal and no .txt temp path",
              not any("<prompt>" in a for a in sc)
              and not any(a.endswith(".txt") for a in sc), json.dumps(sc)[:260])
        # the durable prompt survives the run: readable after the runner exits
        check("A1 prompt survives the run (no unlink class)",
              pf.exists() and pf.read_text() == text, "prompt vanished")

    # ---------------- A1b: per-attempt prompts are distinct files ----------------
    with tempfile.TemporaryDirectory(prefix="l7-attempt-") as t:
        tmp = Path(t)
        home, fake_bin = home_and_fakes(tmp)
        graph = {"name": "a1b", "nodes": [
            {"id": "solo", "type": "agent", "goal": "PRINTCWD and answer"}]}
        run = mk_run(home, "a1b", graph, fake_bin)
        step(home, "a1b", tmp, tmp / "fake.log")
        check("A1b attempt 0 prompt is a0 (naming rule shared with the log)",
              (run / "logs" / "solo.a0.prompt.md").exists()
              and (run / "logs" / "solo.a0.log").exists(),
              sorted(p.name for p in (run / "logs").iterdir()))
        # A4: the child's cwd IS the per-node durable work dir, absolute
        rec = json.loads((run / "nodes" / "solo.json").read_text())
        want = str((run / "work" / "solo").resolve())
        check("A4 child cwd == <run>/work/<node> (absolute)",
              rec.get("status") == "done" and (rec.get("output") or {}).get("cwd") == want,
              json.dumps(rec)[:300])
        check("A4 the child read --query-file at the same path the record names",
              (rec.get("output") or {}).get("query_file")
              == str(run / "logs" / "solo.a0.prompt.md"), json.dumps(rec)[:200])

    # ---------------- A4: node completes after the plugin dir is renamed --------
    # The door spawns the runner with cwd=<install dir> (__init__.py:136-138) and a
    # release copy replaces that dir mid-run: children must not care.
    with tempfile.TemporaryDirectory(prefix="l7-workdir-") as t:
        tmp = Path(t)
        home, _fake = home_and_fakes(tmp)
        install = tmp / "plugin-install"
        install.mkdir()
        for f in ("wf.py", "wfcommon.py"):
            (install / f).write_text((ROOT / f).read_text())
        fake_bin = install / "fake-duckwork"          # child lives IN the install dir
        fake_bin.write_text(FAKE)
        fake_bin.chmod(fake_bin.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        graph = {"name": "a4", "nodes": [{"id": "n1", "type": "agent", "goal": "PRINTCWD"}]}
        run = mk_run(home, "a4", graph, fake_bin)
        fake_log = tmp / "fake.log"
        env = dict(os.environ, DUCKWORK_HOME=str(home), WF_RUNS_ROOT=str(home / "workflows"), FAKE_LOG=str(fake_log))
        proc = subprocess.Popen([sys.executable, str(install / "wf.py"), "run", run.name],
                                env=env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, cwd=str(install))
        # wait until the child has spawned (fake writes FAKE_LOG at its start), then
        # replace the install dir out from under the live runner
        import time
        for _ in range(600):
            if fake_log.exists() and fake_log.read_text().strip():
                break
            time.sleep(0.05)
        else:
            check("A4 child spawned", False, "fake child never started")
        renamed = tmp / "plugin-install.replaced"
        os.rename(install, renamed)
        check("A4 install dir really gone mid-run", not install.exists(), str(install))
        out = proc.communicate(timeout=90)[0]
        check("A4 node completes after the install dir is renamed",
              "WORKFLOW_DONE a4" in out and proc.returncode == 0, out[:300])
        rec = json.loads((run / "nodes" / "n1.json").read_text())
        check("A4 child cwd stayed in the run dir, never the (now dead) install dir",
              (rec.get("output") or {}).get("cwd") == str((run / "work" / "n1").resolve()),
              json.dumps(rec)[:300])

    print(("" if not FAILS else "\nRED: ") + f"{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
