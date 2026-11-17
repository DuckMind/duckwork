#!/usr/bin/env python3
"""Serial bounded suite with durable per-case logs and atomic exit ledger.

The ledger resets per run: exits.json reports the CURRENT pass only.

Pass-gate admission contract (#17): with --baseline <exits.json> (a prior run's
ledger, e.g. the clean base SHA), the run additionally writes admission.json
next to exits.json carrying the EXACT red identities (test name + exit code)
split into introduced vs pre-existing, plus fixed reds. The gate never waives
anything: only a fully-green integrated SHA (zero reds, base or fix) is green
and exits 0; pre-existing reds land in blocking_base_reds for a linked fix
item, never hand-carried. Without --baseline every red is reported as
introduced (there is no evidence it pre-existed).

Zero-discovery is a failed admission (#112): an empty tests/ dir that
discovers no cases is not a pass — the run writes exits.json == [] and
admission.json green:false + zero_discovery:true and exits nonzero, so a
suite that ran nothing can never report green. An invalid root (missing
root or missing tests directory) fails closed as exit 2 BEFORE any out-dir
side effects, leaving no ledger or admission behind.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def load_baseline(path):
    """Read a prior ledger into {test: exit}. Contract is exact identities, so
    an unreadable/malformed baseline is a hard error (exit 2), never a silent
    fallback that could launder an introduced red as pre-existing."""
    try:
        rows = json.loads(Path(path).read_text())
        if not isinstance(rows, list):
            raise ValueError('ledger is not a list')
        for row in rows:
            if not isinstance(row, dict) or 'test' not in row or 'exit' not in row:
                raise ValueError(f'ledger row missing test/exit: {row!r}')
        return {row['test']: int(row['exit']) for row in rows}
    except Exception as exc:
        print(f'suite: baseline ledger unusable ({path}): {type(exc).__name__}: {exc}',
              flush=True)
        raise SystemExit(2)


def admission(base_reds, reds, baseline_path=None, present=None):
    """Diff red identities base vs fix. An identity match requires BOTH the
    test name and the exit code: the same test dying differently (1 vs 124) is
    a different failure and counts as introduced. A base red that does not
    appear in the fix run AT ALL is `missing` — a deleted test is not a fixed
    test (review F1: `rm` must not launder a base red; the #17 'never
    auto-waives' law covers deletion, so `missing` blocks like a red does).
    `fixed` therefore requires the test PRESENT (in `present`, the set of every
    test the fix run executed) AND green. `present` defaults to
    set(base) | set(reds) for library callers. Zero discovery is a failed
    admission (#112): green requires a non-empty present set — a suite that
    ran nothing never reports green."""
    base = dict(base_reds) if base_reds is not None else {}
    present = set(reds) if present is None else set(present)
    zero_discovery = not present
    base_reds_only = {n: rc for n, rc in base.items() if rc != 0}
    introduced = sorted(n for n, rc in reds.items() if base.get(n) != rc)
    pre_existing = sorted(n for n, rc in reds.items() if base.get(n) == rc)
    missing = sorted(n for n in base_reds_only if n not in present)
    fixed = sorted(n for n in base_reds_only if n in present and n not in reds)
    return {
        'baseline': None if baseline_path is None else str(baseline_path),
        # review F2: `base_reds` = RED identities only (rc != 0) — the shape the
        # downstream pass gate reads literally; the whole baseline map rides as
        # `base_exits` for provenance.
        'base_reds': dict(sorted(base_reds_only.items())),
        'base_exits': dict(sorted(base.items())),
        'reds': dict(sorted(reds.items())),
        'introduced': introduced,
        'pre_existing': pre_existing,
        'missing': missing,
        'blocking_base_reds': sorted(set(pre_existing) | set(missing)),  # never waived
        'fixed': fixed,
        'zero_discovery': zero_discovery,
        'green': not reds and not missing and not zero_discovery,  # fully-green integrated SHA only
    }


def parse_args(argv):
    root = Path(argv[1]).resolve()
    out = Path(argv[2]).resolve()
    baseline = None
    rest = argv[3:]
    i = 0
    while i < len(rest):
        if rest[i] == '--baseline':
            if i + 1 >= len(rest):
                print('suite: --baseline needs a path to an exits.json ledger', flush=True)
                raise SystemExit(2)
            baseline = Path(rest[i + 1]).resolve()
            i += 2
        else:
            print(f'suite: unknown argument {rest[i]!r}', flush=True)
            raise SystemExit(2)
    return root, out, baseline


root, out, _baseline_path = parse_args(sys.argv)


def invalidate_receipts():
    """A refused invocation must never leave a PRIOR green receipt standing in a
    reused out-dir (CI cache reuse, stale --baseline flows): a consumer reading
    only admission.json would mistake yesterday's success for current proof.
    Invalidate if the dir exists; never CREATE it."""
    if out.exists():
        (out / 'admission.json').unlink(missing_ok=True)
        (out / 'exits.json').unlink(missing_ok=True)


# #112: validate the invocation BEFORE any out-dir side effects — an invalid
# root must never leave a green-looking ledger or admission behind.
if not root.is_dir() or not (root / 'tests').is_dir():
    print(f'suite: invalid root: {root} (missing root or tests directory)', flush=True)
    invalidate_receipts()
    raise SystemExit(2)
if _baseline_path:
    try:
        base_reds = load_baseline(_baseline_path)
    except SystemExit:
        # The refusal is right; the durable receipt must agree with it. A reused
        # out-dir holding a prior green admission + ledger would otherwise still
        # read as current proof after this exit-2 (#112 F4 law, baseline path).
        invalidate_receipts()
        raise
else:
    base_reds = None
out.mkdir(parents=True, exist_ok=True)
ledger = out / 'exits.json'
# fb 3d2175e9cd75d2a1: a suite run reports the CURRENT pass only — reset the
# ledger at start instead of appending to a stale dir's rows. Durability is
# kept: the per-case atomic tmp+os.replace write below persists progress.
rows = []
tmp = ledger.with_suffix('.tmp')
tmp.write_text('[]\n')
os.replace(tmp, ledger)
# review F5: admission.json resets with the ledger — an interrupted re-run must
# never leave a stale admission.json beside the fresh (partial) ledger.
(out / 'admission.json').unlink(missing_ok=True)
py = sorted((root / 'tests').glob('test_*.py'))
js = sorted((root / 'tests').glob('test_*.mjs'))
cases = [[sys.executable, str(p)] for p in py] + [['node', '--experimental-strip-types', str(p)] for p in js]
# est-2ek.1.762: the serial run exports a TEMPORARY WF_RUNS_ROOT so a test that
# forgets its own pin can never land fixture runs in the PRODUCTION runs root
# (774/1227 zero-log fixture dirs were leaked exactly this way; census spool
# key 9cfe87a0199e5e1b). An inherited hostile root is replaced; tests that
# self-pin (the law) overwrite it in their own child envs and are unaffected.
import atexit as _atexit
import shutil as _shutil
import tempfile as _tempfile
_suite_runs_root = Path(_tempfile.mkdtemp(prefix='wf-suite-runs-'))
# est-7ps8 (note 3): the temp root is the suite's own scratch — best-effort
# removal at process end via atexit, which runs on normal exit, SystemExit,
# and handled exceptions; it is NOT a guarantee under SIGKILL or a native
# crash (no handler runs there). mkdir'd lazily by an unpinned test's child,
# so cleanup is best-effort and never raises.
_atexit.register(_shutil.rmtree, _suite_runs_root, ignore_errors=True)
# Tests own private shelves, not the caller's lane identity. Keep the operator
# launcher override; leave the live shelf guard unchanged (est-2ek.1.808).
_KEEP_WF_ENV = {'DUCKWORK_WF_DUCKWORK_BIN'}
# est-2ek.1.862: a test process must never wear the LAUNCHING agent's session
# identity. An API seat exports DUCKWORK_SESSION_PLATFORM=api_server (and friends);
# the door stamps run.json.owner.{session_id,ui_session_id,platform} via
# _session_env, so the frozen golden baseline (owner.platform null) was CI-green
# / seat-red — six owner diffs under an inherited env. The suite owns the seat
# the tests see: DUCKWORK_SESSION_* / DUCKWORK_UI_SESSION_* are lane-identity keys,
# stripped exactly like DUCKWORK_WF_* above. Tests that WANT a session identity
# set it themselves in their own child env (wake matrices, card suites).
_NO_SESSION_IDENTITY = {k for k in os.environ
                        if k.startswith('DUCKWORK_SESSION_')
                        or k.startswith('DUCKWORK_UI_SESSION_')}
_base_env = {k: v for k, v in os.environ.items()
             if (not k.startswith('DUCKWORK_WF_') or k in _KEEP_WF_ENV)
             and k not in _NO_SESSION_IDENTITY}
for argv in cases:
    name = Path(argv[-1]).name
    log = out / (name + '.log')
    try:
        with log.open('w') as fh:
            result = subprocess.run(argv, cwd=root, env={**_base_env, 'DUCKWORK_HOME': str(root / 'tests' / '.suite-home'),
                                                         'WF_RUNS_ROOT': str(_suite_runs_root)},
                                    stdout=fh, stderr=subprocess.STDOUT, timeout=90)
        rc = result.returncode
    except subprocess.TimeoutExpired:
        rc = 124
    except Exception as exc:
        log.write_text(f'{type(exc).__name__}: {exc}\n')
        rc = 125
    rows.append({'test': name, 'exit': rc, 'log': str(log)})
    tmp = ledger.with_suffix('.tmp')
    tmp.write_text(json.dumps(rows, indent=2) + '\n')
    os.replace(tmp, ledger)
    print(f'{name}: {rc}', flush=True)
reds = {row['test']: row['exit'] for row in rows if row['exit'] != 0}
present = {row['test'] for row in rows}   # deleted-test detection (F1): executed set
adm = admission(None if base_reds is None else dict(base_reds), reds,
                baseline_path=_baseline_path, present=present)
tmp = (out / 'admission.json').with_suffix('.tmp')
tmp.write_text(json.dumps(adm, indent=2) + '\n')
os.replace(tmp, out / 'admission.json')
if adm['zero_discovery']:
    print(f'suite: zero cases discovered under {root / "tests"} — refusing green', flush=True)
print(f'TOTAL {len(rows)} FAIL {sum(row["exit"] != 0 for row in rows)}', flush=True)
if _baseline_path:
    print(f"ADMISSION introduced={len(adm['introduced'])} pre_existing={len(adm['pre_existing'])} "
          f"missing={len(adm['missing'])} fixed={len(adm['fixed'])} green={'true' if adm['green'] else 'false'}", flush=True)
raise SystemExit(1 if (any(row['exit'] != 0 for row in rows) or adm['missing'] or adm['zero_discovery']) else 0)
