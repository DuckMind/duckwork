"""Check that bundled Render files still match the recorded upstream snapshot."""

# Standard-library tools read files, hash their contents, and report a useful exit status.
import hashlib
import json
from pathlib import Path


def main():
    """Read the source record and compare every bundled file without using the network."""
    root = Path(__file__).resolve().parents[1]
    source = json.loads((root / "upstream.json").read_text())
    expected = source["files"]
    # Check both file contents and membership so missing or extra files cannot go unnoticed.
    actual = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (root / "skills").rglob("*") if path.is_file()}
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    changed = sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])
    # The report contains filenames and the public source revision, never credentials.
    result = {"ok": not (missing or extra or changed), "source_revision": source["revision"],
              "skills": len(list((root / "skills").glob("*/SKILL.md"))), "files": len(actual),
              "missing": missing, "extra": extra, "changed": changed}
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


# Running this file checks the package; importing it does not read or change anything.
if __name__ == "__main__":
    raise SystemExit(main())
