#!/usr/bin/env python3
"""graph_path_ban.py — PR branches do not touch the knowledge graph (single-writer, #153).

graphify-out/ is a committed derived artifact with exactly ONE writer: the main-owned
regen lane (scripts/graph_regen.py via the ra-graph-regen graph, which opens a
chore(graph): PR). Every other PR is forbidden from the path: an author-side regen
was the r10 pattern that made every two open PRs collide on cosmetic graph churn.

The ban: base = `git merge-base origin/<base-ref> HEAD` (default main; CI passes
the event's base_ref), changed = `git diff -z --name-status base..HEAD` parsed
into every path the diff touches (est-gbim: BOTH endpoints of renames/copies,
NUL-split so quoting and embedded newlines cannot hide an entry). Non-empty
graphify-out/ slice → exit 1 printing the offending files, UNLESS the head branch
matches ^chore/graph- AND every changed file lives under graphify-out/ — the regen
lane's own PR shape (branch chore/graph-<sha7>, ONLY graphify-out/ files). A
mixed PR that claims the exempt branch prefix but also edits source is not a
regen PR and fails.

The core decision is split from argv (build_parser / head_branch / changed_files /
ban_decision) so tests/test_graph_single_writer_153.py can unit-test the semantics
directly and drive the CLI against a temp clone. Stdlib only.

  exit 0  no graphify-out/ paths in the PR diff (or an exempt regen-lane PR)
  exit 1  the diff touches graphify-out/ outside the regen lane — file list printed
  exit 2  git failed (not a repo, base-ref unknown) — the gate fails closed
"""
import argparse
import os
import re
import subprocess
import sys

GRAPH_OUT_PREFIX = "graphify-out/"
EXEMPT_BRANCH_RE = re.compile(r"^chore/graph-")


def exempt_branch(branch):
    """True only for the regen lane's own branch pattern ^chore/graph-."""
    return bool(EXEMPT_BRANCH_RE.match(branch or ""))


def ban_decision(changed, branch, *, graphify_out_prefix=GRAPH_OUT_PREFIX):
    """Pure decision. `changed` = every path changed base..HEAD (all paths, not
    only the graph path). Returns None when the PR is exempt (regen lane: branch
    matches AND the whole diff lives under the graph prefix — that is exactly the
    shape scripts/graph_regen.py's caller is allowed to open), else the list of
    offending graphify-out/ paths (empty list = clean, no ban triggered)."""
    graph_touched = [f for f in changed if f.startswith(graphify_out_prefix)]
    if not graph_touched:
        return []
    if exempt_branch(branch) and all(f.startswith(graphify_out_prefix) for f in changed):
        return None
    return graph_touched


def _git(repo_dir, *args):
    return subprocess.run(["git", "-C", str(repo_dir), *args],
                          capture_output=True, text=True)


def merge_base(repo_dir, base_ref):
    """base = git merge-base origin/<base-ref> HEAD (None if git failed)."""
    r = _git(repo_dir, "merge-base", f"origin/{base_ref}", "HEAD")
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def head_branch(repo_dir, env=None):
    """Head branch name, CI-first: GITHUB_HEAD_REF is the only truth when
    actions/checkout leaves a detached HEAD on the PR merge ref; GITHUB_REF_NAME
    covers the push-event case; otherwise ask git (local contributor run)."""
    env = os.environ if env is None else env
    for key in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
        v = (env.get(key) or "").strip()
        if v:
            return v
    r = _git(repo_dir, "branch", "--show-current")
    return r.stdout.strip() if r.returncode == 0 else ""


_STATUS_RE = re.compile(r"^[A-Z]{1,2}[0-9]{0,3}!?$")  # git name-status: A M D T U X B, R100/C75, optional ! (unmerged)


def _name_status_paths(fields):
    """Parse the NUL-split fields of `git diff -z --name-status` into every path
    the diff touches: BOTH endpoints of R (rename) and C (copy) records, raw
    bytes decoded with surrogateescape (never quoted, never newline-split).

    est-gbim: this replaced `--name-only` parsing, which had three ban-dodging
    holes — rename/collapse (post-image only), octal quoting of exotic paths
    (the quote broke prefix matching), and newline splitting (an embedded
    newline forged a fake entry). -z mode closes all three; fields here are
    already split on NUL.

    Fail-closed (returns None) on any output shape we cannot trust: a status
    token outside the name-status grammar, or a record missing its path
    field(s). The callers must treat None as their hard-error path, never green.
    """
    paths = []
    i = 0
    while i < len(fields):
        status = fields[i].decode("utf-8", "surrogateescape")
        if not _STATUS_RE.match(status):
            return None  # output shape we cannot trust → fail closed
        i += 1
        if status[0] in "RC":
            if i + 1 >= len(fields):
                return None  # truncated rename record → fail closed
            paths.append(fields[i].decode("utf-8", "surrogateescape"))      # pre-image
            paths.append(fields[i + 1].decode("utf-8", "surrogateescape"))  # post-image
            i += 2
        else:
            if i >= len(fields):
                return None
            paths.append(fields[i].decode("utf-8", "surrogateescape"))
            i += 1
    return paths


def diff_name_status_paths(repo_dir, revs=None, pathspec=None):
    """Shared -z --name-status parser (est-h3yi): every path a diff touches,
    both rename/copy endpoints, NUL-split so quoting and embedded newlines
    cannot hide or forge an entry. `revs` is a git rev or rev range (None =
    the working tree vs the index); `pathspec` optionally limits the diff.

    This is the ONE parser: scripts/graph_path_ban.py (the ban) and
    scripts/graph_regen.py (the regen decision) both answer their path
    questions through it — the est-h3yi finding was exactly that the regen
    kept an old `--name-only` + splitlines read with the same three holes the
    ban had already closed. Fail-closed: None on git failure or unparseable
    output; callers must fail, never proceed green."""
    argv = ["diff", "-z", "--name-status"]
    if revs:
        argv.append(revs)
    if pathspec:
        argv += ["--", pathspec]
    r = _git_bytes(repo_dir, *argv)
    if r.returncode != 0:
        return None
    fields = r.stdout.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()  # trailing NUL terminator
    return _name_status_paths(fields)


def changed_files(repo_dir, base, head="HEAD"):
    """All paths changed base..head (full diff — the exemption check needs to see
    whether ANY non-graph file moved, not only the offending slice). See
    diff_name_status_paths for the parsing law; fail-closed to None."""
    return diff_name_status_paths(repo_dir, f"{base}..{head}")


def _git_bytes(repo_dir, *args):
    return subprocess.run(["git", "-C", str(repo_dir), *args],
                          capture_output=True)


def build_parser():
    ap = argparse.ArgumentParser(
        description="PR branches do not touch the knowledge graph (single-writer, #153)")
    ap.add_argument("--base-ref", default="main",
                    help="base branch to compute merge-base against (CI passes "
                         "the event's github.base_ref; empty falls back to main)")
    ap.add_argument("--repo-dir", default=".",
                    help="repository root (default: cwd)")
    return ap


def main(argv=None, env=None):
    args = build_parser().parse_args(argv)
    base_ref = args.base_ref or "main"  # a non-PR event hands us an empty base_ref
    base = merge_base(args.repo_dir, base_ref)
    if base is None:
        print(f"graph_path_ban: cannot compute merge-base against origin/{base_ref} "
              f"(does the CI checkout fetch it?) — failing closed")
        return 2
    changed = changed_files(args.repo_dir, base)
    if changed is None:
        print("graph_path_ban: git diff failed — failing closed")
        return 2
    branch = head_branch(args.repo_dir, env=env)
    offenders = ban_decision(changed, branch)
    if offenders is None:
        print(f"graph_path_ban: OK — regen-lane PR ({branch}) touches only "
              f"{GRAPH_OUT_PREFIX} ({len(changed)} files) — exempt")
        return 0
    if not offenders:
        print(f"graph_path_ban: OK — no {GRAPH_OUT_PREFIX} paths in the PR diff")
        return 0
    print(f"graph_path_ban: FORBIDDEN — PR branch '{branch}' touches the "
          f"single-writer path {GRAPH_OUT_PREFIX} ({len(offenders)} files):")
    for f in offenders:
        print(f"  {f}")
    print(f"only the main-owned regen lane (branch ^chore/graph-, graphify-out/ "
          f"files only) may change it — see issue #153. Drop these files from "
          f"the PR; main's graph refreshes itself after merge.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
