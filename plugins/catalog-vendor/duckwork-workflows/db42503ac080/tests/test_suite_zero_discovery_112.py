#!/usr/bin/env python3
"""#112 zero-discovery is a failed admission, never green: scripts/suite.py must
(1) validate the root BEFORE any out-dir side effects (missing root or missing
tests/ dir -> exit 2, no out/, no exits.json, no admission.json), (2) treat zero
cases discovered under a valid tests/ dir as a failed admission (exits.json ==
[], admission.json green=false + zero_discovery=true, nonzero exit), and (3)
keep the one-pass / one-fail controls and the missing-red protection intact.
Hermetic: throwaway trees of stub test files, run with sys.executable."""
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


def make_root(td, spec, empty=False):
    """spec: {test name: exit code}; a stub test that exits with that code.
    empty=True makes tests/ exist but hold no test_*.py files."""
    root = Path(td) / "root"
    (root / "tests").mkdir(parents=True)
    if not empty:
        for name, rc in spec.items():
            (root / "tests" / name).write_text(f"import sys\nsys.exit({rc})\n")
    return root


def run_suite(root, out, baseline=None):
    argv = [sys.executable, str(SUITE), str(root), str(out)]
    if baseline is not None:
        argv += ["--baseline", str(baseline)]
    r = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    adm = None
    adm_path = Path(out) / "admission.json"
    if adm_path.exists():
        adm = json.loads(adm_path.read_text())
    led = None
    led_path = Path(out) / "exits.json"
    if led_path.exists():
        led = json.loads(led_path.read_text())
    return r, adm, led


with tempfile.TemporaryDirectory(prefix="suite-zero-112-") as td:
    td = Path(td)

    # (a) missing root: exit 2 (invalid-invocation class), nothing created in out.
    miss_root = td / "nope" / "root"
    out_a = td / "out-a"
    ra, adm_a, led_a = run_suite(miss_root, out_a)
    check("(a) missing root exits nonzero", ra.returncode != 0, str(ra.returncode))
    check("(a) missing root exits 2 (invalid invocation)", ra.returncode == 2, str(ra.returncode))
    check("(a) invalid-root message names the root", "suite: invalid root" in ra.stdout, ra.stdout[-200:])
    check("(a) no out/ side effects on invalid root", not out_a.exists(), str(out_a))

    # (b) root exists but tests/ is absent: same contract.
    no_tests = td / "b" / "root"
    no_tests.mkdir(parents=True)
    out_b = td / "out-b"
    rb, adm_b, _ = run_suite(no_tests, out_b)
    check("(b) absent tests dir exits 2", rb.returncode == 2, str(rb.returncode))
    check("(b) absent tests dir prints invalid-root message", "suite: invalid root" in rb.stdout, rb.stdout[-200:])
    check("(b) no out/ side effects without tests dir", not out_b.exists(), str(out_b))

    # (c) empty tests dir: valid invocation, zero discovery -> failed admission.
    empty_root = make_root(td / "c", {}, empty=True)
    out_c = td / "out-c"
    rc_, adm_c, led_c = run_suite(empty_root, out_c)
    check("(c) zero discovery exits nonzero", rc_.returncode != 0, str(rc_.returncode))
    check("(c) zero discovery writes exits.json == []", led_c == [], str(led_c))
    check("(c) zero discovery writes admission.json", adm_c is not None)
    if adm_c:
        check("(c) admission green=false", adm_c["green"] is False, str(adm_c.get("green")))
        check("(c) admission zero_discovery=true", adm_c.get("zero_discovery") is True, str(adm_c.get("zero_discovery")))
    check("(c) zero-discovery message printed", "zero cases discovered" in rc_.stdout and "refusing green" in rc_.stdout,
          rc_.stdout[-200:])

    # (d) all-green baseline + empty discovery: green must stay false.
    green_root = make_root(td / "d-base", {"test_green.py": 0})
    base_out = td / "out-d-base"
    rd_base, _, led_d_base = run_suite(green_root, base_out)
    check("(d) all-green baseline run exits 0", rd_base.returncode == 0, str(rd_base.returncode))
    ledger_green = base_out / "exits.json"
    out_d = td / "out-d"
    rd, adm_d, _ = run_suite(empty_root, out_d, baseline=ledger_green)
    check("(d) all-green baseline + zero discovery exits nonzero", rd.returncode != 0, str(rd.returncode))
    if adm_d:
        check("(d) admission green=false despite all-green baseline", adm_d["green"] is False, str(adm_d.get("green")))
        check("(d) admission zero_discovery=true", adm_d.get("zero_discovery") is True, str(adm_d.get("zero_discovery")))
    else:
        check("(d) admission.json written", False, "missing")

    # (e) controls: one pass -> exit 0 green=true; one fail -> exit 1.
    pass_root = make_root(td / "e-pass", {"test_pass.py": 0})
    out_e1 = td / "out-e-pass"
    re1, adm_e1, _ = run_suite(pass_root, out_e1)
    check("(e) one passing stub exits 0", re1.returncode == 0, str(re1.returncode))
    check("(e) one passing stub green=true", bool(adm_e1) and adm_e1["green"] is True, str(adm_e1))
    fail_root = make_root(td / "e-fail", {"test_fail.py": 1})
    out_e2 = td / "out-e-fail"
    re2, adm_e2, _ = run_suite(fail_root, out_e2)
    check("(e) one failing stub exits 1", re2.returncode == 1, str(re2.returncode))
    check("(e) one failing stub green=false", bool(adm_e2) and adm_e2["green"] is False, str(adm_e2))

    # (f) negative control: a base red whose test is missing still fails (unchanged law).
    base_red_root = make_root(td / "f-base", {"test_red.py": 1})
    out_f_base = td / "out-f-base"
    run_suite(base_red_root, out_f_base)
    ledger_missing = out_f_base / "exits.json"
    rm_root = make_root(td / "f-rm", {}, empty=True)  # red deleted AND nothing discovered
    out_f = td / "out-f"
    rf, adm_f, _ = run_suite(rm_root, out_f, baseline=ledger_missing)
    check("(f) missing base red still fails (never launders to green)", rf.returncode != 0, str(rf.returncode))
    if adm_f:
        check("(f) missing base red reported missing", adm_f["missing"] == ["test_red.py"], str(adm_f.get("missing")))
        check("(f) missing base red green=false", adm_f["green"] is False)

    # (g) review F4: REUSED out-dir + invalid invocation must not leave a prior
    # green admission standing (#112 §1: 'none left green'). Prior green run into
    # OUT, then invalid root reusing the SAME OUT: exit 2, admission gone/non-green,
    # and out/ is never CREATED when it did not exist (covered fresh by (a)/(b)).
    green_root = make_root(td / "g-green", {"test_ok.py": 0})
    notests_root = td / "g-notests" / "root"
    notests_root.mkdir(parents=True)          # root exists, tests/ absent
    for variant, bad_root in (("missing-root", td / "g-missing" / "nope"),  # never created
                              ("no-tests", notests_root)):
        out_g = td / f"g-out-{variant}"
        rg, adm_g, led_g = run_suite(green_root, out_g)
        check(f"(g:{variant}) prior run green", bool(adm_g) and adm_g["green"] is True, str(adm_g))
        check(f"(g:{variant}) prior ledger non-empty", bool(led_g), str(led_g))
        # reuse the SAME out-dir with an invalid invocation
        ri, adm_i, led_i = run_suite(bad_root, out_g)
        check(f"(g:{variant}) invalid reuse exits 2", ri.returncode == 2, str(ri.returncode))
        check(f"(g:{variant}) prior admission NOT left green",
              adm_i is None or adm_i.get("green") is not True, str(adm_i))
        check(f"(g:{variant}) stale ledger invalidated", led_i is None or led_i == [], str(led_i))

    # (h) F4 belt: invalid invocation must never CREATE a fresh out/ (spec §1) —
    # asserted again here explicitly beside the (g) reuse family.
    fresh_out = td / "g-out-fresh"
    rh, _, _ = run_suite(td / "g" / "nope", fresh_out)
    check("(h) invalid invocation creates no out/ dir", not fresh_out.exists(), str(fresh_out))

print(f"TOTAL {total - fails} PASS {fails} FAIL", flush=True)
raise SystemExit(1 if fails else 0)
