#!/usr/bin/env python3
"""Stub duckwork_bin for test_runner_orphan_666 — the runner-death-orphan repro child.

The witnessed shape (est-2ek.1.666, fb-closeout 2026-10-04 15:32Z): a terminating
runner leaves its agent-node child running unsupervised. This stub reproduces it
faithfully: it prints a progress line (never a silent spawn), detaches a
grandchild into its OWN session (double-fork + setsid — the escape shape the
killpg of the child's group cannot reach), and the grandchild APPENDS a
heartbeat line every 0.2 s while it lives.

The child-side belt (est-2ek.1.666): BOTH the agent child and its detached
grandchild run wf.child_parent_watch() — they self-exit non-zero the instant
their runner is verifiably gone and no replacement runner holds the lane.
On base the helper does not exist: the belt is a no-op, the heartbeat advances
forever, and the test is RED. That is the point. (wf is imported ONCE, before
any thread/fork — the forked grandchild uses the inherited reference; forking
while another thread imports can hand the child a held import lock.)
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import wf as _wf
except Exception:
    _wf = None                                # base: no helper -> pure orphan (RED)

args = sys.argv[1:]
q = ""
if "--query-file" in args:
    try:
        q = open(args[args.index("--query-file") + 1]).read()
    except OSError:
        q = ""

HB = os.environ.get("FAKE_HB_666", os.devnull)
GC_LOG = os.environ.get("FAKE_GC_666", os.devnull)


def _belt():
    """Contract-following belt: never returns while the runner lives; hard-exits
    non-zero once the runner is verifiably gone and no replacement holds the lane."""
    watch = getattr(_wf, "child_parent_watch", None) if _wf else None
    if callable(watch):
        watch(interval=0.15)


def _detach_heartbeat():
    """Double-fork + setsid: the heartbeat writer escapes BOTH our process group
    and (once we exit) our session — the exact unsupervised-survivor shape."""
    pid = os.fork()
    if pid > 0:
        return
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    os.chdir("/")                             # never pin a cwd the test wipes mid-run
    # grandchild: independent session. Announce, then heartbeat until killed or
    # (on the branch) the parent-liveness belt cuts it.
    try:
        with open(GC_LOG, "a") as f:
            f.write(str(os.getpid()) + "\n")
            f.flush()
    except OSError:
        pass
    threading.Thread(target=_belt, daemon=True).start()
    n = 0
    while True:
        n += 1
        try:
            with open(HB, "a") as f:
                f.write(f"beat {n} pid={os.getpid()} t={time.time()}\n")
                f.flush()
        except OSError:
            pass
        time.sleep(0.2)


with open(os.environ.get("FAKE_LOG", os.devnull), "a") as f:
    f.write(str(os.getpid()) + "\n")
print("stub 666 child cooking", flush=True)   # log exists -> not a silent spawn
_detach_heartbeat()
threading.Thread(target=_belt, daemon=True).start()
time.sleep(float(os.environ.get("STUB_SLEEP", "120")))
item = ""
for line in (q or "").splitlines():
    if line.strip():
        item = line.strip()[:80]
        break
print("```json\n" + "{\"result\": \"done:" + item.replace('"', "'") + "\"}\n```")
sys.exit(0)
