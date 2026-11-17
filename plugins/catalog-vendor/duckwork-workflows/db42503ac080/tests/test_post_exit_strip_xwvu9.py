"""est-xwvu9: the shipped/catalog build must not carry the post_exit_hook mechanism.

Upstream duckwork-agent PR #133387 review 5467148429 asked for the launchctl
post-exit node-script registration (a4dbd51 / #261 nightly-#261 mechanism) to
be stripped from anything we ship; we publicly accepted the ask in reply
6079245885. This is the RED->GREEN strip gate:
  (a) post_exit_hook.py is absent from the shipped tree AND from the release ZIP,
  (b) wf.py carries no post_exit_hook reference at all,
  (c) the dispatch block (dispatch + post_exit_handoff sweep) is gone.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_pack():
    spec = importlib.util.spec_from_file_location("pack_xwvu9", ROOT / "scripts/pack.py")
    assert spec is not None and spec.loader is not None
    pack = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pack)
    return pack


class PostExitStripTest(unittest.TestCase):
    def test_module_absent_from_shipped_tree(self):
        # (a) The runner imports it by bare name from the package root — if the
        # file is in the tree it is shipped, so the tree itself must be clean.
        self.assertFalse((ROOT / "post_exit_hook.py").exists(),
                         "post_exit_hook.py still sits in the shipped tree root")
        pack = _load_pack()
        with tempfile.TemporaryDirectory(prefix="pack-xwvu9-") as tmp:
            archive = Path(tmp) / "release.zip"
            pack.build(archive)
            with zipfile.ZipFile(archive) as z:
                prefix = pack.PACKAGE_NAME + "/"
                members = {name.removeprefix(prefix) for name in z.namelist()}
        self.assertNotIn("post_exit_hook.py", members,
                         "post_exit_hook.py still rides in the release ZIP")
        for member in sorted(m for m in members if m.startswith("tests/")):
            self.assertNotIn("post_exit_hook", member,
                             f"shipped test for the stripped mechanism: {member}")

    def test_wf_py_has_no_post_exit_reference(self):
        # (b) A bare-name import anywhere in the runner re-arms the mechanism.
        text = (ROOT / "wf.py").read_text(encoding="utf-8")
        self.assertNotIn("post_exit_hook", text,
                         "wf.py still references post_exit_hook")

    def test_dispatch_block_removed(self):
        # (c) The dispatch call and its handoff-only child sweep are gone.
        text = (ROOT / "wf.py").read_text(encoding="utf-8")
        self.assertNotIn("dispatch_post_exit_hook", text)
        self.assertNotIn("post_exit_handoff", text,
                         "the handoff-only _runner_term_cleanup call survived the strip")


if __name__ == "__main__":
    unittest.main()
