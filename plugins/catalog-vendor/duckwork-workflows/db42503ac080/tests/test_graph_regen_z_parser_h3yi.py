#!/usr/bin/env python3
"""graph_regen diff parsing contract (est-h3yi).

scripts/graph_regen.py's graph_diff_files() used `git diff --name-only` +
splitlines — the same three holes PR #275 (est-gbim) closed in the ban
(graph_path_ban.changed_files): a rename collapses to the post-image, exotic
names come back octal-quoted (the quote breaks the `graphify-out/` prefix
match), and a path with an embedded newline forges a fake row on the split.
The fix factors ONE parser (`-z --name-status`, NUL-split, both R/C endpoints,
fail-closed to None) into graph_path_ban.diff_name_status_paths and makes
BOTH the ban and the regen answer their path questions through it.

RED witness (old read): case 1 lists only the rename POST-image — the emptied
pre-image vanishes from FILES; case 2 returns the octal-quoted `"graphify-out/
evil\\n.json"` instead of the real path and could forge rows; case 5 shows a
tracked change invisible to the pathspec'd read. Green requires every check;
the unit cases drive the parser directly with crafted field lists so the
fail-closed branch is proven, not asserted. (Rename pairs appear as R only
when both sides sit on the same diff side — a worktree delete+reappear reads
D|M, which is why the rename cases use committed ranges.)

Loaded via spec_from_file_location (repo convention; the shipped import-
closure gate #105 probes top-level imports from the unpacked root, where
scripts/ is not on sys.path — graph_regen resolves graph_path_ban by its own
directory, which this loading style still gets right).
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gr = _load("graph_regen_under_test", ROOT / "scripts" / "graph_regen.py")
gpb = _load("graph_path_ban_under_test_h3", ROOT / "scripts" / "graph_path_ban.py")

fails = 0
CLEAN_ENV = {k: v for k, v in os.environ.items()
             if k not in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME", "GITHUB_BASE_REF", "GITHUB_REF")}


def check(name, ok, detail=""):
    global fails
    if not ok:
        fails += 1
        print(f"FAIL: {name}" + (f" — {detail}" if detail else ""))
    else:
        print(f"ok: {name}")


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True, env=CLEAN_ENV).stdout


def commit_all(repo, msg):
    git(repo, "add", "-A")
    git(repo, "-c", "user.email=t@example.com", "-c", "user.name=Test",
        "commit", "-q", "-m", msg)


def fresh_repo(path):
    repo = Path(path)
    repo.mkdir(parents=True, exist_ok=True)
    (repo / "graphify-out").mkdir(exist_ok=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "Test")
    return repo


def main():
    tmp = Path(tempfile.mkdtemp(prefix="h3yi-"))
    try:
        # ---- unit: the shared parser's field walk, fail-closed branches ----
        p = gpb._name_status_paths
        check("unit: plain M/A records",
              p([b"M", b"x.py", b"A", b"graphify-out/y.json"]) == ["x.py", "graphify-out/y.json"])
        check("unit: R takes BOTH endpoints",
              p([b"R100", b"graphify-out/a.json", b"moved.json"])
              == ["graphify-out/a.json", "moved.json"])
        check("unit: C takes BOTH endpoints",
              p([b"C75", b"src.json", b"graphify-out/copy.json"])
              == ["src.json", "graphify-out/copy.json"])
        check("unit: embedded newline is ONE path, not two rows",
              p([b"A", b"graphify-out/evil\nfake.json"]) == ["graphify-out/evil\nfake.json"])
        check("unit: untrusted status token → None (fail closed)",
              p([b"WEIRD", b"x.py"]) is None)
        check("unit: truncated rename record → None",
              p([b"R100", b"only-one-endpoint.json"]) is None)
        check("unit: truncated plain record → None",
              p([b"M"]) is None)
        check("unit: empty field list → []",
              p([]) == [])

        # ---- (1) committed rename OUT of graphify-out/ over the rev range ----
        # git prints R100 only when both sides are on the same diff side; the
        # regen's caller commits with `git add graphify-out/`, so what matters
        # is: the emptied pre-image is LISTED (the old --name-only read showed
        # only the post-image) and the out-of-path post-image stays out of the
        # pathspec'd list (the regen must not report files it cannot own).
        repo = fresh_repo(tmp / "r1")
        body = json.dumps({"nodes": [{"name": f"n{i}"} for i in range(120)]})
        (repo / "graphify-out" / "graph.json").write_text(body)
        commit_all(repo, "base")
        shutil.move(str(repo / "graphify-out" / "graph.json"), str(repo / "moved.json"))
        commit_all(repo, "moved out")
        files = gr.graph_diff_files(repo)  # worktree clean vs HEAD → []
        check("baseline: clean tree reads []", files == [], f"got {files!r}")
        shared = gpb.diff_name_status_paths(repo, revs="HEAD~1..HEAD", pathspec="graphify-out/")
        check("rename-out: pre-image under graphify-out/ is listed",
              shared is not None and "graphify-out/graph.json" in shared,
              f"got {shared!r}")
        check("rename-out: pathspec keeps the foreign post-image out",
              shared is not None and "moved.json" not in shared,
              f"got {shared!r}")

        # ---- (2) embedded newline in a tracked graph path (working tree) ----
        # old read: octal-quoted "graphify-out/evil\\n.json" (prefix match dies
        # on the quote) and splitlines can forge rows; -z gives the raw path.
        repo2 = fresh_repo(tmp / "r2")
        nl_name = "graphify-out/evil\nfake.json"
        (repo2 / "graphify-out" / "evil\nfake.json").write_text('{"v": 1}\n')
        commit_all(repo2, "base-nl")
        (repo2 / "graphify-out" / "evil\nfake.json").write_text('{"v": 2}\n')
        files2 = gr.graph_diff_files(repo2)
        check("newline-path: the REAL path is listed verbatim",
              files2 is not None and nl_name in files2, f"got {files2!r}")
        check("newline-path: one entry, no forged row, no quoted artifact",
              files2 is not None and len(files2) == 1
              and not any("evil\\n" in f for f in files2),
              f"got {files2!r}")
        old2 = git(repo2, "diff", "--name-only", "--", "graphify-out/")
        check("RED witness: old read octal-quotes the path",
              old2.startswith('"'), f"old read={old2!r}")

        # ---- (3) tracked rename PAIR within the path over a rev range ----
        # THE hiding case: an in-path rename (regen re-emits graph.json's body
        # under a new name and deletes the old) is printed R100 on one side of
        # the diff; `--name-only` shows ONLY the post-image, so the emptied
        # file never reaches FILES and the caller's commit under-reports.
        repo3 = fresh_repo(tmp / "r3")
        big = json.dumps({"nodes": [{"name": f"m{i}"} for i in range(120)]})
        (repo3 / "graphify-out" / "a.json").write_text(big)
        (repo3 / "graphify-out" / "keep.json").write_text("k\n")
        commit_all(repo3, "base3")
        (repo3 / "graphify-out" / "new.json").write_text(big)
        (repo3 / "graphify-out" / "a.json").unlink()
        commit_all(repo3, "regen shuffle")
        pair = gpb.diff_name_status_paths(repo3, revs="HEAD~1..HEAD", pathspec="graphify-out/")
        check("rename-pair: BOTH endpoints of the in-path rename",
              pair is not None and "graphify-out/a.json" in pair
              and "graphify-out/new.json" in pair, f"got {pair!r}")
        old3 = [f for f in git(repo3, "diff", "--name-only", "HEAD~1..HEAD",
                               "--", "graphify-out/").splitlines() if f]
        check("RED witness: old --name-only hides the emptied pre-image",
              "graphify-out/a.json" not in old3,
              f"old read unexpectedly listed {old3!r}")

        # ---- (4) untracked new graph file still surfaces (ls-files half) ----
        (repo / "graphify-out" / "brand-new.json").write_text('{"new": true}\n')
        files = gr.graph_diff_files(repo)
        check("untracked: new graphify-out/ file joins the list",
              files is not None and "graphify-out/brand-new.json" in files,
              f"got {files!r}")

        # ---- (5) fail-closed at the git boundary ----
        nowhere = tmp / "not-a-repo"
        nowhere.mkdir()
        check("fail-closed: graph_diff_files on a non-repo → None",
              gr.graph_diff_files(nowhere) is None)
        check("fail-closed: shared parser on a non-repo → None",
              gpb.diff_name_status_paths(nowhere, revs="HEAD") is None)

        # ---- (6) single-parser law: ban + regen answer through the ONE fn ----
        src = (ROOT / "scripts" / "graph_regen.py").read_text()
        check("shared-parser: graph_regen's parser resolves to graph_path_ban.py",
              getattr(gr, "diff_name_status_paths", None) is not None
              and Path(gr.diff_name_status_paths.__code__.co_filename).resolve()
              == (ROOT / "scripts" / "graph_path_ban.py").resolve())
        check("shared-parser: no raw git-diff read left in graph_regen",
              '"--name-only"' not in src and '"--name-status"' not in src
              and '"diff"' not in src)
        ban_src = (ROOT / "scripts" / "graph_path_ban.py").read_text()
        check("shared-parser: graph_path_ban.changed_files delegates",
              gpb.changed_files(repo3, "HEAD~1", "HEAD") == ["graphify-out/a.json",
                                                              "graphify-out/new.json"])
        import inspect
        check("shared-parser: changed_files body calls the shared fn",
              "diff_name_status_paths" in inspect.getsource(gpb.changed_files)
              and '"-z"' not in inspect.getsource(gpb.changed_files))

        print("ALL PASS" if not fails else f"FAIL {fails}")
        sys.exit(1 if fails else 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
