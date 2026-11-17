"""fb 625a3241cfcc9dee — the child's advertised durable work dir is writable
under DUCKWORK_WRITE_SAFE_ROOT.

WORK_DIR_NOTE tells every agent child 'Your working directory {WORK_DIR} is
durable; write your artifact there first'. That dir is <run>/work/<node>[.<i>]
under $DUCKWORK_HOME/workflows/. When the runner's env carries a (non-empty)
DUCKWORK_WRITE_SAFE_ROOT, core denies writes outside it, so the runner must append
the child's OWN work dir (narrowest) to the child's value. Unset/empty = no
restriction in core: the runner must leave it exactly as inherited.

Cases: SET (inherited order kept, last entry == child's cwd), NARROW (never the
run dir, run/work, or HOME/workflows), UNSET (child sees None), EMPTY (child
sees '' or None), FAN-OUT (each item sees only its own <node>.<i>).

est-2ek.1.772: the same dir is also the child's terminal-tool default cwd. The
Duckwork terminal tool resolves its default from $TERMINAL_CWD, not the process cwd,
and a host-exported TERMINAL_CWD used to win — a `git clone` with no workdir landed
outside the node workspace. Cases: TERMINAL_CWD INHERITED (foreign value replaced),
TERMINAL_CWD UNSET (still pinned), TERMINAL_CWD FAN-OUT (each item its own dir).

Self-contained fake CLI (written to the temp dir): must not touch the shared
tests/fake_duckwork.py. Plain script: exit non-zero on any red.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS = []


def check(name, cond, detail=None):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  ::  " + str(detail)[:400]))
    if not cond:
        FAILS.append(name)


# The fake child appends one JSON line {safe_root, cwd, terminal_cwd} to FAKE_LOG, then commits.
FAKE = r'''#!/usr/bin/env python3
import json, os
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(json.dumps({"safe_root": os.environ.get("DUCKWORK_WRITE_SAFE_ROOT"),
                        "terminal_cwd": os.environ.get("TERMINAL_CWD"),
                        "cwd": os.getcwd()}) + "\n")
print("progress line", flush=True)
print("```json\n" + json.dumps({"result": "ok"}) + "\n```")
'''

UNSET = object()


def run_graph(tmp, name, graph, safe_root, terminal_cwd=UNSET):
    home = tmp / "home"
    home.mkdir(parents=True, exist_ok=True)
    fake_bin = tmp / "fake-duckwork"
    fake_bin.write_text(FAKE)
    fake_bin.chmod(fake_bin.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    run = home / "workflows" / name
    (run / "nodes").mkdir(parents=True)
    (run / "gates").mkdir()
    (run / "graph.json").write_text(json.dumps(graph))
    (run / "run.json").write_text(json.dumps({"duckwork_bin": str(fake_bin), "concurrency": 4}))
    fake_log = tmp / (name + ".fake.log")
    env = dict(os.environ, DUCKWORK_HOME=str(home), WF_RUNS_ROOT=str(home / "workflows"), FAKE_LOG=str(fake_log))
    env.pop("DUCKWORK_WRITE_SAFE_ROOT", None)
    env.pop("TERMINAL_CWD", None)
    if safe_root is not UNSET:
        env["DUCKWORK_WRITE_SAFE_ROOT"] = safe_root
    if terminal_cwd is not UNSET:
        env["TERMINAL_CWD"] = terminal_cwd
    p = subprocess.run([sys.executable, str(ROOT / "wf.py"), "run", name],
                       env=env, text=True, capture_output=True, timeout=90, cwd=str(tmp))
    out = p.stdout + p.stderr
    check(f"{name}: lifecycle WORKFLOW_DONE", "WORKFLOW_DONE" in out and p.returncode == 0, out[:300])
    seen = [json.loads(l) for l in fake_log.read_text().splitlines() if l.strip()] \
        if fake_log.exists() else []
    return home, run, seen


SOLO = {"name": "s", "nodes": [{"id": "recon", "type": "agent", "goal": "do it"}]}


def main():
    inherited = ["/x/a", "/x/b"]

    # ---------------- SET + NARROW ----------------
    with tempfile.TemporaryDirectory(prefix="sr-set-") as t:
        tmp = Path(t)
        home, run, seen = run_graph(tmp, "set", dict(SOLO, name="set"), os.pathsep.join(inherited))
        check("SET one child spawned", len(seen) == 1, seen)
        c = seen[0] if seen else {}
        sr = c.get("safe_root") or ""
        parts = sr.split(os.pathsep)
        want = str((run / "work" / "recon").resolve())
        check("SET inherited entries first, original order", parts[:2] == inherited, sr)
        check("SET last entry == child's own work dir", parts[-1] == want, sr)
        check("SET last entry == child's cwd", parts[-1] == c.get("cwd"), c)
        check("SET exactly one entry added", len(parts) == len(inherited) + 1, sr)
        forbidden = {str(p) for p in (run, run.resolve(), run / "work", (run / "work").resolve(),
                                      home / "workflows", (home / "workflows").resolve())}
        check("NARROW no entry is the run dir, run/work, or HOME/workflows",
              not (set(parts) & forbidden), sr)

    # ---------------- UNSET ----------------
    with tempfile.TemporaryDirectory(prefix="sr-unset-") as t:
        _h, _r, seen = run_graph(Path(t), "unset", dict(SOLO, name="unset"), UNSET)
        check("UNSET child spawned", len(seen) == 1, seen)
        check("UNSET child sees None (never newly restricted)",
              bool(seen) and seen[0].get("safe_root") is None, seen)

    # ---------------- EMPTY ----------------
    with tempfile.TemporaryDirectory(prefix="sr-empty-") as t:
        _h, _r, seen = run_graph(Path(t), "empty", dict(SOLO, name="empty"), "")
        check("EMPTY child spawned", len(seen) == 1, seen)
        check("EMPTY child sees '' or None (never the work dir alone)",
              bool(seen) and seen[0].get("safe_root") in ("", None), seen)

    # ---------------- FAN-OUT ----------------
    with tempfile.TemporaryDirectory(prefix="sr-fan-") as t:
        graph = {"name": "fan", "nodes": [{"id": "recon", "type": "agent",
                                           "fanout": {"items": ["alpha", "beta"],
                                                      "goal": "audit {item}"}}]}
        _h, run, seen = run_graph(Path(t), "fan", graph, os.pathsep.join(inherited))
        check("FAN-OUT two children spawned", len(seen) == 2, seen)
        wants = {str((run / "work" / f"recon.{i}").resolve()) for i in (0, 1)}
        got = set()
        for c in seen:
            parts = (c.get("safe_root") or "").split(os.pathsep)
            check(f"FAN-OUT {Path(c.get('cwd', '?')).name}: inherited first",
                  parts[:2] == inherited, c)
            check(f"FAN-OUT {Path(c.get('cwd', '?')).name}: last entry == own cwd, one added",
                  parts[-1] == c.get("cwd") and len(parts) == 3, c)
            check(f"FAN-OUT {Path(c.get('cwd', '?')).name}: no sibling dir allowed",
                  not (set(parts) & (wants - {c.get("cwd")})), c)
            got.add(parts[-1])
        check("FAN-OUT per-item dirs recon.0 / recon.1", got == wants, (got, wants))

    # ---------------- TERMINAL_CWD (est-2ek.1.772) ----------------
    with tempfile.TemporaryDirectory(prefix="tc-inh-") as t:
        tmp = Path(t)
        foreign = str(tmp / "host-default-cwd")
        _h, run, seen = run_graph(tmp, "tcinh", dict(SOLO, name="tcinh"), UNSET, terminal_cwd=foreign)
        check("TERMINAL_CWD INHERITED one child spawned", len(seen) == 1, seen)
        c = seen[0] if seen else {}
        want = str((run / "work" / "recon").resolve())
        check("TERMINAL_CWD INHERITED terminal default cwd == child's work dir",
              c.get("terminal_cwd") == want, (c, want))
        check("TERMINAL_CWD INHERITED terminal default cwd == process cwd",
              c.get("terminal_cwd") == c.get("cwd"), c)
        check("TERMINAL_CWD INHERITED foreign value not forwarded", c.get("terminal_cwd") != foreign, c)

    with tempfile.TemporaryDirectory(prefix="tc-unset-") as t:
        _h, run, seen = run_graph(Path(t), "tcunset", dict(SOLO, name="tcunset"), UNSET)
        check("TERMINAL_CWD UNSET one child spawned", len(seen) == 1, seen)
        c = seen[0] if seen else {}
        check("TERMINAL_CWD UNSET terminal default cwd == child's work dir",
              c.get("terminal_cwd") == str((run / "work" / "recon").resolve()), c)

    with tempfile.TemporaryDirectory(prefix="tc-fan-") as t:
        graph = {"name": "tcfan", "nodes": [{"id": "recon", "type": "agent",
                                             "fanout": {"items": ["alpha", "beta"],
                                                        "goal": "audit {item}"}}]}
        _h, run, seen = run_graph(Path(t), "tcfan", graph, UNSET,
                                  terminal_cwd=str(Path(t) / "host-default-cwd"))
        check("TERMINAL_CWD FAN-OUT two children spawned", len(seen) == 2, seen)
        wants = {str((run / "work" / f"recon.{i}").resolve()) for i in (0, 1)}
        check("TERMINAL_CWD FAN-OUT each item's terminal cwd is its own dir, no sibling",
              {c.get("terminal_cwd") for c in seen} == wants
              and all(c.get("terminal_cwd") == c.get("cwd") for c in seen), (seen, wants))

    print(("" if not FAILS else "\nRED: ") + f"{len(FAILS)} failure(s)")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
