#!/usr/bin/env python3
"""graph_regen.py — the single-writer knowledge-graph regen (issue #153).

Used by the ra-graph-regen graph (the bot-owned regen lane; same posture as the
release lane: everything lands as a PR, this script NEVER pushes and NEVER opens
the PR itself):

    python3 scripts/graph_regen.py --repo-dir <clone> --base-sha <main sha>

Contract:
  1. assert HEAD == base-sha (the caller cloned at the exact main sha; a moved
     main means the regen is based on stale source — abort so the graph retries);
  2. `graphify update <repo>` AST-only (GRAPHIFY_NO_LLM=1; no LLM, no network),
     then `scripts/graph_check.py --fix` rewrites graphify-out/ to the honest
     form (semantic memory carried per the graph_check policy);
  3. decide from `git diff -- graphify-out/`:
       empty diff  -> print NO_CHANGES, exit 0  (idempotent: no PR, self-healing);
       non-empty   -> print FILES + one path per line, exit 0 (the caller commits
                      the branch chore/graph-<sha7> with commit trailer
                      `graph-base: <sha>` and opens the ONE chore(graph): PR).

Exit codes: 0 = decision made (NO_CHANGES or FILES); 1 = aborted (HEAD != base
or the regen failed — caller must NOT open a PR); 2 = unusable inputs (no
graphify binary, no graph_check.py, not a git repo). Stdlib only.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Same-directory import (repo convention for script->script deps; see the
# spec_from_file_location note in tests/test_graph_single_writer_153.py — the
# shipped import-closure gate #105 does not resolve scripts/, so resolve this
# by the script's own directory, never by cwd).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from graph_path_ban import diff_name_status_paths  # noqa: E402  (shared -z parser)

GRAPH_OUT = "graphify-out/"


def build_parser():
    ap = argparse.ArgumentParser(
        description="single-writer knowledge-graph regen decision (issue #153)")
    ap.add_argument("--repo-dir", required=True,
                    help="clean clone at the exact main sha")
    ap.add_argument("--base-sha", required=True,
                    help="the main sha the clone was made at; HEAD must equal it")
    return ap


def _git(repo_dir, *args):
    return subprocess.run(["git", "-C", str(repo_dir), *args],
                          capture_output=True, text=True)


def head_sha(repo_dir):
    r = _git(repo_dir, "rev-parse", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else None


def graph_diff_files(repo_dir):
    """Tracked files under graphify-out/ with a working-tree diff vs HEAD, plus
    any untracked new files there (a first regen on a tree without a committed
    graph). Untracked dirs alone are not a diff, but graph_check gates that
    case: no committed graph is its exit-2, caught by regen()'s post-check.

    est-h3yi: the tracked half parses through the shared `-z --name-status`
    parser (graph_path_ban.diff_name_status_paths), NOT `--name-only` +
    splitlines. The old read had the same three holes PR #275 closed in the ban
    (est-gbim): renames inside graphify-out/ collapsed to the post-image (a
    rename OUT of the path hid the pre-image, so FILES/commit reporting lost a
    file that the caller's `git add graphify-out/` still removed), and
    octal-quoted/exotic names listed wrong or forged. The FILES list feeds the
    caller's commit, so a hidden pre-image is real damage even though
    graph_check remains the honesty gate. NUL-split, both R/C endpoints, and
    fail-closed: None on git failure or unparseable output — main() aborts,
    never opens a PR on a list it cannot trust."""
    files = diff_name_status_paths(repo_dir, pathspec=GRAPH_OUT)
    if files is None:
        return None
    r = _git(repo_dir, "ls-files", "--others", "--exclude-standard", "--", GRAPH_OUT)
    if r.returncode != 0:
        return None
    files += [f for f in r.stdout.splitlines() if f]
    return sorted(set(files))


def graph_check(repo_dir, fix=False):
    """Run the honesty gate; returns (exit_code, tail). 0 = honest."""
    env = {**os.environ, "GRAPHIFY_NO_LLM": "1"}
    argv = [sys.executable, "scripts/graph_check.py"] + (["--fix"] if fix else [])
    r = subprocess.run(argv, cwd=str(repo_dir), capture_output=True, text=True, env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def regen(repo_dir):
    """Run the regen steps in the repo. Returns (ok, tail, was_honest):
    was_honest = the COMMITTED graph already matched the source before the run
    (measured by a plain graph_check first). `graphify update --force` rewrites
    the tracked bytes into its raw build form (different formatting from
    graph_check's canonical write); graph_check --fix returns OK early without
    restoring when the committed graph is honest. A caller that then commits
    whatever git diff shows would land a phantom byte-only regen — the very
    churn #153 exists to kill — so the decision-maker needs the before-state."""
    rc0, _ = graph_check(repo_dir)
    was_honest = rc0 == 0
    env = {**os.environ, "GRAPHIFY_NO_LLM": "1"}
    r = subprocess.run(["graphify", "update", str(repo_dir), "--force"],
                       cwd=str(repo_dir), capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return False, (r.stdout + r.stderr)[-1500:], was_honest
    rc, tail = graph_check(repo_dir, fix=True)
    if rc != 0:
        return False, tail, was_honest
    return True, tail, was_honest


def restore_graph(repo_dir):
    """Undo working-tree dirt under graphify-out/ (git checkout HEAD -- ...)."""
    r = _git(repo_dir, "checkout", "HEAD", "--", GRAPH_OUT)
    return r.returncode == 0


def main(argv=None, env=None):
    args = build_parser().parse_args(argv)
    repo = Path(args.repo_dir).resolve()
    if not (repo / ".git").exists() and not (repo / "HEAD").exists():
        print(f"graph_regen: {repo} is not a git repo"); return 2
    if not shutil.which("graphify"):
        print("graph_regen: graphify not on PATH (uv tool install graphifyy)"); return 2
    if not (repo / "scripts" / "graph_check.py").is_file():
        print(f"graph_regen: no scripts/graph_check.py under {repo}"); return 2

    head = head_sha(repo)
    if head is None:
        print("graph_regen: cannot read HEAD"); return 2
    if head != args.base_sha:
        # main moved (or the clone was made at the wrong sha): the PR would be
        # based on stale source — abort and let the caller re-trigger.
        print(f"graph_regen: ABORT — HEAD {head} != base-sha {args.base_sha} "
              f"(main moved or wrong clone); do not open a PR")
        return 1

    ok, tail, was_honest = regen(repo)
    if not ok:
        print(f"graph_regen: ABORT — regen failed:\n{tail}")
        return 1
    rc, verify = graph_check(repo)          # post-fix verification: the written tree must be honest
    if rc != 0:
        print(f"graph_regen: ABORT — post-fix graph_check not OK (rc={rc}):\n{verify}")
        return 1

    files = graph_diff_files(repo)
    if files is None:
        print("graph_regen: ABORT — git diff failed"); return 1
    if was_honest:
        # The committed graph was honest BEFORE the run: graph_check --fix
        # early-returned without writing, so any bytes the in-place
        # `graphify update --force` left under graphify-out/ are its raw-build
        # re-formatting of the canonical committed file — a phantom diff.
        # Restore HEAD's bytes; reporting them as FILES would open a churn PR
        # (and a regen PR whose --fix diff is non-empty fails acceptance).
        if files and not restore_graph(repo):
            print("graph_regen: ABORT — could not restore graphify-out/"); return 1
    if not files or was_honest:
        print(f"graph_regen: graphify-out/ already honest at {head[:7]} — no PR needed")
        print("NO_CHANGES")
        return 0
    if any(not f.startswith(GRAPH_OUT) for f in files):
        print(f"graph_regen: ABORT — regen dirtied files outside {GRAPH_OUT}: "
              f"{[f for f in files if not f.startswith(GRAPH_OUT)][:5]}")
        return 1
    print(f"graph_regen: {len(files)} files changed under {GRAPH_OUT} at {head[:7]}")
    print("FILES")
    for f in files:
        print(f)
    print(f"graph_regen: caller opens ONE 'chore(graph): refresh at {head[:7]}' PR "
          f"from branch chore/graph-{head[:7]} containing ONLY these files, with "
          f"commit trailer 'graph-base: {args.base_sha}'. This script never pushes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
