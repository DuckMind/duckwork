"""Runner-owned, durable handoff for an external post-exit script.

The registration is data written by a node. The runner stopped dispatching this
at est-xwvu9 (mechanism stripped from the shipped build); `dispatch()` remains
exercised by tests and kept source-only. The external script must live outside the run tree.
The receipt records the runner PID and every launch attempt, never a child's claim.
"""
import json
import os
import plistlib
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REG = "post_exit_hook.json"
RECEIPT = "post_exit_hook_receipt.json"


def _atomic(path, data):
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _check(run, script):
    run = Path(run).resolve(strict=True)
    script = Path(script).resolve(strict=True)
    if not run.is_dir() or not script.is_file() or run == script or run in script.parents:
        raise ValueError("hook script must be a file outside the workflow run tree")
    if not script.is_absolute() or script.suffix != ".sh":
        raise ValueError("hook must be an absolute shell script")
    return run, script


def register(run, script, *args):
    """Called by the close node before returning; persists the runner's work order."""
    run, script = _check(run, script)
    if not all(isinstance(a, str) and "\x00" not in a for a in args):
        raise ValueError("hook argv must be strings")
    order = {"run_id": run.name, "script": str(script), "args": list(args)}
    p = run / REG
    if p.exists():
        if json.loads(p.read_text()) != order:
            raise ValueError("post-exit hook already registered with different arguments")
        return order
    _atomic(p, order)
    return order


def _live(script):
    d = script.parent
    try:
        state = (d / "state").read_text().strip()
        if state in {"all_done", "final_hold", "flip_failed", "snapshot_held", "snapshot_rolled_back"}:
            return True
    except OSError:
        pass
    try:
        pid = int((d / "tail.pid").read_text().strip())
        os.kill(pid, 0)
        return True
    except (ValueError, OSError):
        return False


def _detached(argv, log):
    """Double-fork into a new session after runner cleanup, not a runner child."""
    pid = os.fork()
    if pid:
        os.waitpid(pid, 0)
        return
    try:
        os.setsid()
        if os.fork():
            os._exit(0)
        fd = os.open(str(log), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        devnull = os.open(os.devnull, os.O_RDONLY)
        os.dup2(devnull, 0)
        os.dup2(fd, 1)
        os.dup2(fd, 2)
        os.execv(argv[0], argv)
    except BaseException:
        os._exit(127)


def dispatch(run, reason, *, launchctl="/bin/launchctl", poll_seconds=3):
    """Historically called by the admitted runner after exit verdict and child
cleanup; the runner no longer dispatches (est-xwvu9) — tests exercise it directly.

    A failed handoff is a durable RED receipt; it never converts a workflow's
    failed/held verdict into an install. Existing dispatch receipts are replay-safe.
    """
    run = Path(run)
    p = run / REG
    if not p.exists():
        return None
    receipt_path = run / RECEIPT
    if receipt_path.exists():
        old = json.loads(receipt_path.read_text())
        if old.get("state") == "dispatched":
            return old
    receipt = {"author": "workflow_runner", "runner_pid": os.getpid(),
               "run_id": run.name, "reason": reason,
               "at": datetime.now(timezone.utc).isoformat(), "attempts": []}
    def save(state):
        receipt["state"] = state
        _atomic(receipt_path, receipt)
        return receipt
    try:
        order = json.loads(p.read_text())
        if order.get("run_id") != run.name or not isinstance(order.get("args"), list):
            raise ValueError("wrong run ID or hook arguments")
        run, script = _check(run, order["script"])
        if not all(isinstance(a, str) and "\x00" not in a for a in order["args"]):
            raise ValueError("invalid hook arguments")
        if reason != "done":
            receipt["error"] = "runner did not complete"
            return save("held")
        argv = ["/bin/bash", str(script), *order["args"]]
        label = "cc.duckwork.workflow-post-exit-" + str(os.getpid())
        out = script.parent / "runner-hook.log"
        plist = script.parent / "runner-hook.plist"
        plist.write_bytes(plistlib.dumps({"Label": label, "ProgramArguments": argv,
                                           "StandardOutPath": str(out),
                                           "StandardErrorPath": str(out),
                                           "RunAtLoad": True}))
        attempts = [
            [launchctl, "submit", "-l", label, "-o", str(out), "-e", str(out), "--", *argv],
            [launchctl, "bootstrap", f"gui/{os.getuid()}", str(plist)],
            [launchctl, "load", "-w", str(plist)],
        ]
        for cmd in attempts:
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                rc = proc.returncode
                detail = (proc.stderr or proc.stdout)[-240:]
            except (OSError, subprocess.TimeoutExpired) as e:
                rc, detail = 99, str(e)[-240:]
            receipt["attempts"].append({"method": cmd[1], "rc": rc, "detail": detail})
            save("launching")
            if rc == 0:
                receipt["method"] = cmd[1]
                return save("dispatched")
        # All launchd paths failed: escape the runner process group. This path is
        # reached AFTER _runner_term_cleanup; registration remains durable on disk.
        _detached(argv, out)
        for _ in range(max(1, int(poll_seconds * 4))):
            if _live(script):
                receipt["method"] = "double_fork"
                return save("dispatched")
            time.sleep(0.25)
        receipt["error"] = "detached tail not proven live or terminal"
        return save("failed")
    except (OSError, ValueError, KeyError, TypeError) as e:
        receipt["error"] = f"{type(e).__name__}: {e}"
        return save("failed")


if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[1] != "register":
        sys.exit("usage: post_exit_hook.py register <run_dir> <script.sh> [args...]")
    print(json.dumps(register(sys.argv[2], sys.argv[3], *sys.argv[4:])))
