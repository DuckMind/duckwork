#!/usr/bin/env python3
"""Version truth (est-2ek.1.159): pack.py stamps install.json provenance into the ZIP
root, and the door's doctor_version action flags live-vs-packaged drift in one read.

1) pack: a ZIP built from the tree carries install.json {version, source_commit,
   packaged_at} at the package root — with DUCKWORK_WF_PACK_COMMIT pinned (the test seam
   for a fake sha off-git) the bytes are exactly the pinned triple.
2) door: action=doctor_version on a fake plugin dir where plugin.yaml disagrees with
   install.json returns drift:true with the exact field set; agreement drift:false;
   a dir with no install.json reports null provenance, never a fabricated version.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VERSION = re.search(r"^version:\s*([\d.]+)", (ROOT / "plugin.yaml").read_text(), re.M).group(1)

BUILD = Path(os.environ.get("WF_TEST_BUILD") or HERE)
HOME = BUILD / "home-159"
os.environ["DUCKWORK_HOME"] = str(HOME)
os.environ["WF_RUNS_ROOT"] = str(HOME / "workflows")
shutil.rmtree(HOME, ignore_errors=True)
import importlib.util
spec = importlib.util.spec_from_file_location("hw159", str(BUILD.parent / "__init__.py"))
hw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hw)
import wf_test_isolation as _iso71; _iso71.install(hw)

ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("" if cond or not detail else f"  {detail}"))
    ok = ok and cond
def call(**a):
    return json.loads(hw.handle(a))

FAKE_SHA = "0" * 39 + "f"
EPOCH = "1757000000"

# ---------- 1) pack.py writes install.json provenance into the ZIP root ----------
with tempfile.TemporaryDirectory(prefix=".tmp-vt159-") as td:
    out = Path(td) / "pkg.zip"
    env = {**os.environ, "DUCKWORK_WF_PACK_COMMIT": FAKE_SHA, "SOURCE_DATE_EPOCH": EPOCH}
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/pack.py"), "--output", str(out)],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )
    check("V1 pack.py exits 0 with the provenance seams pinned",
          result.returncode == 0, result.stderr[-300:])
    root = f"duckwork-workflows-{VERSION}/"
    info = None
    blob = None
    if out.exists():
        with zipfile.ZipFile(out) as archive:
            names = archive.namelist()
            info = archive.getinfo(root + "install.json") if root + "install.json" in names else None
            blob = archive.read(root + "install.json") if info else None
    check("V2 install.json sits at the ZIP root next to SHA256SUMS", info is not None)
    if blob is not None:
        rec = json.loads(blob.decode("utf-8"))
        check("V3 install.json carries exactly {version, source_commit, packaged_at}",
              set(rec) == {"version", "source_commit", "packaged_at"}, repr(rec))
        check("V4 version is the manifest version verbatim", rec.get("version") == VERSION, repr(rec))
        check("V5 source_commit is the pinned fake sha verbatim",
              rec.get("source_commit") == FAKE_SHA, repr(rec.get("source_commit")))
        # Behavioral expectation, NOT a replay of pack.py's expression: the
        # pinned epoch renders in explicit UTC (zap review #198 — a host-TZ
        # conversion here would repeat the implementation's bug, as V6 did).
        expected_at = "2025-09-04T15:33:20+00:00"
        assert expected_at == datetime.fromtimestamp(int(EPOCH), timezone.utc).isoformat()
        check("V6 packaged_at is the pinned SOURCE_DATE_EPOCH rendered in explicit UTC",
              rec.get("packaged_at") == expected_at,
              f"{rec.get('packaged_at')!r} != {expected_at!r}")
    else:
        check("V3 install.json carries exactly {version, source_commit, packaged_at}", False, "no bytes")
        check("V4 version is the manifest version verbatim", False, "no bytes")
        check("V5 source_commit is the pinned fake sha verbatim", False, "no bytes")
        check("V6 packaged_at is the pinned SOURCE_DATE_EPOCH as ISO-8601", False, "no bytes")

    # provenance must not poison the checksum ledger: SHA256SUMS pins sources only,
    # and install.json itself must not be a self-referential row.
    if out.exists():
        with zipfile.ZipFile(out) as archive:
            sums = archive.read(root + "SHA256SUMS").decode("utf-8")
        check("V7 SHA256SUMS does not pin install.json (generated provenance, not a source)",
              "install.json" not in sums)

    # off-git: a malformed commit pin must never enter the archive raw — the sanitizer
    # refuses it and the git read answers instead (never an injected string).
    env_bad = {**os.environ, "DUCKWORK_WF_PACK_COMMIT": "not-a-sha; rm -rf /",
               "SOURCE_DATE_EPOCH": EPOCH}
    out2 = Path(td) / "pkg2.zip"
    result2 = subprocess.run(
        [sys.executable, str(ROOT / "scripts/pack.py"), "--output", str(out2)],
        cwd=ROOT, capture_output=True, text=True, env=env_bad,
    )
    check("V8 a malformed commit pin never enters the archive (falls back to git/unknown)",
          result2.returncode == 0 and out2.exists(), result2.stderr[-200:])
    if out2.exists():
        with zipfile.ZipFile(out2) as archive:
            rec2 = json.loads(archive.read(root + "install.json").decode("utf-8"))
        check("V9 malformed pin is refused in favour of the git read (never raw)",
              rec2.get("source_commit") != "not-a-sha; rm -rf /"
              and re.fullmatch(r"[0-9a-f]{40}|unknown", str(rec2.get("source_commit"))) is not None,
              repr(rec2.get("source_commit")))

    # ---------- 1b) cross-TZ regression (zap review #198) ----------
    # Identical HEAD, identical pinned seams, ONLY TZ differs: both packs must
    # agree on packaged_at (UTC) AND on the ZIP hash. The old implementation
    # converted through the host timezone and failed both assertions.
    def pack_under(tz_value, dest):
        env_tz = {**os.environ, "DUCKWORK_WF_PACK_COMMIT": FAKE_SHA,
                  "SOURCE_DATE_EPOCH": EPOCH, "TZ": tz_value}
        res = subprocess.run(
            [sys.executable, str(ROOT / "scripts/pack.py"), "--output", str(dest)],
            cwd=ROOT, capture_output=True, text=True, env=env_tz,
        )
        return res.returncode == 0 and dest.exists()

    out_utc = Path(td) / "pkg-tz-utc.zip"
    out_chi = Path(td) / "pkg-tz-chi.zip"
    ok_utc = pack_under("UTC", out_utc)
    ok_chi = pack_under("America/Chicago", out_chi)
    check("V10 cross-TZ: both TZ packs exit 0 and produce a ZIP",
          ok_utc and ok_chi)
    if ok_utc and ok_chi:
        import hashlib
        h_utc = hashlib.sha256(out_utc.read_bytes()).hexdigest()
        h_chi = hashlib.sha256(out_chi.read_bytes()).hexdigest()
        check("V11 cross-TZ: ZIP hash is TZ-invariant (host TZ cannot leak into bytes)",
              h_utc == h_chi, f"UTC {h_utc} != Chicago {h_chi}")
        at = {}
        for name, zp in (("UTC", out_utc), ("America/Chicago", out_chi)):
            with zipfile.ZipFile(zp) as archive:
                at[name] = json.loads(archive.read(root + "install.json")
                                       .decode("utf-8"))["packaged_at"]
        check("V12 cross-TZ: packaged_at is the UTC rendering under BOTH timezones",
              at["UTC"] == at["America/Chicago"] == "2025-09-04T15:33:20+00:00",
              repr(at))

# ---------- 2) the door's doctor_version flags live-vs-packaged drift ----------
check("D0 doctor_version is a registered action",
      "doctor_version" in hw.ACTIONS and "doctor_version" in
      hw.WORKFLOW_PARAMS["properties"]["action"]["enum"])

def fake_plugin_dir(tmp, live, packaged):
    d = Path(tmp) / f"seat-{live}-{packaged}"
    d.mkdir(parents=True)
    (d / "plugin.yaml").write_text(f"name: duckwork-workflows\nversion: {live}\n", encoding="utf-8")
    if packaged is not None:
        rec = {"version": packaged, "source_commit": "a" * 40,
               "packaged_at": "2026-10-01T00:00:00+00:00"}
        (d / "install.json").write_text(json.dumps(rec), encoding="utf-8")
    return d

with tempfile.TemporaryDirectory(prefix=".tmp-vt159door-") as td:
    drifted = fake_plugin_dir(td, "1.2.1", "1.2.0")
    out1 = call(action="doctor_version", plugin_dir=str(drifted))
    check("D1 drifted seat reports drift:true", out1.get("drift") is True, repr(out1))
    check("D2 exact field set {live_version, newest_packaged, source_commit, drift}",
          set(out1) == {"live_version", "newest_packaged", "source_commit", "drift"}, repr(out1))
    check("D3 live_version is the plugin.yaml bytes", out1.get("live_version") == "1.2.1", repr(out1))
    check("D4 newest_packaged is the install.json bytes",
          out1.get("newest_packaged") == "1.2.0", repr(out1))
    check("D5 source_commit passes through verbatim",
          out1.get("source_commit") == "a" * 40, repr(out1))

    agree = fake_plugin_dir(td, "1.2.1", "1.2.1")
    out2 = call(action="doctor_version", plugin_dir=str(agree))
    check("D6 an in-step seat reports drift:false",
          out2.get("drift") is False and out2.get("live_version") == "1.2.1"
          and out2.get("newest_packaged") == "1.2.1", repr(out2))

    naked = fake_plugin_dir(td, "1.2.1", None)
    out3 = call(action="doctor_version", plugin_dir=str(naked))
    check("D7 a seat with no install.json says null provenance, never invents a version",
          out3.get("newest_packaged") is None and out3.get("source_commit") is None
          and out3.get("live_version") == "1.2.1", repr(out3))

    missing = call(action="doctor_version", plugin_dir=str(Path(td) / "does-not-exist"))
    check("D8 a missing dir fails soft with an error, no traceback crash",
          "error" in missing, repr(missing))

    # default (no plugin_dir): the door reads its OWN package dir — one read, no args.
    own = call(action="doctor_version")
    check("D9 bare doctor_version reads the door's own package dir",
          set(own) == {"live_version", "newest_packaged", "source_commit", "drift"}
          and own["live_version"] == VERSION, repr(own))

print("ALL PASS" if ok else "FAILURES")
sys.exit(0 if ok else 1)
