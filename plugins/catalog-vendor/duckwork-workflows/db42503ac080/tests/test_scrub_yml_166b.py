#!/usr/bin/env python3
"""Committee wf166c A1-reopened: .yml was absent from AUDIT_SUFFIXES — a poisoned
.yml (the shipped .github/workflows/ci.yml IS one) exported with "0 scrub hits",
with OR without a NUL. The known-text suffix list must cover every text shape
the repo actually ships; an unrecognized extension that is plainly YAML (.yml)
is YAML.

Law pinned (adversary's acceptance recommendation):
  * .yml joins the known-text suffixes: forbidden line + NUL at 0/4096/8191 ->
    refused BEFORE export, naming file:line;
  * an ordinary-text .yml without NUL is audited too (the pre-fix skip was the
    whole blind spot);
  * controls unchanged: unknown-extension true binary (.dat) skips byte-
    identically; extensionless text stays audited (A1) and extensionless
    binary stays skipped.

Red-proof (run before the fix): the .yml probes exit 0 and export the forbidden
line; green: exit 1 naming adversary-probe.yml:3 and nothing exported.
"""
import shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent
SCRIPT = BUILD / "scripts" / "make_public.py"
OUT_ROOT = BUILD / "home-yml"
ok = True
def check(label, cond, detail=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (f"  {detail}" if detail and not cond else ""))
    ok = ok and bool(cond)

FORBIDDEN_LINE = 'haus-marcus-opus-sol  # credential-shaped marker for the audit'

def run_export(files, tag):
    """Build a minimal git repo holding `files` {rel: bytes}, run make_public,
    return (exit code, stdout+stderr, exported tree dict rel->bytes or None)."""
    src = OUT_ROOT / f"src-{tag}"; dst = OUT_ROOT / f"dst-{tag}"
    for d in (src, dst):
        shutil.rmtree(d, ignore_errors=True)
    src.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=src, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=src, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=src, check=True)
    (src / "README.md").write_text("# fixture\n")
    (src / "scripts").mkdir(exist_ok=True)
    # fixture-owned audit inputs: exactly one forbidden pattern, no guards — the
    # repo's real lists key their guards by real-repo line numbers and would
    # flag their own lines inside a fixture tree.
    (src / "scripts" / "scrub-list.txt").write_text("haus-marcus-opus-sol\n")
    # like the real repo: the audit INPUTS are guard-listed (their lines carry
    # the patterns by role) — only the probes stay unguarded.
    (src / "scripts" / ".scrub-guards").write_text("scripts/scrub-list.txt\n")
    for rel, payload in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_bytes(payload)
    subprocess.run(["git", "add", "-A"], cwd=src, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=src, check=True)
    p = subprocess.run([sys.executable, str(SCRIPT), str(dst), "--repo", str(src)],
                       capture_output=True, text=True)
    exported = None
    if p.returncode == 0 and dst.exists():
        exported = {str(f.relative_to(dst)): f.read_bytes()
                    for f in dst.rglob("*") if f.is_file() and ".git" not in f.parts}
    return p.returncode, p.stdout + p.stderr, exported

NUL_AT = (0, 4096, 8191)
for off in NUL_AT:
    body = ("a: 1\n" + "filler: x\n" * 3 + FORBIDDEN_LINE + "\n")
    payload = body.encode()
    payload = payload[:off] + b"\0" + payload[off:]
    rc, out, exp = run_export({"adversary-probe.yml": payload}, f"yml-nul{off}")
    check(f".yml with NUL@{off} + forbidden line is REFUSED before export",
          rc != 0 and "adversary-probe.yml:5" in out,
          f"rc={rc} out={out[:160]}")

rc, out, exp = run_export({"adversary-probe.yml": (FORBIDDEN_LINE + "\n").encode()}, "yml-plain")
check("ordinary-text .yml (no NUL) is audited too — the blind spot itself",
      rc != 0 and "adversary-probe.yml:1" in out, f"rc={rc} out={out[:160]}")

rc, out, exp = run_export({"adversary-probe.yml": "clean: true\n".encode()}, "yml-clean")
check("clean .yml still exports (audit, not ban)", rc == 0 and exp and "adversary-probe.yml" in exp,
      f"rc={rc} out={out[:160]}")

# controls: unknown-extension binary skips byte-identically; extensionless text audited
bin_payload = bytes(range(256)) * 4 + FORBIDDEN_LINE.encode() + b"\xff\xfe"
rc, out, exp = run_export({"adversary-probe.dat": bin_payload}, "dat-bin")
check("control: unknown-extension true binary skips byte-identically",
      rc == 0 and exp and exp.get("adversary-probe.dat") == bin_payload,
      f"rc={rc} exported={bool(exp and 'adversary-probe.dat' in (exp or {}))}")
rc, out, exp = run_export({"fake-textbin": (FORBIDDEN_LINE + "\n").encode()}, "extless-text")
check("control (A1): extensionless TEXT stays audited", rc != 0 and "fake-textbin:1" in out,
      f"rc={rc} out={out[:160]}")

# .txt — the wf166c adversary's unaudited-text census named mac-source.txt:
# same class, same law: shipped known-text shapes are ALWAYS audited.
rc, out, exp = run_export({"adversary-probe.txt": b"\0" + (FORBIDDEN_LINE + "\n").encode()},
                         "txt-nul0")
check(".txt with NUL@0 + forbidden line is REFUSED before export",
      rc != 0 and "adversary-probe.txt:1" in out, f"rc={rc} out={out[:160]}")

# .sig — the wf166d adversary's reproducible gap (B2): the SHIPPED
# graphify-out/.graphify_labels.json.sig is plain NUL-free UTF-8 JSON (od -c:
# starts `{"0": "c55709b2...`), not base64/minisign material — a text shape the
# repo ships, so it belongs in AUDIT_SUFFIXES, never the skip path. A poisoned
# copy must refuse export exactly like every other known-text shape.
rc, out, exp = run_export({"adversary-probe.sig": (FORBIDDEN_LINE + "\n").encode()}, "sig-plain")
check(".sig with forbidden line REFUSED before export (shipped .sig is plain JSON)",
      rc != 0 and "adversary-probe.sig:1" in out, f"rc={rc} out={out[:160]}")
rc, out, exp = run_export({"adversary-probe.sig": b"\x00" + (FORBIDDEN_LINE + "\n").encode()},
                         "sig-nul0")
check(".sig with NUL@0 + forbidden line is REFUSED (NUL cannot exempt a known suffix)",
      rc != 0 and "adversary-probe.sig:1" in out, f"rc={rc} out={out[:160]}")
rc, out, exp = run_export({"adversary-probe.sig": b'{"0": "deadbeef"}\n'}, "sig-clean")
check("clean .sig still exports (audit, not ban)",
      rc == 0 and exp and "adversary-probe.sig" in exp,
      f"rc={rc} exported={bool(exp and 'adversary-probe.sig' in (exp or {}))}")

print("DONE test_scrub_yml_166b", "OK" if ok else "FAIL")
sys.exit(0 if ok else 1)
