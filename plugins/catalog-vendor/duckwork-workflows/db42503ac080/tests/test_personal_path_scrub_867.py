#!/usr/bin/env python3
"""est-2ek.1.867 — the publish audit must SEE personal absolute paths (R9 gap).

The shape this pins: a shipped test module carried an unnecessary incident
narrative containing a real personal home path; the merged scrub audit
(scripts/make_public.py + scripts/scrub-list.txt) reported zero hits while the
prose survived BOTH the public export and the built source ZIP. A green scrub
was not sufficient evidence for R9: the audit simply had no personal-path
category. Two parts, standalone (no pytest), house style:

1. DETECTION (fixture repo): a shipped test file carrying a personal
   home-path incident narrative makes scripts/make_public.py's OWN audit exit
   nonzero — the category exists, and no guard silences it.
2. CLEANLINESS (this repo): the real export build passes, and the packed
   source ZIP (scripts/pack.py) contains ZERO personal-path hits in any
   member — the ZIP is audited with the same regex the export audit uses,
   independently of the guard list, because pack.py has never run the audit
   at all (the second half of the shipped-byte gap).
"""
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MAKE_PUBLIC = ROOT / "scripts" / "make_public.py"
PACK = ROOT / "scripts" / "pack.py"

ok = True


def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL " if cond is not None else "SKIP ") + label
          + ("" if cond or not detail else f"  {detail}"))
    ok = ok and bool(cond)


# The personal-path category, written independently of the committed list on
# purpose: pinning the SHIPPED behaviour means restating the shape here, so a
# future edit that drops the category from scripts/scrub-list.txt cannot
# vacuously green this test (the dropped category fails the detection half,
# and the cleanliness half keeps enforcing the shipped ZIP bytes).
PERSONAL_PATH = re.compile(r"(?:/home|/Users)/(?:duckwork|[A-Za-z0-9._-]{2,})/\.duckwork(?:/|\b)")

# ---- 1. detection: the audit catches the shipped-prose shape -----------------
# Built at runtime, never as one literal byte: this file SHIPS inside the
# pack ZIP, and the cleanliness half below audits every member — embedding a
# verbatim estate path here would make this test its own offender (the exact
# category it audits). Assembly keeps the bytes neutral while the fixture
# still leaks the real shape.
_LEAK_USER = "duckwork"
_LEAK_PATH = "/home/" + _LEAK_USER + "/" + ".duckwork" + "/workflows"

LEAKY_DOCSTRING = (
    '"""pin for 199.\n\n'
    'Postmortem (incident 20260927-082306-fb-fix-cef3acf6): a door launched via an\n'
    'importlib import returned a run_id whose dir never landed under the durable\n'
    f'root ({_LEAK_PATH}) — neighbours intact, cause unknown.\n"""\n'
    "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertTrue(True)\n"
)


def run_make_public(src, dst):
    return subprocess.run(
        [sys.executable, str(MAKE_PUBLIC), str(dst), "--repo", str(src)],
        capture_output=True, text=True)


with tempfile.TemporaryDirectory(prefix="personal-scrub-867-") as td:
    base = Path(td)
    src = base / "src"
    dst = base / "dst"
    src.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=src, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=src, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=src, check=True)
    (src / "README.md").write_text("# fixture\n")
    (src / "scripts").mkdir(exist_ok=True)
    # fixture-owned audit inputs: the repo's COMMITTED scrub-list verbatim —
    # detection therefore pins that the shipped list actually carries the
    # personal-path category (drop it upstream and this check REDs). The
    # list guards itself (same contract as the real repo: every line of the
    # audit INPUT is a forbidden pattern by role); the leaky probe stays
    # UNGARDED — a personal home path in shipped prose must have no guard
    # exemption available to it.
    committed = (ROOT / "scripts" / "scrub-list.txt").read_text(encoding="utf-8")
    (src / "scripts" / "scrub-list.txt").write_text(committed)
    (src / "scripts" / ".scrub-guards").write_text(
        "# audit inputs guard themselves, verbatim\nscripts/scrub-list.txt\n")
    leaky = src / "tests" / "test_incident_prose_199.py"
    leaky.parent.mkdir(exist_ok=True)
    leaky.write_text(LEAKY_DOCSTRING, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=src, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=src, check=True)

    r = run_make_public(src, dst)
    check("audit catches a personal home-path incident narrative (exit nonzero)",
          r.returncode != 0, f"rc={r.returncode} out={r.stdout[:200]}")
    check("the offender is reported as file:line of the leaky test",
          "test_incident_prose_199.py" in (r.stdout + r.stderr),
          (r.stdout + r.stderr)[:300])

    # control: the same file with the narrative reduced to the neutral shape
    # (no personal home path) exports clean — the gate bites the prose, not
    # the whole test-shipping pattern.
    leaky.write_text('"""pin for 199 — durable launch shape, neutral prose."""\n'
                     "import unittest\n\n\nclass T(unittest.TestCase):\n"
                     "    def test_x(self):\n        self.assertTrue(True)\n",
                     encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=src, check=True)
    subprocess.run(["git", "commit", "-qm", "neutral"], cwd=src, check=True)
    dst2 = base / "dst2"
    r2 = run_make_public(src, dst2)
    check("neutral narrative exports clean (the gate is category-scoped)",
          r2.returncode == 0 and "0 scrub hits" in r2.stdout,
          f"rc={r2.returncode} {r2.stdout[:150]} {r2.stderr[:150]}")

# ---- 2. cleanliness of THIS repo's two public artefacts ----------------------
with tempfile.TemporaryDirectory(prefix="personal-export-867-") as td:
    r = run_make_public(ROOT, Path(td) / "public-tree")
    check("this repo's real export build passes the merged audit",
          r.returncode == 0, f"rc={r.returncode}\n{r.stdout[-400:]}\n{r.stderr[-800:]}")

with tempfile.TemporaryDirectory(prefix="personal-zip-867-") as td:
    zpath = Path(td) / "package.zip"
    pr = subprocess.run([sys.executable, str(PACK), "--output", str(zpath)],
                        cwd=ROOT, capture_output=True, text=True)
    check("pack.py builds", pr.returncode == 0, f"rc={pr.returncode} {pr.stderr[-300:]}")
    if pr.returncode == 0:
        with zipfile.ZipFile(zpath) as zf:
            offenders = []
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                data = zf.read(name)
                if b"\0" in data[:8192]:
                    continue
                for i, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
                    if PERSONAL_PATH.search(line):
                        offenders.append(f"{name}:{i}")
            check("packed source ZIP carries ZERO personal home paths (any member)",
                  not offenders, "; ".join(offenders[:10]))

print("DONE personal_path_scrub_867", "OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
