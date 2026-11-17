#!/usr/bin/env python3
"""Rebuild a dead lane's working tree from its journaled tool calls (#37).

A build lane that wipes its own uncommitted work (a base checkout over a dirty
tree for a RED run) or dies at the turn cap with an unbanked tree still leaves
one durable trace: every tool call it made is journaled in the profile's
`state.db` (sessions row keyed by the runner's session key, messages in order).
This replays the write_file / patch calls into a restore dir so the recovery is
one command instead of a hand replay. Stdlib only (sqlite3, argparse); the db
is opened READ-ONLY (`mode=ro`) and never mutated.

Usage:
  python3 scripts/lane_recover.py --profile <name> --skey <session-key> [--out <restore-dir>]
  python3 scripts/lane_recover.py --run <run-id> [--node <id>] [--index <i>] [--attempt <n>] [--out <restore-dir>]

The session key is what the runner writes into the spawn record / node record
(`nodes/<node>[.<i>].json` -> `skey`): `wf:<run>:<node>[:<i>]:<efp8>.<nonce>`;
the child's sessions row carries `<skey>#a<attempt>` as its title. `--skey`
accepts either form (a bare key resolves to its latest attempt unless
`--attempt` is given). `--run` reads the key from the run dir instead (the run
dir resolves the way the read model does: `WF_RUNS_ROOT`, else
`$DUCKWORK_HOME/workflows`; the db home is the node's own child home for
profile-routed nodes, else the launcher's).

Default mode (no --out): the triage view — the ordered call list
(index, tool, target path; `[REFUSED]` when the live tool answered with an
error). With --out: emit `<out>/<relpath>` for each touched file (write_file
replays the content; patch applies old_string -> new_string to the
accumulated text — exact first, then whitespace-flexible) and write
`<out>/lane_recover_report.json`: `written`, `applied`, `unmatched` (anchor not
found / no path / arguments not JSON), `skipped` (the joined role='tool' result
carried an error — a refused write is not a write — or the anchor is ambiguous
without replace_all, the same refusal core `patch` makes), `unconfirmed` (no
result row at all: replayed, flagged).

Exit codes: 0 recovered > 0 (or a non-empty triage list), 2 no session / no
db / db locked by a live writer, 3 no journaled write_file/patch calls.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import threading
from pathlib import Path

REPLAY_TOOLS = ("write_file", "patch")

# ---------- est-ujtf: ONE live-plugin resolver (respawn must never boot an archive) ----------
# Law: the exact-name dir (plain or symlink) carrying wf.py is the ONLY answer;
# a `*.old-*` sibling is never a discovery match; a missing/broken live dir
# REFUSES with a message naming every archive it is refusing. Canonical
# symlink policy: an exact-name symlink is an operator-owned pointer and IS
# followed even if its target is an .old-* dir (refusing it would remove the
# only sanctioned symlink-deploy channel); what this refuses is DISCOVERY
# choosing an archive, which is why archives are never globbed, only named.
PLUGIN_NAME = "duckwork-workflows"


class PluginResolutionError(Exception):
    """No trustworthy live plugin copy: refuse to resolve, never fall back."""
    def __init__(self, msg):
        super().__init__(msg)
        self.code = 2


def _plugins_root(home=None):
    return Path(home if home else _duckwork_home()) / "plugins"


def resolve_plugin_dir(plugins_root=None):
    """Deterministically resolve the LIVE plugin dir under `plugins_root`
    (default: <duckwork_home>/plugins). Returns the exact-name
    `duckwork-workflows` dir when it (or its symlink target) is a dir carrying
    wf.py; raises PluginResolutionError otherwise — never returns an
    `*.old-*` archive, never silently picks a sibling."""
    root = Path(plugins_root) if plugins_root else _plugins_root()
    live = root / PLUGIN_NAME
    archives = sorted(p.name for p in root.glob(PLUGIN_NAME + ".old-*") if p.is_dir()) \
        if root.is_dir() else []
    if live.is_dir() and (live / "wf.py").is_file():
        return live
    detail = (f"live plugin dir {PLUGIN_NAME} "
              + ("exists but carries no wf.py at " if live.is_dir() else "is absent at ")
              + str(live))
    if archives:
        detail += (f"; refusing to boot an ARCHIVED copy instead — refused: {', '.join(archives)} "
                   f"under {root}. Restore/reinstall the live plugin and retry.")
    else:
        detail += f"; no {PLUGIN_NAME} copy under {root}. Restore/reinstall the live plugin and retry."
    raise PluginResolutionError(detail)


# ---------- est-2ek.1.718: crashed-no-exit watchdog (respawn on sight, once) ----------
# The crashed-no-exit signature (dead pid + absent runner_exit.json + unfinished
# node claims) is unambiguous: the watchdog respawns WITHOUT waiting for an owner
# wait call — exactly once per run fingerprint (guard file) — and appends one
# `runner_respawn` event as receipt. A VALID recorded exit is a verdict, never a
# crash. Three hard laws (zap review on #237):
#   * RECEIPT ON CONFIRMED SPAWN ONLY: the door's act_wait answer is propagated —
#     an error / unproven liveness writes NO receipt and NO guard, so retries
#     stay open. Confirmation reads the ONE liveness law back (HELD flock =>
#     live, else /proc pid identity); a spawn is never trusted by receipt alone.
#   * SERIALIZED ADMISSION: an exclusive flock is held across guard-check +
#     spawn + receipt + guard write; atomic replace alone is not exactly-once.
#   * THE ONE VALIDITY RULE: when wfcommon is importable, unfinished work is
#     read through wfcommon.node_rec (stale efp after an amend == pending,
#     cancelled == pending), and for fan-out nodes the AGGREGATE record is the
#     commit — committed item records never mask a missing aggregate. The
#     raw-status stdlib branch is the documented WEAKER fallback for when
#     wfcommon is unimportable.

def _jload(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _run_fingerprint(r):
    """Stable crash fingerprint: graph.json + run.json digests. Same content =
    same crash scene = the guard's key; an amend changes it and re-arms."""
    import hashlib
    h = hashlib.sha256()
    for name in ("graph.json", "run.json"):
        try:
            h.update((Path(r) / name).read_bytes())
        except OSError:
            h.update(b"\x00")
    return h.hexdigest()[:16]


def _flock_held(r):
    """Mirror of wfcommon.runner_lock_held: HELD => live, unconditionally."""
    import fcntl
    path = Path(r) / "runner.lock"
    try:
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return True                      # another fd holds it: live
    try:                                 # we hold it — not held before; release
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
    return False


def _pid_is_our_runner(pid, run):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace")
    except OSError:
        return False                     # unverifiable identity is not liveness
    return "wf.py" in cmd and str(Path(run).name) in cmd


def crashed_no_exit_signature(r):
    """True iff the run carries the crashed-no-exit signature: a previous pid,
    that pid provably dead (flock NOT held + pid identity failed), NO recorded
    runner_exit verdict, and unfinished work (a record still claiming running, or
    a graph node with no committed record). None/falsy otherwise."""
    r = Path(r)
    rec = _jload(r / "runner_exit.json")
    if isinstance(rec, dict) and rec.get("reason"):
        return False                     # a verdict — the wait path owns it
    pid_file = r / "wf.pid"
    try:
        pid = int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return False                     # no pid file = fresh, never-spawned run
    if _flock_held(r) or _pid_is_our_runner(pid, r):
        return False                     # live: nothing to revive
    graph = _jload(r / "graph.json") or {}
    nodes = graph.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return False
    wc = _wfcommon()
    byid = {n["id"]: n for n in nodes
            if isinstance(n, dict) and isinstance(n.get("id"), str)}
    for n in nodes:
        nid = n.get("id") if isinstance(n, dict) else None
        if not nid or nid not in byid:
            continue
        node = byid[nid]
        agg = _jload(r / "nodes" / f"{nid}.json")
        if isinstance(agg, dict) and agg.get("status") == "running":
            return True                  # falsely-claimed child = unfinished work
        if isinstance(agg, dict) and agg.get("status") in ("done", "partial", "failed",
                                                           "skipped"):
            if wc is not None and ("efp" in agg or "def_hash" in agg):
                # THE ONE validity rule, applied to every FINGERPRINTED
                # terminal aggregate — efp-era AND legacy def_hash-only alike
                # (#237 r4, zap): a genuinely amended legacy done commit reads
                # pending in the read model (stale def_hash fails the
                # legacy-chain rule; error_class=cancelled reads pending) and
                # must surface here too — skipping no-efp records hid
                # unfinished work from the watchdog. node_rec validates both
                # eras through the SAME primitive the read model uses, so a
                # valid legacy commit stays not-a-signature. A record with NO
                # fingerprint at all is the documented weaker shape (the
                # aggregate is the commit, pinned by r1 test C) — untouched.
                st, _rec = wc.node_rec(r, node, byid)
                if st == "pending":
                    return True
            continue                     # the AGGREGATE record is the commit
        return True                      # no aggregate commit = pending (items don't count)
    return False


def _load_door(plugin):
    """Import the door module from the LIVE plugin dir (test seam: monkeypatch
    THIS, not the importlib mechanics)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("wfdoor_watchdog",
                                                  str(Path(plugin) / "__init__.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _spawn_confirmed(r, waited):
    """Confirmation of a production revive: the door answered WITHOUT an error
    key AND the ONE liveness law reads a runner live (HELD flock => live, else
    the wf.pid /proc identity). Never trust a receipt the door never proved."""
    if isinstance(waited, dict) and waited.get("error"):
        return False
    if _flock_held(r):
        return True
    try:
        pid = int((Path(r) / "wf.pid").read_text().strip())
    except (OSError, ValueError):
        return False
    return _pid_is_our_runner(pid, r)


class _admission:
    """SERIALIZED ADMISSION (blocker 4): exclusive flock on <run>/respawn.admission
    held across guard-check + spawn + receipt + guard write. An atomic replace is
    not exactly-once; two concurrent callers must serialize here or both spawn."""

    def __init__(self, r):
        self.path = Path(r) / "respawn.admission"
        self.fd = None

    def __enter__(self):
        import fcntl
        self.fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        import fcntl
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
        return False


def recover_crashed_runner(r, spawn=None):
    """Watchdog entry: on the crashed-no-exit signature, respawn the runner
    ONCE per run fingerprint and append one `runner_respawn` receipt — only on
    a CONFIRMED spawn (blocker 1: an unconfirmed revive writes no receipt and
    no guard, so later attempts may retry). Admission is serialized by flock
    (blocker 4). `spawn` is injectable for tests (truthy return = confirmed
    spawn, falsy = nothing spawned); the production default revives in-place
    through the door at the LIVE plugin dir (resolve_plugin_dir — so a respawn
    can never boot an .old-* archive) and confirms via _spawn_confirmed.
    Returns {respawned, reason/prev_pid/fp}."""
    r = Path(r)
    fp = _run_fingerprint(r)
    guard = r / "respawn_guard.json"
    with _admission(r):
        g = _jload(guard)
        if isinstance(g, dict) and g.get("fp") == fp:
            return {"respawned": False,
                    "reason": f"guard: signature already respawned once for fp={fp}"}
        if not crashed_no_exit_signature(r):
            return {"respawned": False, "reason": "no crashed-no-exit signature"}
        try:
            prev_pid = int((r / "wf.pid").read_text().strip())
        except (OSError, ValueError):
            prev_pid = None
        if spawn is None:
            def _production_revive(run):             # revive in-place via the door
                plugin = resolve_plugin_dir()        # est-ujtf law: LIVE copy only
                waited = _load_door(plugin).act_wait({"run_id": Path(run).name,
                                                      "timeout": 1})
                if not _spawn_confirmed(run, waited):
                    return None                      # door error / no proved liveness
                try:                                 # the respawned runner's own pid
                    return int((Path(run) / "wf.pid").read_text().strip())
                except (OSError, ValueError):
                    return waited
            spawn = _production_revive
        handle = spawn(r)
        if not handle:
            return {"respawned": False, "prev_pid": prev_pid, "fp": fp,
                    "reason": "spawn unconfirmed (door error or liveness not proved) "
                              "— no receipt written; retries stay open"}
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(r / "events.jsonl", "a") as f:
            f.write(json.dumps({"ts": ts, "event": "runner_respawn", "prev_pid": prev_pid,
                                "fp": fp, "by": "lane_recover.watchdog"},
                               ensure_ascii=False) + "\n")
        tmp = guard.with_name(
            f"respawn_guard.json.{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps({"fp": fp, "at": ts, "prev_pid": prev_pid,
                                   "spawned_pid": handle}) + "\n", encoding="utf-8")
        os.replace(tmp, guard)
        return {"respawned": True, "prev_pid": prev_pid, "fp": fp, "spawned_pid": handle}
# ---------- #733 dead-on-arrival finalize (reaper-callable, explicit act) ----------
# The census shape (2026-10-06, 63 stale records): the runner + its children were
# SIGKILLed out-of-band; the door's silent-death reaper made the death loud (its
# law: event-only, records byte-intact — "a reaper must not erase the crime
# scene") but when no replacement runner ever arrives, node records claim
# status="running" with a dead pid forever and the run reads non-terminal on
# every watcher. The finalize is the missing CLOSE step, invoked explicitly by
# the reaper-caller (never a passive read, never inside the door's respawn
# reaper whose bytes its own tests pin): non-terminal claims whose spawn record
# fails the ONE verification law are closed as failed/dead-on-arrival, and the
# run gets a terminal blocked verdict only if no authoritative one stands.
DOA_FINALIZED = "dead-on-arrival"
# #235 review F5: reuse a member of the closed wf.ERROR_CLASSES set — the
# runner died, so its children were never finalized; `finalized` carries the
# dead-on-arrival provenance, the class stays read-model vocabulary.
DOA_ERROR_CLASS = "crashed"


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_json(p: Path, obj):
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, default=str))
        os.replace(tmp, p)
    except OSError:
        tmp.unlink(missing_ok=True)                    # never leave tmp litter behind
        raise


def _take_runner_flock(r):
    """#235 review F2: the runner's OWN admission flock (wf.py acquire_lock:
    LOCK_EX on <run>/runner.lock, same bounded 3 x 10ms LOCK_NB retry so a
    liveness PROBE's microsecond hold is not mistaken for a runner). Held
    across the whole check-and-write, so no runner can be admitted and commit
    between our liveness read and our write. Returns the fd, or None when a
    holder exists (= runner live)."""
    import fcntl
    import time
    fd = os.open(str(Path(r) / "runner.lock"), os.O_RDWR | os.O_CREAT, 0o644)
    for _ in range(3):
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except OSError:
            time.sleep(0.01)
    os.close(fd)
    return None


def finalize_run(run_dir):
    """Close a dead lane's falsely-claimed running records. Returns the process
    exit code: 0 done (or nothing left to do); 2 unknown run / no pid file — a
    fresh run nobody ever claimed; 3 runner alive — leave alone; 4 a write
    failed (record or runner_exit) — rerun once writable, the pass repairs.

    Law: the whole pass runs UNDER the runner's own flock (F2). Only
    status=="running" records whose spawn fails wfcommon._verify_spawn_rec (a
    verifiably-live child is ADOPTED, never finalized) are written:
      status="failed", finalized="dead-on-arrival", error_class="crashed",
      death_cause, finished_at. The record's OWN fingerprint is kept verbatim —
      never stamped from the current graph (F3: a legacy/stale claim must stay
      stale, not become a current failed commit for a node it never ran).
    A fan-out node whose current-efp item claims were closed and which has NO
    aggregate record gets a failed aggregate (F1: node_rec reads only the
    aggregate — without it the parent read pending and the run `interrupted`).
    The run gets ONE terminal verdict in the runner's own read-model vocabulary
    ("blocked by failed <ids>", detail names dead-on-arrival) only when no
    authoritative verdict stands; a recorded exit — fresh or amend-staled — is
    never overwritten. Verdict + aggregates derive from ALL dead-on-arrival
    records, so a retry repairs a write the previous pass lost (F4).
    Idempotent: a second pass changes zero bytes."""
    wc = _wfcommon()
    if wc is None:
        print("finalize needs wfcommon importable beside this script", file=sys.stderr)
        return 2
    r = Path(run_dir)
    graph = wc.jload(r / "graph.json")
    if not isinstance(graph, dict) or not graph.get("nodes"):
        print(f"no usable graph.json under {r}", file=sys.stderr)
        return 2
    if not (r / "wf.pid").exists():
        print(f"{r}: no wf.pid — a fresh/never-spawned run is not stuck", file=sys.stderr)
        return 2
    lock = _take_runner_flock(r)
    if lock is None:
        print(f"{r}: runner alive (runner.lock held) — nothing to finalize", file=sys.stderr)
        return 3
    try:
        # pid half of the ONE liveness law (runner_alive minus the flock probe,
        # which would read OUR held lock as a live runner).
        if wc._runner_pid_alive(r):
            print(f"{r}: runner alive — nothing to finalize", file=sys.stderr)
            return 3
        return _finalize_locked(wc, r, graph)
    finally:
        os.close(lock)                                 # kernel releases the flock


def _finalize_locked(wc, r, graph):
    byid = {n["id"]: n for n in graph["nodes"] if isinstance(n, dict) and n.get("id")}
    errors = 0
    newly = []                                         # node ids closed THIS pass
    doa = []                                           # (nid, is_item, rec): every DOA record
    for p in sorted((r / "nodes").glob("*.json")):
        try:
            rec = wc.jload(p)
        except Exception:
            continue                                   # torn record: never a fact, never fatal
        stem = p.stem
        nid, _, idx = stem.partition(".")
        n = byid.get(nid)
        if n is None or not isinstance(rec, dict):
            continue                                   # orphan record (amended-away node): not ours
        if rec.get("finalized") == DOA_FINALIZED:
            doa.append((nid, bool(idx), rec))          # already closed: idempotent
            continue
        if rec.get("status") != "running":
            continue                                   # committed/absent truth is never rewritten
        if wc._verify_spawn_rec(r, n, byid, rec):
            continue                                   # ONE verification law: live child => adopt
        closed = dict(rec)                             # own efp/def_hash kept verbatim (F3)
        closed.update(
            status="failed",
            finalized=DOA_FINALIZED,
            error_class=DOA_ERROR_CLASS,
            death_cause=f"runner dead (pid {closed.get('pid')} unverifiable), child never "
                        f"finalized — closed by lane_recover --finalize",
            finished_at=_now_iso(),
        )
        try:
            _atomic_json(p, closed)
        except OSError as e:
            print(f"{p}: finalize write failed: {e}", file=sys.stderr)
            errors += 1
            continue
        newly.append(nid)
        doa.append((nid, bool(idx), closed))
    if newly:
        try:
            with open(r / "events.jsonl", "a") as f:
                f.write(json.dumps({"ts": _now_iso(), "event": "run.finalized_doa",
                                    "nodes": sorted(set(newly)), "count": len(newly)},
                                   ensure_ascii=False) + "\n")
        except OSError:
            pass
    # F1: a fan-out parent with closed CURRENT item claims and no aggregate
    # gets the terminal aggregate the dead runner never wrote.
    for nid in sorted({nid for nid, is_item, rec in doa
                       if is_item and wc.record_efp_valid(rec, byid, byid[nid])}):
        agg = r / "nodes" / f"{nid}.json"
        if agg.exists():
            continue                                   # an aggregate is a fact: never rewritten
        items = sorted(int(q.stem.split(".", 1)[1]) for q in (r / "nodes").glob(f"{nid}.[0-9]*.json")
                       if (wc.jload(q) or {}).get("finalized") == DOA_FINALIZED)
        try:
            _atomic_json(agg, {
                "status": "failed", "finalized": DOA_FINALIZED, "error_class": DOA_ERROR_CLASS,
                "death_cause": f"fan-out item(s) {items} closed dead-on-arrival — runner dead "
                               f"before the aggregate commit; closed by lane_recover --finalize",
                "items_finalized": items, "finished_at": _now_iso(),
                "efp": wc.efp(byid, byid[nid]), "fp_rule_version": wc.FP_RULE_VERSION})
        except OSError as e:
            print(f"{agg}: aggregate write failed: {e}", file=sys.stderr)
            errors += 1
    ids = sorted({nid for nid, _i, _rec in doa})
    if not ids:
        return 4 if errors else 0
    # terminal verdict ONLY if no authoritative one stands. A recorded exit
    # (fresh OR amend-staled — a verdict is a verdict) is never overwritten; a
    # finalize-authored one counts (idempotency).
    rx = wc.jload(r / "runner_exit.json")
    verdict = wc.runner_exit_read(r) or {}
    keep = bool(verdict.get("reason")) and verdict.get("reason") != "crashed (no exit record)"
    if (isinstance(rx, dict) and rx.get("finalized") == DOA_FINALIZED) or keep:
        return 4 if errors else 0
    try:
        _atomic_json(r / "runner_exit.json", {
            # the runner's own verdict vocabulary — run_state classifies it failed
            "reason": "blocked by failed " + ",".join(ids), "at": _now_iso(),
            "detail": f"dead-on-arrival: runner dead, {len(ids)} node(s) closed by "
                      f"lane_recover --finalize",
            "graph_fingerprint": wc.graph_fingerprint(graph),
            "fp_rule_version": wc.FP_RULE_VERSION,
            "finalized": DOA_FINALIZED})
    except OSError as e:
        print(f"{r}: runner_exit write failed: {e} — rerun --finalize to repair", file=sys.stderr)
        errors += 1
    return 4 if errors else 0


class Bail(Exception):
    """A typed early exit: message + process exit code (2 = no session/run/db)."""
    def __init__(self, msg, code=2):
        super().__init__(msg)
        self.code = code
REPORT_NAME = "lane_recover_report.json"


# ---------- HOME -> state.db (the read model's mapping, reused not re-derived) ----------

def _wfcommon():
    """wfcommon when importable (plugin checkout beside this script), else None."""
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        import wfcommon  # noqa: E402
        return wfcommon
    except Exception:
        return None


def _duckwork_home():
    wc = _wfcommon()
    if wc is not None:
        return Path(wc.duckwork_home())
    return Path(os.environ.get("DUCKWORK_HOME") or (Path.home() / ".duckwork"))


def profile_db(profile, home=None):
    """`<profiles_root>/<profile>/state.db` via wfcommon.profile_home (the door's own
    mapping: `<root>/profiles/<name>` where root = DUCKWORK_HOME.parent.parent when
    DUCKWORK_HOME is itself a named profile home). `--profile default` (or empty) is
    the launcher home itself."""
    home = Path(home) if home else _duckwork_home()
    if not profile or profile == "default":
        return home / "state.db"
    wc = _wfcommon()
    if wc is not None:
        return Path(wc.profile_home(profile, home)) / "state.db"
    root = home.parent.parent if home.parent.name == "profiles" else home
    return root / "profiles" / str(profile) / "state.db"


# ---------- run-dir lookup (--run): the spawn record names the key ----------

def run_lookup(run_id, node, index=None, home=None):
    """(skey, db_path) from the run dir's node record. Raises SystemExit(2) with a
    message when the run/record/key is missing."""
    wc = _wfcommon()
    if wc is not None:
        r = Path(wc.find_run(run_id))
    else:
        root = os.environ.get("WF_RUNS_ROOT") or str(_duckwork_home() / "workflows")
        r = Path(root) / run_id
    if not (r / "graph.json").exists():
        raise Bail(f"no run dir for {run_id!r} at {r}")
    if not node:
        raise Bail("--run needs --node <id> (the node whose child tree to rebuild)")
    name = str(node) + (f".{index}" if index is not None else "")
    rec_path = r / "nodes" / f"{name}.json"
    try:
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Bail(f"no node record at {rec_path}")
    skey = rec.get("skey") if isinstance(rec, dict) else None
    if not isinstance(skey, str) or not skey:
        raise Bail(f"node record {rec_path} carries no skey")
    db_home = None
    if wc is not None:
        db_home = wc.node_child_home(r, node, index)
    elif isinstance(rec.get("profile_home"), str):
        db_home = Path(rec["profile_home"])
    db = (Path(db_home) if db_home else _duckwork_home()) / "state.db"
    return skey, db


# ---------- the journal ----------

def open_ro(db):
    db = Path(db)
    if not db.exists():
        raise Bail(f"no state.db at {db}")
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=1.0)


def find_session(conn, skey, attempt=None):
    """The sessions row for a child key. `skey` may already carry `#a<n>`; a bare
    key picks `--attempt` when given, else the LATEST attempt (max started_at,
    rowid). Returns (id, title) or None."""
    if "#a" in skey:
        row = conn.execute("select id, title from sessions where title = ? "
                           "order by started_at desc, rowid desc limit 1", (skey,)).fetchone()
        return tuple(row) if row else None
    if attempt is not None:
        row = conn.execute("select id, title from sessions where title = ? "
                           "order by started_at desc, rowid desc limit 1",
                           (f"{skey}#a{attempt}",)).fetchone()
        return tuple(row) if row else None
    rows = conn.execute("select id, title from sessions where title = ? or title like ? "
                        "order by started_at desc, rowid desc",
                        (skey, skey + "#a%")).fetchall()
    return tuple(rows[0]) if rows else None


# Plain-text tool results (non-JSON) that core emits when it REFUSES a write. The
# JSON form (`{"error": ...}`, what tools/file_tools.py returns) is the primary
# signal; these phrases catch a result that was flattened to text.
_REFUSAL_TEXT = re.compile(r"^\s*error\b|\bFound \d+ (?:approximate )?matches\b|"
                           r"\bCould not find\b|\bold_string not found\b|\bpermission denied\b",
                           re.IGNORECASE)


def result_error(content):
    """The error text carried by a role='tool' result row, or None when the call
    succeeded. Core file tools answer with a JSON object whose `error` key is set
    on refusal (ambiguous anchor, anchor not found, denied path, stale write);
    a non-JSON body is checked against the known refusal phrases."""
    if content is None:
        return None
    if isinstance(content, (bytes, bytearray)):
        content = content.decode("utf-8", "replace")
    if not isinstance(content, str):
        return None
    s = content.strip()
    if not s:
        return None
    parsed = None
    if s[:1] in "{[":
        try:
            parsed = json.loads(s)
        except ValueError:
            parsed = None
    if isinstance(parsed, dict):
        err = parsed.get("error")
        return str(err) if err else None
    if parsed is not None:
        return None
    if _REFUSAL_TEXT.search(s):
        return s
    return None


def tool_results(conn, session_id):
    """{tool_call_id: content} for every role='tool' row of the session — the
    result side of the journal, joined to the assistant side by tool_call_id.
    The FIRST result per id wins (a duplicated id keeps its original answer)."""
    res = {}
    rows = conn.execute("select id, tool_call_id, content from messages where session_id = ? "
                        "and role = 'tool' and tool_call_id is not null order by id",
                        (session_id,)).fetchall()
    for _mid, cid, content in rows:
        if cid and cid not in res:
            res[cid] = content
    return res


def journaled_calls(conn, session_id):
    """Ordered [{index, tool, args, call_id, msg_id, error}] of write_file/patch
    calls. The assistant row's `tool_calls` column is a JSON list of
    {id, type:'function', function:{name, arguments:<JSON string>}}; the tool
    result row (role='tool') that follows carries `tool_call_id` + `tool_name`
    and the tool's answer. We read the assistant side (it holds the arguments)
    and JOIN the result row by tool_call_id: a call whose result carries an
    error is kept in the list (the triage view still shows it) but flagged with
    `error` so replay SKIPS it — a refused write is not a write. A call with no
    result row at all (the lane died mid-call) is replayed but `confirmed`
    is False and the report lists it under `unconfirmed`."""
    out = []
    results = tool_results(conn, session_id)
    rows = conn.execute("select id, role, tool_calls from messages where session_id = ? "
                        "and tool_calls is not null order by id", (session_id,)).fetchall()
    for mid, role, tc in rows:
        try:
            calls = json.loads(tc) if isinstance(tc, str) else tc
        except ValueError:
            continue
        if not isinstance(calls, list):
            continue
        for c in calls:
            fn = (c or {}).get("function") if isinstance(c, dict) else None
            if not isinstance(fn, dict):
                continue
            name = fn.get("name")
            if name not in REPLAY_TOOLS:
                continue
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {"_unparsed": args}
            if not isinstance(args, dict):
                args = {}
            cid = c.get("id") or c.get("call_id")
            confirmed = cid in results
            error = result_error(results[cid]) if confirmed else None
            out.append({"index": len(out), "tool": name, "args": args,
                        "call_id": cid, "msg_id": mid, "error": error, "confirmed": confirmed})
    return out


def target_path(call):
    return str(call["args"].get("path") or call["args"].get("file_path") or "")


# ---------- replay ----------

def _ws_flex(s):
    """Whitespace-flexible regex for a patch anchor: every INNER run of whitespace
    matches any run of whitespace (indent / trailing-space drift), literal
    otherwise; a leading indent matches any indent and a trailing newline still
    consumes through the end of that line, so the replacement keeps line shape."""
    parts = [re.escape(p) for p in re.split(r"\s+", s.strip()) if p]
    if not parts:
        return None
    head = r"[ \t]*" if s[:1] in (" ", "\t") else ""
    tail = r"[ \t]*\n" if s.endswith("\n") else (r"[ \t]*" if s[-1:] in (" ", "\t") else "")
    return re.compile(head + r"\s+".join(parts) + tail)


def apply_patch(text, old, new, replace_all=False):
    """(new_text, how) — how in {'exact', 'fuzzy', 'ambiguous:<n>', None}. Exact
    substring first; then whitespace-flexible; None leaves the text untouched.
    An anchor with more than one hit and no replace_all is REFUSED (text
    untouched, how = 'ambiguous:<n>') — the same rule core `patch` applies
    (fuzzy_match.py: "Found N matches … use replace_all=True"); never the first."""
    if old is None:
        return text, None
    if old == "":
        return text + new, "exact"           # empty anchor: append (an insert)
    n = text.count(old)
    if n:
        if replace_all:
            return text.replace(old, new), "exact"
        if n > 1:
            return text, f"ambiguous:{n}"
        return text.replace(old, new, 1), "exact"
    rx = _ws_flex(old)
    if rx is not None:
        hits = list(rx.finditer(text))
        if hits:
            if replace_all:
                return rx.sub(lambda _m: new, text), "fuzzy"
            if len(hits) > 1:
                return text, f"ambiguous:{len(hits)}"
            m = hits[0]
            return text[:m.start()] + new + text[m.end():], "fuzzy"
    return text, None


def _rel(p):
    """A safe restore-relative path: absolute paths lose their root, `..` is dropped."""
    parts = [x for x in Path(p).parts if x not in ("/", "..", "")]
    if parts and re.match(r"^[A-Za-z]:\\?$", parts[0]):
        parts = parts[1:]
    return Path(*parts) if parts else Path("_unnamed")


def replay(calls, out_dir, seed_root=None):
    """Replay into out_dir. Files are accumulated in memory per target path
    (write_file sets, patch edits) then flushed. A patch whose file has no prior
    write in the journal seeds from `seed_root/<rel>` when that exists (the lane's
    committed base), else from the target path itself if readable, else ''."""
    out_dir = Path(out_dir)
    files, seeded_from = {}, {}
    report = {"unmatched": [], "applied": [], "written": [], "skipped": [], "unconfirmed": []}
    for c in calls:
        p = target_path(c)
        if "_unparsed" in c["args"]:
            # corrupt payload: nothing to replay, distinct from a well-formed pathless call
            report["unmatched"].append({"index": c["index"], "tool": c["tool"], "path": "",
                                        "reason": "arguments not JSON",
                                        "arguments_head": str(c["args"]["_unparsed"])[:200]})
            continue
        if c.get("error"):
            # the live tool REFUSED this call (joined role='tool' row carries the error):
            # a refused write is not a write — never replay it.
            report["skipped"].append({"index": c["index"], "tool": c["tool"], "path": p,
                                      "reason": "tool result carries an error: " + str(c["error"])[:300]})
            continue
        if not p:
            report["unmatched"].append({"index": c["index"], "tool": c["tool"], "path": "",
                                        "reason": "no path argument"})
            continue
        if not c.get("confirmed", True):
            report["unconfirmed"].append({"index": c["index"], "tool": c["tool"], "path": p,
                                          "reason": "no tool result journaled (lane died mid-call?)"})
        rel = _rel(p)
        if c["tool"] == "write_file":
            files[rel] = str(c["args"].get("content", ""))
            report["written"].append({"index": c["index"], "path": p})
            continue
        if rel not in files:
            seed = None
            for cand in ((Path(seed_root) / rel) if seed_root else None, Path(p)):
                if cand is not None and cand.is_file():
                    try:
                        seed = cand.read_text(encoding="utf-8")
                        seeded_from[rel] = str(cand)
                        break
                    except OSError:
                        pass
            files[rel] = seed if seed is not None else ""
        a = c["args"]
        new_text, how = apply_patch(files[rel], a.get("old_string"), str(a.get("new_string", "")),
                                    bool(a.get("replace_all")))
        if how is None:
            report["unmatched"].append({"index": c["index"], "tool": "patch", "path": p,
                                        "reason": "old_string not found (exact or whitespace-flexible)",
                                        "old_string_head": str(a.get("old_string", ""))[:200]})
        elif how.startswith("ambiguous:"):
            n_hits = how.split(":", 1)[1]
            report["skipped"].append({"index": c["index"], "tool": "patch", "path": p,
                                      "reason": f"ambiguous ({n_hits} matches)",
                                      "old_string_head": str(a.get("old_string", ""))[:200]})
        else:
            files[rel] = new_text
            report["applied"].append({"index": c["index"], "path": p, "match": how})
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text, encoding="utf-8")
    report["files"] = sorted(str(k) for k in files)
    report["seeded_from"] = {str(k): v for k, v in seeded_from.items()}
    (out_dir / REPORT_NAME).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    return report


# ---------- cli ----------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_argument_group("journal source")
    src.add_argument("--profile", help="profile whose state.db holds the child session "
                                       "('default' = the launcher home)")
    src.add_argument("--skey", help="child session key (with or without #a<n>)")
    src.add_argument("--run", help="run id; the key is read from nodes/<node>[.<i>].json")
    src.add_argument("--node", help="node id (with --run)")
    src.add_argument("--index", type=int, help="fan-out item index (with --run)")
    src.add_argument("--attempt", type=int, help="attempt number (#a<n>); default: latest")
    ap.add_argument("--db", help="explicit state.db path (overrides --profile / --run mapping)")
    ap.add_argument("--home", help="DUCKWORK_HOME to resolve profiles/runs from (default: env)")
    ap.add_argument("--out", help="restore dir; omit for the triage view")
    ap.add_argument("--seed", help="tree to seed patched-but-never-written files from "
                                   "(e.g. the lane's committed base checkout)")
    ap.add_argument("--watchdog", metavar="RUN_ID",
                    help="est-2ek.1.718: check RUN_ID for the crashed-no-exit signature "
                         "(dead pid + no runner_exit.json + unfinished claims) and respawn "
                         "the runner ONCE per fingerprint; prints the verdict JSON")
    fin = ap.add_argument_group("#733 dead-on-arrival finalize (mutually exclusive with replay)")
    fin.add_argument("--finalize", metavar="RUN_DIR",
                     help="close a dead lane's falsely-claimed running node records "
                          "(runner verified dead): each unverifiable status=running "
                          "record -> failed + finalized=dead-on-arrival + death_cause + "
                          "finished_at; the run gets a terminal blocked verdict only if "
                          "no authoritative exit record stands. Idempotent; a live "
                          "child is adopted, never finalized (exit 3 when the runner "
                          "is alive, 2 for an unknown/fresh run, 4 when a write failed "
                          "— rerun to repair, 0 when done).")
    args = ap.parse_args(argv)
    if args.home:   # the read model resolves runs/profiles from DUCKWORK_HOME; honor the flag
        os.environ["DUCKWORK_HOME"] = str(Path(args.home).expanduser())   # (before --watchdog too)
    if args.watchdog:
        wc = _wfcommon()
        if wc is not None:
            wd_run = Path(wc.find_run(args.watchdog))
        else:
            root = os.environ.get("WF_RUNS_ROOT") or str(_duckwork_home() / "workflows")
            wd_run = Path(root) / args.watchdog
        if not (wd_run / "graph.json").exists():
            print(f"no run dir for {args.watchdog!r} at {wd_run}", file=sys.stderr)
            return 2
        print(json.dumps(recover_crashed_runner(wd_run)))
        return 0

    if args.finalize:
        # #733: an explicit close act, never entangled with the replay path.
        # A bare run id resolves the way the read model does (WF_RUNS_ROOT /
        # --home, else wfcommon.find_run); a path is taken verbatim.
        cand = Path(args.finalize)
        if not cand.is_dir():
            root = os.environ.get("WF_RUNS_ROOT") or str(_duckwork_home() / "workflows")
            cand = Path(root) / args.finalize
            if not cand.is_dir():
                wc = _wfcommon()
                if wc is not None:
                    try:
                        cand = Path(wc.find_run(args.finalize))
                    except SystemExit:
                        pass
        return finalize_run(cand)

    if args.run:
        skey, db = run_lookup(args.run, args.node, args.index, args.home)
    elif args.skey:
        skey, db = args.skey, profile_db(args.profile, args.home)
    else:
        ap.error("need --skey (with --profile) or --run --node")
    if args.db:
        db = Path(args.db)

    try:
        conn = open_ro(db)
    except sqlite3.OperationalError as e:
        raise Bail(f"state.db not readable right now ({e}) at {db}")
    try:
        sess = find_session(conn, skey, args.attempt)
        if sess is None:
            print(f"no session for {skey!r} in {db}", file=sys.stderr)
            return 2
        sid, title = sess
        calls = journaled_calls(conn, sid)
    except sqlite3.OperationalError as e:
        # a live writer holding EXCLUSIVE (or a corrupt/odd file): a clean bail, no traceback
        raise Bail(f"state.db not readable right now ({e}) at {db} — retry when the lane's "
                   f"writer releases it")
    finally:
        conn.close()
    if not calls:
        print(f"session {title!r} ({sid}) journaled no write_file/patch calls", file=sys.stderr)
        return 3

    if not args.out:
        print(f"session {title} ({sid}) — {len(calls)} journaled write_file/patch call(s):")
        for c in calls:
            flag = "  [REFUSED]" if c.get("error") else ("  [no result]" if not c.get("confirmed", True) else "")
            print(f"{c['index']:4d}  {c['tool']:<10}  {target_path(c)}{flag}")
        return 0

    rep = replay(calls, args.out, args.seed)
    n_files = len(rep["files"])
    print(f"session {title} ({sid}): {len(rep['written'])} write_file, "
          f"{len(rep['applied'])} patch applied, {len(rep['unmatched'])} unmatched, "
          f"{len(rep['skipped'])} skipped "
          f"-> {n_files} file(s) under {args.out} (report: {Path(args.out) / REPORT_NAME})")
    for u in rep["unmatched"]:
        print(f"  UNMATCHED #{u['index']} {u['tool']} {u['path']}: {u['reason']}")
    for u in rep["skipped"]:
        print(f"  SKIPPED #{u['index']} {u['tool']} {u['path']}: {u['reason']}")
    for u in rep["unconfirmed"]:
        print(f"  UNCONFIRMED #{u['index']} {u['tool']} {u['path']}: {u['reason']}")
    return 0 if n_files > 0 else 3


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Bail, PluginResolutionError) as e:   # both carry the documented exit code
        print(str(e), file=sys.stderr)
        sys.exit(e.code)
