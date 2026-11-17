#!/usr/bin/env python3
"""est-9yl2 — the committed CI baseline is load-bearing; guard its invariants.

Pins (issue #75 acceptance):
  (1) .github/workflows/ci.yml feeds the serial suite the committed ledger via
      --baseline ci-baseline/exits.json — without a baseline every red counts
      as introduced, so a lane's first hour goes back to re-proving
      "pre-existing, not mine".
  (2) ci-baseline/exits.json is a GREEN ledger: list of {test, exit} rows,
      unique names, every exit == 0, zero-discovery proof (count > 0). A red
      row may only ride as the known-red.json shape (per-red tracking link),
      never as a silent waiver — so any nonzero exit here is a fail.
  (3) ci-baseline/PROVENANCE.json exists, names the source commit/run, and its
      totals agree with the ledger (measured, not asserted).
  (4) The refresh contract is enforced BY the suite, not by prose: every
      test_*.py / test_*.mjs under tests/ must have a row in the ledger. A new
      test without a ledger row makes CI's `missing` admission block
      (suite.py F1: deleted/new tests are never laundered), so the baseline is
      refreshed from a green run whenever the suite set moves. This check
      fails at the SAME time as CI would, locally, with a legible reason.

Hermetic: reads files only; runs under the serial suite with stdlib.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails = 0
total = 0


def check(name, ok, detail=""):
    global fails, total
    total += 1
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    fails += 0 if ok else 1


# (1) CI wiring
ci = (ROOT / ".github" / "workflows" / "ci.yml")
if not ci.exists():
    check("ci.yml exists", False, str(ci))
else:
    text = ci.read_text()
    m = re.search(r"scripts/suite\.py\s+\S+\s+\S+\s+--baseline\s+(\S+)", text)
    check("ci.yml runs the serial suite with --baseline", m is not None, text[:200])
    baseline_rel = m.group(1) if m else "ci-baseline/exits.json"
    check("the wired baseline path is ci-baseline/exits.json",
          m is not None and baseline_rel == "ci-baseline/exits.json", str(baseline_rel))

    # (2) ledger shape
    led_path = ROOT / baseline_rel
    rows = None
    if not led_path.exists():
        check(f"baseline ledger exists at {baseline_rel}", False, "")
    else:
        try:
            rows = json.loads(led_path.read_text())
        except Exception as exc:
            check("baseline ledger parses as JSON", False, f"{type(exc).__name__}: {exc}")
        if rows is not None:
            ok_shape = (isinstance(rows, list) and rows
                        and all(isinstance(r, dict) and isinstance(r.get("test"), str)
                                and isinstance(r.get("exit"), int) for r in rows))
            check("ledger is a non-empty list of {test:str, exit:int} rows", ok_shape,
                  f"rows={len(rows) if isinstance(rows, list) else type(rows).__name__}")
            names = [r["test"] for r in rows]
            check("ledger test names are unique", len(names) == len(set(names)),
                  str(sorted({n for n in names if names.count(n) > 1})))
            reds = sorted(r["test"] for r in rows if r["exit"] != 0)
            check("ledger is fully green (every exit == 0) — red rows need the "
                  "known-red.json shape with a tracking link, never here",
                  not reds, str(reds[:5]))

            # (3) provenance agrees with the ledger — measured, not asserted
            prov_path = led_path.parent / "PROVENANCE.json"
            if not prov_path.exists():
                check("PROVENANCE.json exists beside the ledger", False, str(prov_path))
            else:
                try:
                    prov = json.loads(prov_path.read_text())
                except Exception as exc:
                    prov = None
                    check("PROVENANCE.json parses", False, f"{type(exc).__name__}: {exc}")
                if prov is not None:
                    check("PROVENANCE names the source commit",
                          bool(str(prov.get("captured_from", {}).get("commit", ""))),
                          str(prov.get("captured_from")))
                    t = prov.get("totals") or prov.get("captured_from", {}).get("totals", {})
                    check("PROVENANCE totals match the ledger (cases & zero reds)",
                          t.get("cases") == len(rows) and t.get("red") == 0,
                          f"prov={t} ledger_rows={len(rows)}")

                    # (4) refresh contract: the suite set == the ledger set
                    disk = sorted(p.name for p in (ROOT / "tests").glob("test_*.py")) + \
                          sorted(p.name for p in (ROOT / "tests").glob("test_*.mjs"))
                    disk = sorted(disk)
                    lset = set(names)
                    dset = set(disk)
                    new = sorted(dset - lset)      # would block CI as `missing`
                    stale = sorted(lset - dset)    # deleted tests (also `missing`)
                    check("every discovered test has a ledger row (else CI `missing` blocks; "
                          "refresh the ledger from a green run)",
                          not new, f"tests without rows: {new[:8]}")
                    check("no ledger row points at a deleted test",
                          not stale, f"rows without tests: {stale[:8]}")

print("DONE baseline_guard_9yl2", "OK" if fails == 0 else "FAIL")
sys.exit(0 if fails == 0 else 1)
