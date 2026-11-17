#!/usr/bin/env python3
"""est-g2xx seat-semaphore driver fixture.

Usage: seat_acquire_driver.py <seats_dir> <name> <hold_s> <cap> [bounded_s]
       [abort_after_s] [hold_lock_s]

Acquires a global agent seat through wf._seat_acquire (the SAME entry the
runner's spawn seam uses), holds it hold_s seconds, releases, and prints one
JSON row to stdout:
  {"ok": true, "name", "acquired_after", "released_at", "waited_s"}
or on bounded-wait expiry / abort:
  {"ok": false, "error_class": "seat_wait", "waited_s"}
or (est-g255 P255-5) when process identity cannot be verified at all:
  {"ok": false, "error_class": "seat_unsupported", "waited_s", "ancestors",
   "tickets_left"}

est-g255 knobs (zap P255-2/P255-5 controls; additive, base-compatible):
  abort_after_s: the abort() predicate flips True after this many seconds —
    the same channel the stop watcher / fan-out cancel use at the spawn seam.
  hold_lock_s: a holder thread flocks <seats_dir>/.lock for this long BEFORE
    the acquire attempt — the stuck-lock shape (a slow lock holder must never
    make the advertised bounded wait unbounded).
  SEAT_NO_PROCFS=1 env: patch the product's /proc ppid channel to fail (the
    no-procfs platform); SEAT_NO_PROC_AT_ALL=1 additionally fails the ps
    fallback — the runner must then refuse typed, never silently deadlock.
  SEAT_SEED_ANCESTOR=1: pre-seed a holder ticket whose child pid is this
    process's parent (the nested-lending shape: a runner launched from inside
    a seat must LENT the ancestor ticket, not count it).
"""
import importlib.util
import inspect
import json, os, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_spec = importlib.util.spec_from_file_location("hw_g255_driver", ROOT / "wf.py")
wf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wf)

def _opt(v):
    return None if v is None or v == "-" else float(v)

seats_dir, name, hold_s, cap = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
bounded = _opt(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] != "-" else 30.0
abort_after = _opt(sys.argv[6]) if len(sys.argv) > 6 else None
hold_lock = _opt(sys.argv[7]) if len(sys.argv) > 7 else None

# no-procfs platform simulation (est-g255 P255-5): swap the product's module-
# level Path for one whose /proc rows cannot be read — the shape of a platform
# without procfs. 'full' additionally kills the ps fallback (no process-
# identity channel at all). Bites at base AND head (patches what the product
# resolves at call time).
_nps = os.environ.get("SEAT_FAKE_NOPROCS", "")
if _nps:
    import subprocess as _sp_mod
    class _NoProcPath(type(Path())):
        def read_text(self, *a, **k):
            if str(self).startswith("/proc/"):
                raise FileNotFoundError(2, "no procfs (simulated)")
            return super().read_text(*a, **k)
        def read_bytes(self):
            if str(self).startswith("/proc/"):
                raise FileNotFoundError(2, "no procfs (simulated)")
            return super().read_bytes()
    wf.Path = _NoProcPath
    if _nps == "full":
        _real_run = _sp_mod.run
        def _run_no_ps(*a, **k):
            argv0 = a[0] if a else k.get("args") or k.get("cmd")
            if isinstance(argv0, (list, tuple)) and argv0 and str(argv0[0]).endswith("ps"):
                raise OSError(2, "no ps (simulated)")
            return _real_run(*a, **k)
        wf.subprocess = type("sp", (), {"run": staticmethod(_run_no_ps),
                                        "PIPE": _sp_mod.PIPE,
                                        "DEVNULL": _sp_mod.DEVNULL})

# nested-lending probe: seed a holder ticket whose child pid is THIS process —
# a nested runner launched from inside a seat (the parent seat waits on us, so
# its ticket is LENT, not counted).
if os.environ.get("SEAT_SEED_ANCESTOR"):
    seats = Path(seats_dir)
    seats.mkdir(parents=True, exist_ok=True)
    (seats / "ancestor-holder.json").write_text(json.dumps(
        {"pid": os.getppid(), "child": os.getppid(), "name": "ancestor",
         "ts": round(time.time(), 3)}))

try:
    ancestors = wf._ancestors()
    ancestors = sorted(ancestors) if ancestors is not None else None
except TypeError:
    ancestors = "unprintable"

if hold_lock is not None:
    import fcntl
    Path(seats_dir).mkdir(parents=True, exist_ok=True)
    _holder_in = threading.Event()
    def _hold():
        fd = os.open(str(Path(seats_dir) / ".lock"), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)
        _holder_in.set()
        time.sleep(hold_lock)
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    threading.Thread(target=_hold, daemon=True).start()
    _holder_in.wait(5)                     # the holder holds before we try

abort_at = time.time() + abort_after if abort_after is not None else None
def _abort():
    return abort_at is not None and time.time() >= abort_at

kwargs = {}
try:
    _params = inspect.signature(wf._seat_acquire).parameters
except (TypeError, ValueError):
    _params = {}
if "abort" in _params:
    kwargs["abort"] = _abort
if "admit_lock" in _params:
    kwargs["admit_lock"] = threading.Lock()

t0 = time.time()
got = wf._seat_acquire(Path(seats_dir), name, cap, bounded, **kwargs)
waited = time.time() - t0
unsupported = hasattr(wf, "_SEAT_UNSUPPORTED") and got is wf._SEAT_UNSUPPORTED
if got is None or unsupported:
    tickets_left = sorted(p.name for p in Path(seats_dir).glob("*.json")
                          if "ancestor-holder" not in p.name)
    print(json.dumps({"ok": False, "name": name,
                      "error_class": "seat_unsupported" if unsupported else "seat_wait",
                      "waited_s": round(waited, 3), "ancestors": ancestors,
                      "tickets_left": tickets_left}))
    sys.exit(2)
acquired_after = time.time()
time.sleep(hold_s)
wf._seat_release(got)
print(json.dumps({"ok": True, "name": name,
                  "acquired_after": round(acquired_after, 6),
                  "released_at": round(time.time(), 6),
                  "waited_s": round(waited, 3), "ancestors": ancestors}))
