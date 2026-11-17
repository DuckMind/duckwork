#!/usr/bin/env python3
"""#17 pass-gate admission contract: scripts/suite.py --baseline <ledger> must
split reds into EXACT identities (test name + exit code): introduced vs
pre-existing, write admission.json, keep a fully-green integrated SHA as the
only green, never waive a base red, and hard-fail (2) on an unusable baseline.
Hermetic: throwaway trees of stub test files, run with sys.executable."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "scripts" / "suite.py"
fails = 0


def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    fails += 0 if ok else 1


def make_root(td, spec):
    """spec: {test name: exit code}; a stub test that exits with that code."""
    root = Path(td) / "root"
    (root / "tests").mkdir(parents=True)
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
    return r, adm


with tempfile.TemporaryDirectory(prefix="suite-admission-") as td:
    td = Path(td)

    # base: one pre-existing red; fix: keeps it AND introduces a new red.
    base_root = make_root(td / "base", {"test_green.py": 0, "test_base_red.py": 1})
    base_out = td / "out-base"
    rb, _ = run_suite(base_root, base_out)
    check("base run without --baseline still exits 1 on red", rb.returncode == 1, str(rb.returncode))
    ledger_b = base_out / "exits.json"
    check("base run writes exits.json ledger", ledger_b.exists())

    fix_root = make_root(td / "fix", {"test_green.py": 0, "test_base_red.py": 1, "test_new_red.py": 1})
    fix_out = td / "out-fix"
    rf, adm = run_suite(fix_root, fix_out, baseline=ledger_b)
    check("fix run with reds exits 1 (never auto-waived)", rf.returncode == 1, str(rf.returncode))
    check("admission.json written", adm is not None)
    if adm:
        check("introduced carries ONLY the new red (exact identities)",
              adm["introduced"] == ["test_new_red.py"], str(adm["introduced"]))
        check("pre-existing carries ONLY the base red",
              adm["pre_existing"] == ["test_base_red.py"], str(adm["pre_existing"]))
        check("base red is blocking, never waived",
              adm["blocking_base_reds"] == ["test_base_red.py"], str(adm.get("blocking_base_reds")))
        check("green is false while any red stands (fully-green SHA only)",
              adm["green"] is False)
        check("reds capture exit identities", adm["reds"] == {"test_base_red.py": 1, "test_new_red.py": 1},
              str(adm["reds"]))
        check("fixed empty here", adm["fixed"] == [], str(adm["fixed"]))
        check("baseline path recorded", adm["baseline"] == str(ledger_b.resolve()), str(adm["baseline"]))
    check("stdout prints ADMISSION line", "ADMISSION introduced=1 pre_existing=1" in rf.stdout, rf.stdout[-200:])

    # a base red that the fix repairs, everything else green -> green true, exit 0
    fixed_root = make_root(td / "fixed", {"test_green.py": 0, "test_base_red.py": 0})
    fixed_out = td / "out-fixed"
    rg, admf = run_suite(fixed_root, fixed_out, baseline=ledger_b)
    check("fully-green integrated SHA exits 0", rg.returncode == 0, str(rg.returncode))
    if admf:
        check("repairing the base red reports it as fixed", admf["fixed"] == ["test_base_red.py"], str(admf.get("fixed")))
        check("fully-green SHA reports green true", admf["green"] is True)
    else:
        check("admission.json written on green run too", False, "missing")

    # same test, DIFFERENT exit code on the fix = introduced, not pre-existing
    d2 = make_root(td / "diff2", {"test_green.py": 0, "test_base_red.py": 1})
    # ledger says exit 1; fix run exits 2 -> identity mismatch
    (d2 / "tests" / "test_base_red.py").write_text("import sys\nsys.exit(2)\n")
    rd = td / "out-diff"
    r2, adm2 = run_suite(d2, rd, baseline=ledger_b)
    if adm2:
        check("same test failing with a DIFFERENT exit code counts as introduced",
              adm2["introduced"] == ["test_base_red.py"] and adm2["pre_existing"] == [],
              str({k: adm2[k] for k in ("introduced", "pre_existing")}))
    else:
        check("admission.json written (exit-identity case)", False, "missing")

    # no baseline at all: every red is introduced (no evidence it pre-existed)
    nb_root = make_root(td / "nb", {"test_green.py": 0, "test_red.py": 1})
    nb_out = td / "out-nb"
    rn, admn = run_suite(nb_root, nb_out)
    if admn:
        check("without --baseline every red is introduced",
              admn["introduced"] == ["test_red.py"] and admn["pre_existing"] == [],
              str({k: admn[k] for k in ("introduced", "pre_existing")}))
        check("without --baseline baseline is null", admn["baseline"] is None)
    else:
        check("admission.json written even without --baseline", False, "missing")

    # review F1: a base red whose TEST FILE IS DELETED is `missing`, not fixed —
    # `rm` must never launder a base red into a green gate.
    rm_root = make_root(td / "rm", {"test_green.py": 0})   # test_base_red.py gone
    rm_out = td / "out-rm"
    rrm, admr = run_suite(rm_root, rm_out, baseline=ledger_b)
    check("deleting a base red exits 1 (never launders to green)", rrm.returncode == 1, str(rrm.returncode))
    if admr:
        check("deleted base red reports missing", admr["missing"] == ["test_base_red.py"], str(admr.get("missing")))
        check("deleted base red lands in blocking_base_reds",
              admr["blocking_base_reds"] == ["test_base_red.py"], str(admr.get("blocking_base_reds")))
        check("deleted base red is NOT fixed", admr["fixed"] == [], str(admr.get("fixed")))
        check("green false while a base red is missing", admr["green"] is False)
    else:
        check("admission.json written on deleted-red run", False, "missing")

    # review F2: base_reds carries RED identities only; full map rides as base_exits
    if adm:
        check("base_reds is red-only; base_exits carries the full baseline map",
              adm["base_reds"] == {"test_base_red.py": 1}
              and adm["base_exits"] == {"test_green.py": 0, "test_base_red.py": 1},
              str({k: adm.get(k) for k in ("base_reds", "base_exits")}))

    # unusable baseline is a hard error, never a silent fallback
    bad = td / "bad-ledger.json"
    bad.write_text("{not json")
    rbad, _ = run_suite(nb_root, td / "out-bad", baseline=bad)
    check("malformed baseline hard-fails with exit 2", rbad.returncode == 2, str(rbad.returncode))
    check("malformed baseline names the problem", "baseline ledger unusable" in rbad.stdout, rbad.stdout[-200:])

    # missing path after --baseline -> exit 2
    rmiss, _ = run_suite(nb_root, td / "out-miss", baseline=td / "no-such-dir" / "exits.json")
    check("nonexistent baseline hard-fails with exit 2", rmiss.returncode == 2, str(rmiss.returncode))

print(f"{'OK' if fails == 0 else 'FAILED'} test_suite_admission_17 ({fails} failing)")
raise SystemExit(1 if fails else 0)
