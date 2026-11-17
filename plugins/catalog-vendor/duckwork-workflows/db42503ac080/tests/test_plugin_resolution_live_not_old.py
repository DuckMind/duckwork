#!/usr/bin/env python3
"""est-ujtf: respawn must pick the LIVE plugin copy, never an ARCHIVED one.

The incident (run 20261006-041852-fb-fix-fb609): the runner was respawned
07:27:11Z by s6-svscan (ppid 1) from
`~/.duckwork/plugins/duckwork-workflows.old-1.1.2-9073584/wf.py` — an archived
pre-update copy — instead of the live `~/.duckwork/plugins/duckwork-workflows`.
A respawn/discovery path that globs the plugins root for wf.py can land on
the archive and silently boot a stale engine.

Law pinned here (scripts/lane_recover.py's resolver, stdlib-only):
  * exact-name (or symlink-at-exact-name) `duckwork-workflows` carrying wf.py
    is picked whenever present — deterministically, ahead of every sibling;
  * a `*.old-*` sibling is NEVER a resolution result, in any case;
  * live dir absent (or wf.py-less) -> refuse with a clear error that names
    the archived copy(ies) it is refusing, never a silent fallback.

Plain script, no pytest: exits non-zero on the first red.
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FAILS = []


def check(name, cond, detail=None):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  ::  " + str(detail)[:600]))
    if not cond:
        FAILS.append(name)


def mkcopy(root_dir, name, symlink_to=None):
    d = Path(root_dir) / name
    if symlink_to is not None:
        d.symlink_to(Path(symlink_to))
    else:
        d.mkdir(parents=True, exist_ok=True)
    (d / "wf.py").write_text("# fake engine\n")
    (d / "__init__.py").write_text("# fake door\n")
    return d


def main():
    lr = load("lane_recover_ujtf", ROOT / "scripts" / "lane_recover.py")
    resolver = getattr(lr, "resolve_plugin_dir", None)
    check("resolver: scripts/lane_recover.py exposes resolve_plugin_dir",
          callable(resolver), "attribute missing")
    if not callable(resolver):
        print(f"FAILED: {FAILS}")
        sys.exit(1)
    err_type = getattr(lr, "PluginResolutionError", None)
    check("resolver: refuses with a typed PluginResolutionError",
          isinstance(err_type, type) and issubclass(err_type, Exception), err_type)

    with tempfile.TemporaryDirectory(prefix="ujtf-") as td:
        # A. live + archived sibling (the incident shape): live wins, deterministically.
        root = Path(td) / "plugins"
        mkcopy(root, "duckwork-workflows")
        mkcopy(root, "duckwork-workflows.old-1.1.2-9073584")
        got = resolver(root)
        check("A: live copy wins over the .old-1.1.2 archive",
              Path(got).name == "duckwork-workflows", str(got))
        check("A: the result never names an .old- path",
              ".old-" not in str(got), str(got))
        # determinism: repeated resolution is byte-identical
        check("A: resolution is deterministic across calls",
              str(resolver(root)) == str(got), f"{resolver(root)} vs {got}")

        # B. exact name is a SYMLINK to the live release: still the answer.
        root2 = Path(td) / "plugins2"
        mkcopy(root2, "releases/1.2.0")
        mkcopy(root2, "duckwork-workflows.old-1.1.2-9073584")
        (root2 / "duckwork-workflows").symlink_to(root2 / "releases" / "1.2.0")
        got2 = resolver(root2)
        check("B: symlink at the exact name resolves to the live release",
              Path(got2).name == "duckwork-workflows"
              and (Path(got2) / "wf.py").is_file(), str(got2))

        # C. ONLY the archived copy present: refuse, name it, never boot it.
        root3 = Path(td) / "plugins3"
        mkcopy(root3, "duckwork-workflows.old-1.1.2-9073584")
        refused = None
        try:
            refused = resolver(root3)
        except Exception as e:
            refused = e
        ok = isinstance(refused, Exception) or (err_type is not None
                                                and isinstance(refused, err_type))
        check("C: live-absent + only-.old- -> refuses (never returns the archive)",
              isinstance(refused, Exception), f"returned {refused!r}")
        msg = str(refused) if isinstance(refused, Exception) else ""
        check("C: refusal message names the archived copy",
              "duckwork-workflows.old-1.1.2-9073584" in msg, msg[:300])
        check("C: refusal message says the LIVE dir is absent",
              "live" in msg.lower() and "duckwork-workflows" in msg, msg[:300])

        # D. empty plugins root: a clear refusal, not a silent None.
        root4 = Path(td) / "plugins4"
        root4.mkdir()
        try:
            got4 = resolver(root4)
            check("D: empty root refuses", False, f"returned {got4!r}")
        except Exception as e:
            check("D: empty root refuses with a clear message",
                  "duckwork-workflows" in str(e), str(e)[:300])

        # E. exact-name dir without wf.py (broken install) is refused, not skipped-to-archive.
        root5 = Path(td) / "plugins5"
        d5 = root5 / "duckwork-workflows"
        d5.mkdir(parents=True)
        mkcopy(root5, "duckwork-workflows.old-1.1.2-9073584")
        try:
            got5 = resolver(root5)
            check("E: wf.py-less live dir -> refuse, never fall back to the archive",
                  False, f"returned {got5!r}")
        except Exception as e:
            check("E: wf.py-less live dir -> refuse, never fall back to the archive",
                  ".old-" in str(e) and "duckwork-workflows" in str(e), str(e)[:300])

    print(("ALL PASS" if not FAILS else f"FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
