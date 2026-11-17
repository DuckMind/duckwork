#!/usr/bin/env python3
"""pr_tag_audit.py — release-time gate for `(open PR #NN)` doc tags.

Docs that describe UNMERGED behavior carry an `(open PR #NN)` tag (see
tests/test_docs_surface_drift.py for the README action-table half of the same
law). A tag that only a human remembers to age is a definition that rots in
prose: when the PR merges, the tag must be rewritten to shipped-in-vX. This
script makes the aging mechanical — run it in the release/pack step.

FAILS CLOSED:
  - any tag whose PR is MERGED or CLOSED -> exit 1, with file:line and the
    rewrite owed (`(shipped in vX)` / remove for closed-without-merge);
  - INVERSE (est-4vnq finding 2): an `(open PR #NN)` tag on a README action-table
    row whose action IS dispatched by the door's actual ACTIONS dict -> exit 1,
    even while that PR is open. The state check alone let a shipped `run` row
    tagged `(open PR #47)` print `OK — 8 tagged line(s)` / exit 0 (observed on
    base f83e5d0); the tag claims "not shipped" and the executed door proves
    it is. A shipped-row tag is decidable OFFLINE, so it outranks unverifiability:
    exit 1 even when gh is missing (observed old shape: uncaught
    `FileNotFoundError: [Errno 2] No such file or directory: 'gh'` / exit 1).
  - a tag whose PR state cannot be verified (no gh, no auth, unknown repo) ->
    exit 2, printing every tagged file:line and PR number so a no-gh dev still
    gets the diagnostics; an unverifiable tag is an unaged tag.

Exit 0 only when every documented open-PR tag points at a PR that is, in fact,
still open AND no dispatched action claims unshipped. Usage:
  python3 scripts/pr_tag_audit.py [--repo owner/name]
"""
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ["README.md", "SKILL.md", "AGENTS.md", "CONTRIBUTING.md", "INSTALL.md",
        "CHANGELOG.md"] + [str(p.relative_to(ROOT)) for p in
                          (ROOT / "references").glob("*.md")]
# 'open PR #47', 'open PRs #47/#79', and '(open PR #84)' bolded variants
TAG_RE = re.compile(r"open PRs?\s+((?:#\d+)(?:[/:,\s-]*#\d+)*)")
NUM_RE = re.compile(r"#(\d+)")
# The README action-table half: rows under the tool-section anchor, first
# backticked token = the action the row claims. Same anchors as
# tests/test_docs_surface_drift.py — keep the pair in step.
TABLE_ANCHOR = "## The `workflow` tool"
TABLE_END = "Plus a `/wf`"


def dispatched_actions() -> set:
    """ACTUAL dispatch keys from the executed door (finding 1 / R6): executing
    beats regex-scanning source, which stayed green while a callable lived in
    ACTIONS with no README row. A door that will not execute is fail-closed:
    the drift pin hard-fails on the same shape, so the audit never skips."""
    spec = importlib.util.spec_from_file_location("_pr_tag_audit_door", ROOT / "__init__.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"door not loadable from {ROOT / '__init__.py'}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    actions = getattr(mod, "ACTIONS", None)
    if not isinstance(actions, dict) or not actions:
        raise RuntimeError(f"{ROOT / '__init__.py'}: no non-empty ACTIONS dict")
    return set(actions)


def shipped_tagged_rows() -> list:
    """(action, line_no) for every README action-table row that carries an
    open-PR tag while its action is actually dispatched. line_no is the ABSOLUTE
    README.md line so the diagnostic is directly openable."""
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    dispatched = dispatched_actions()
    anchor = next((i for i, l in enumerate(lines) if TABLE_ANCHOR in l), None)
    end = next((i for i, l in enumerate(lines) if l.startswith(TABLE_END) and i > (anchor or -1)),
               len(lines))
    if anchor is None:
        raise RuntimeError(f"README.md lost the {TABLE_ANCHOR!r} section")
    bad = []
    for i in range(anchor + 1, end):
        m = re.match(r"^\|\s*`([a-z_]+)`\s*\|", lines[i].strip())
        if m and m.group(1) in dispatched and TAG_RE.search(lines[i]):
            bad.append((m.group(1), i + 1))
    return bad


def resolve_repo(argv_repo: str | None) -> str | None:
    if argv_repo:
        return argv_repo
    for remote in ("upstream", "origin"):
        try:
            r = subprocess.run(["git", "-C", str(ROOT), "remote", "get-url", remote],
                               capture_output=True, text=True)
        except FileNotFoundError:
            return None  # no git: the --repo argument is the documented fallback
        m = re.search(r"[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$", r.stdout.strip())
        if r.returncode == 0 and m:
            return m.group(1)
    return None


def main() -> int:
    argv_repo = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--repo" else None
    # OFFLINE-decidable phases FIRST (adversary R8 @ bd5ed44): a shipped-row lie
    # and the tag inventory are decidable without repo resolution or gh, so they
    # must run BEFORE resolve_repo — otherwise a bare invocation (no --repo, no
    # git) returned the generic exit-2 "cannot resolve the GitHub repo" while an
    # unconditional FAIL sat below it (reproduced at bd5ed44: shipped `run` row
    # tagged (open PR #47), PATH=, bare -> exit 2 naming only repo resolution;
    # the identical fixture with --repo -> exit 1 naming README.md:line).
    hits = []  # (file, line_no, pr_numbers)
    for rel in SCAN:
        path = ROOT / rel
        if not path.is_file():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in TAG_RE.finditer(line):
                nums = [int(n) for n in NUM_RE.findall(m.group(1))]
                if nums:
                    hits.append((rel, i, nums))
    # INVERSE direction (offline-decidable): a dispatched action whose
    # README row claims unshipped is a lie the executed door proves, whether or
    # not gh exists and whether or not the repo resolves. Proven red on base
    # f83e5d0: shipped `run` + (open PR #47) printed `OK — 8 tagged line(s)` /
    # exit 0.
    try:
        shipped = shipped_tagged_rows()
    except Exception as exc:  # noqa: BLE001 — fail closed: an unauditable surface is a dirty surface
        print(f"pr_tag_audit: FAIL — cannot read the shipped/unshipped surface: {type(exc).__name__}: {exc}")
        return 1
    for action, line_no in shipped:
        print(f"README.md:{line_no}: action `{action}` is dispatched by ACTIONS but its row carries "
              f"(open PR #NN) — shipped: drop the tag (inverse of the doc-only rule)")
    if shipped:
        print(f"pr_tag_audit: FAIL — {len(shipped)} shipped action(s) tagged as unshipped")
        return 1
    if not hits:
        print("pr_tag_audit: no open-PR doc tags — nothing to age")
        return 0

    def print_unverifiable(why: str) -> None:
        for rel, line_no, nums in hits:
            tag = "/".join(f"#{n}" for n in nums)
            print(f"{rel}:{line_no}: tag says open, PR {tag} — cannot verify state ({why}) — fail closed")
        print(f"pr_tag_audit: FAIL-CLOSED — {len(hits)} unverifiable tag(s)")

    repo = resolve_repo(argv_repo)
    if repo is None:
        # same diagnostics promise as no-gh (finding 3): name every tagged
        # file:line, never just a generic resolution error
        print_unverifiable("repo unresolved: no --repo and no git remote; pass --repo owner/name")
        return 2
    state_cache: dict[int, str | None] = {}
    gh_missing = False

    def state(n: int) -> str | None:
        nonlocal gh_missing
        if n not in state_cache:
            if gh_missing:
                return None
            try:
                r = subprocess.run(["gh", "pr", "view", str(n), "--repo", repo,
                                    "--json", "state,mergedAt", "-q",
                                    'if (.mergedAt != null and .mergedAt != "") then "MERGED" else .state end'],
                                   capture_output=True, text=True)
            except FileNotFoundError:
                # the docstring promise: missing gh is exit 2 with named
                # diagnostics, never an uncaught traceback / exit 1 (finding 3,
                # observed on base f83e5d0 with PATH devoid of gh)
                gh_missing = True
                return None
            state_cache[n] = r.stdout.strip() if r.returncode == 0 else None
        return state_cache[n]

    problems, unverifiable = [], []
    for rel, line_no, nums in hits:
        for n in nums:
            s = state(n)
            if s is None:
                unverifiable.append((rel, line_no, n))
            elif s != "OPEN":
                problems.append((rel, line_no, n, s))
    for rel, line_no, n in unverifiable:
        why = ("gh binary not on PATH" if gh_missing
               else "gh unavailable/unauthenticated?")
        print(f"{rel}:{line_no}: tag says open, PR #{n} — cannot verify state ({why}) — fail closed")
    for rel, line_no, n, s in problems:
        owed = "(shipped in vX)" if s == "MERGED" else "remove (closed without merge)"
        print(f"{rel}:{line_no}: tag says open, PR #{n} is {s} — rewrite to {owed}")
    if unverifiable:
        print(f"pr_tag_audit: FAIL-CLOSED — {len(unverifiable)} unverifiable tag(s)")
        return 2
    if problems:
        print(f"pr_tag_audit: FAIL — {len(problems)} stale tag(s) must age before release")
        return 1
    print(f"pr_tag_audit: OK — {len(hits)} tagged line(s), every referenced PR still open")
    return 0


if __name__ == "__main__":
    sys.exit(main())
