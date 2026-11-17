#!/usr/bin/env python3
"""A refused suite invocation must invalidate the durable receipts it leaves behind.
Contract (audit M11 — extending #112's F4 law from the invalid-root path to the
--baseline fail path): a passing invocation writes green admission.json +
exits.json; a SECOND invocation reusing the same out-dir that is refused
(malformed baseline, missing baseline file, invalid root) exits 2 and must leave
NO current successful receipt — a consumer reading only admission.json must not
mistake a prior run's green for this invocation's proof. Guards: a fresh refused
invocation still creates no out/; the legit --baseline <file> flow where the
baseline lives in (or is copied from) the out-dir still classifies; ordinary
pass/fail behavior is byte-unchanged. Hermetic stub trees, sys.executable."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "scripts" / "suite.py"
fails = 0
total = 0


def check(name, ok, detail=""):
    global fails, total
    total += 1
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    fails += 0 if ok else 1


def run_suite(root, out, baseline=None):
    argv = [sys.executable, str(SUITE), str(root), str(out)]
    if baseline is not None:
        argv += ["--baseline", str(baseline)]
    r = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    adm = led = None
    adm_path = Path(out) / "admission.json"
    if adm_path.exists():
        adm = json.loads(adm_path.read_text())
    led_path = Path(out) / "exits.json"
    if led_path.exists():
        led = json.loads(led_path.read_text())
    return r, adm, led


with tempfile.TemporaryDirectory(prefix="suite-stale-m11-") as td:
    td = Path(td)
    root = td / "root"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_pass.py").write_text("import sys\nsys.exit(0)\n")

    # Seed: a passing invocation writes green receipts.
    out = td / "out"
    r0, adm0, led0 = run_suite(root, out)
    check("seed: green invocation exits 0 with green admission",
          r0.returncode == 0 and adm0 and adm0["green"] is True,
          f"rc={r0.returncode} adm={adm0}")

    # (1) malformed baseline in a REUSED out-dir: exit 2, no surviving green.
    bad = td / "bad.json"
    bad.write_text("this is not json")
    r1, adm1, led1 = run_suite(root, out, baseline=bad)
    check("malformed baseline exits 2", r1.returncode == 2, str(r1.returncode))
    check("malformed baseline leaves no admission.json", adm1 is None, str(adm1))
    check("malformed baseline leaves no exits.json", led1 is None, str(led1))

    # (2) missing baseline file: same law.
    r2, adm2, led2 = run_suite(root, out, baseline=td / "nope.json")
    check("missing baseline exits 2", r2.returncode == 2, str(r2.returncode))
    check("missing baseline leaves no admission.json", adm2 is None, str(adm2))
    check("missing baseline leaves no exits.json", led2 is None, str(led2))

    # (3) invalid ROOT against a reused out-dir: exit 2, receipts invalidated
    # (this half worked pre-fix; pinned so it cannot regress with the refactor).
    r3, adm3, led3 = run_suite(td / "nope" / "root", out)
    check("invalid root exits 2", r3.returncode == 2, str(r3.returncode))
    check("invalid root leaves no admission.json", adm3 is None, str(adm3))
    check("invalid root leaves no exits.json", led3 is None, str(led3))

    # (4) FRESH refused invocation creates no out/ at all.
    fresh = td / "fresh-out"
    r4, _, _ = run_suite(root, fresh, baseline=bad)
    check("fresh refused invocation creates no out/", not fresh.exists(), str(fresh))

    # (5) legit flow preserved: baseline read from a file (including one that
    # previously sat in the out-dir) classifies normally after a re-run.
    base_out = td / "base-out"
    rb, admb, ledb = run_suite(root, base_out)
    ledger = base_out / "exits.json"
    copy = td / "ledger-copy.json"
    copy.write_text(ledger.read_text())
    r5, adm5, led5 = run_suite(root, base_out, baseline=copy)
    check("valid baseline reuse from copied ledger exits 0, green",
          r5.returncode == 0 and adm5 and adm5["green"] is True,
          f"rc={r5.returncode} adm={adm5}")
    r6, adm6, _ = run_suite(root, base_out, baseline=base_out / "exits.json")
    check("in-place out-dir ledger as baseline still runs green",
          r6.returncode == 0 and adm6 and adm6["green"] is True,
          f"rc={r6.returncode} adm={adm6}")

    # (6) ordinary behavior unchanged: a failing test still writes red receipts.
    (root / "tests" / "test_fail.py").write_text("import sys\nsys.exit(1)\n")
    r7, adm7, led7 = run_suite(root, out)
    check("red test still writes ledger + non-green admission, exit nonzero",
          r7.returncode != 0 and adm7 and adm7["green"] is False
          and led7 and any(row["exit"] == 1 for row in led7),
          f"rc={r7.returncode}")

print(f"\n{total - fails}/{total} checks pass")
sys.exit(1 if fails else 0)
