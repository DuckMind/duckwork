#!/usr/bin/env python3
"""graph_path_ban.py contract (#153, single-writer knowledge graph).

The ban: a PR whose diff vs merge-base(origin/<base-ref>, HEAD) touches ANY
tracked file under graphify-out/ fails with the offending file list, unless the
head branch matches the regen-lane pattern (^chore/graph-) — the single writer.
The core is split from argv (ban_decision / exempt_branch / changed_files) so
the semantics are unit-testable without CI env; the integration cases below
drive the script as CI does, against a temp clone with a real origin/main.

RED-first witness: before scripts/graph_path_ban.py exists every case here
fails (missing script). Green requires all four.
"""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path

from graph_gate_dep import graphify_dep_guard

ROOT = Path(__file__).resolve().parent.parent
# Load the script as a module by path — the shipped-package import-closure gate
# (#105) probes top-level imports from the unpacked root, where scripts/ is not
# on sys.path; spec_from_file_location is the repo convention (see
# test_graphify_dedupe_27.py loading graph_check the same way).
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "graph_path_ban_under_test", ROOT / "scripts" / "graph_path_ban.py")
gpb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gpb)

PY = sys.executable
fails = 0
# Hermetic: when the serial suite runs inside CI on a PR, GITHUB_HEAD_REF /
# GITHUB_REF_NAME are set for the WHOLE job — the script's CI-first branch read
# would see them through subprocesses and every temp-repo case would evaluate
# against the PR's real branch instead of the fixture's. Scrub them.
CLEAN_ENV = {k: v for k, v in os.environ.items()
             if k not in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME", "GITHUB_BASE_REF", "GITHUB_REF")}


def check(name, ok, detail=""):
    global fails
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    fails += 0 if ok else 1


# --- core unit semantics (no git, no graphify) -----------------------------------
check("core: no graphify-out paths → no violation",
      gpb.ban_decision(["wf.py", "tests/test_engine.py", "docs/README.md"], "feature/x",
                       graphify_out_prefix=gpb.GRAPH_OUT_PREFIX) == [])
check("core: any graphify-out path is a violation on a normal branch",
      gpb.ban_decision(["wf.py", "graphify-out/graph.json"], "feature/x",
                       graphify_out_prefix=gpb.GRAPH_OUT_PREFIX) == ["graphify-out/graph.json"])
check("core: ^chore/graph- branch is exempt from the ban",
      gpb.ban_decision(["graphify-out/graph.json", "graphify-out/manifest.json"],
                       "chore/graph-abc1234", graphify_out_prefix=gpb.GRAPH_OUT_PREFIX) is None)
check("core: exemption is the BRANCH alone — a normal branch may not hide graph files among source",
      gpb.ban_decision(["graphify-out/graph.json"], "chore/graphsync-153",
                       graphify_out_prefix=gpb.GRAPH_OUT_PREFIX) == ["graphify-out/graph.json"])
check("core: exempt branch + MIXED diff (source AND graph) is not a regen PR — banned",
      gpb.ban_decision(["wf.py", "graphify-out/graph.json"], "chore/graph-abc1234",
                       graphify_out_prefix=gpb.GRAPH_OUT_PREFIX) == ["graphify-out/graph.json"])
check("core: empty diff passes on any branch",
      gpb.ban_decision([], "main", graphify_out_prefix=gpb.GRAPH_OUT_PREFIX) == []
      and gpb.ban_decision([], "chore/graph-x", graphify_out_prefix=gpb.GRAPH_OUT_PREFIX) == [])
check("core: exempt_branch accepts only the regen-lane pattern",
      [gpb.exempt_branch(b) for b in ("chore/graph-abc1234", "chore/graph-", "main",
                                      "feature/chore/graph-x", "docs/chore/graph-y")]
      == [True, True, False, False, False])
ap = gpb.build_parser()
check("core: --base-ref defaults to main", ap.parse_args([]).base_ref == "main")
check("core: --base-ref accepts both argv shapes",
      ap.parse_args(["--base-ref", "master"]).base_ref == "master"
      and ap.parse_args(["--base-ref=release"]).base_ref == "release")


def git(repo, *args, **kw):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True,
                          env={**os.environ, "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
                               "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z", **kw.get("env", {})}).stdout


def commit_all(repo, msg):
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg)


def make_case(td, name):
    """Bare origin + clone seeded with tracked source and a tracked graphify-out file."""
    origin = Path(td) / f"{name}-origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "-C", str(origin), "symbolic-ref", "HEAD", "refs/heads/main"],
                   check=True)  # a fresh bare repo defaults to master; the seed pushes main
    seed = Path(td) / f"{name}-seed"
    seed.mkdir()
    (seed / "scripts").mkdir()
    (seed / "graphify-out").mkdir()
    (seed / "a.py").write_text("def a():\n    return 1\n")
    (seed / "graphify-out" / "graph.json").write_text('{"nodes": [], "links": []}\n')
    (seed / "scripts" / "graph_path_ban.py").write_text(
        (ROOT / "scripts" / "graph_path_ban.py").read_text())
    git(seed, "init", "-q")
    commit_all(seed, "init")
    git(seed, "branch", "-M", "main")
    git(seed, "push", "-q", str(origin), "main")
    work = Path(td) / f"{name}-work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True)
    git(work, "config", "user.email", "t@t"); git(work, "config", "user.name", "t")
    return origin, work


def run_ban(work, base_ref="main"):
    return subprocess.run([PY, "scripts/graph_path_ban.py", "--base-ref", base_ref],
                          cwd=work, capture_output=True, text=True, env=CLEAN_ENV)


# --- integration: CI-shaped cases against a real origin/main ----------------------
with tempfile.TemporaryDirectory(prefix="pb-test-") as td:
    # case 1: source-only PR → exit 0, silent
    _, work = make_case(td, "src")
    git(work, "checkout", "-qb", "feature/source-only")
    (work / "b.py").write_text("def b():\n    return 2\n")
    commit_all(work, "feat: add b")
    r = run_ban(work)
    check("integration: source-only PR passes",
          r.returncode == 0 and "FORBIDDEN" not in (r.stdout + r.stderr),
          f"rc={r.returncode} out={r.stdout.strip()[-160:]}")

    # case 2: PR touching graphify-out → exit 1 printing the offending file
    _, work = make_case(td, "touch")
    git(work, "checkout", "-qb", "feature/touches-graph")
    (work / "graphify-out" / "graph.json").write_text('{"nodes": [1], "links": []}\n')
    commit_all(work, "author regen (forbidden)")
    r = run_ban(work)
    check("integration: PR touching graphify-out fails with the file list",
          r.returncode == 1 and "graphify-out/graph.json" in r.stdout,
          f"rc={r.returncode} out={r.stdout.strip()[-160:]}")

    # case 3: same diff on a ^chore/graph- branch → exempt, exit 0
    _, work = make_case(td, "exempt")
    git(work, "checkout", "-qb", "chore/graph-abc1234")
    (work / "graphify-out" / "graph.json").write_text('{"nodes": [2], "links": []}\n')
    commit_all(work, "chore(graph): refresh")
    r = run_ban(work)
    check("integration: chore/graph-* branch is exempt",
          r.returncode == 0, f"rc={r.returncode} out={r.stdout.strip()[-160:]}")

    # case 3b: exempt branch + MIXED diff → not a regen PR, banned
    _, work = make_case(td, "mixed")
    git(work, "checkout", "-qb", "chore/graph-smuggles-source")
    (work / "graphify-out" / "graph.json").write_text('{"nodes": [3], "links": []}\n')
    (work / "sneaky.py").write_text("def sneaky():\n    return 1\n")
    commit_all(work, "chore(graph): refresh + smuggled source")
    r = run_ban(work)
    check("integration: exempt branch hiding source edits alongside graph files fails",
          r.returncode == 1 and "graphify-out/graph.json" in r.stdout,
          f"rc={r.returncode} out={r.stdout.strip()[-160:]}")

    # case 4: base-ref semantics — main advances after the fork; a branch whose own
    # diff vs merge-base is clean passes even though diff vs the NEW main tip is not.
    origin, work = make_case(td, "fork")
    git(work, "checkout", "-qb", "feature/forked")
    (work / "c.py").write_text("def c():\n    return 3\n")
    commit_all(work, "feat: add c")
    git(work, "push", "-q", "origin", "feature/forked")
    base_tip = git(work, "rev-parse", "main").strip()
    main2 = Path(td) / "fork-main2"
    subprocess.run(["git", "clone", "-q", str(origin), str(main2)], check=True)
    (main2 / "graphify-out" / "manifest.json").write_text('{"at": "main"}\n')
    commit_all(main2, "chore(graph): main-side regen (not this branch's diff)")
    git(main2, "push", "-q", "origin", "main")
    git(work, "fetch", "-q", "origin")
    r = run_ban(work)
    check("integration: base is merge-base(origin/main, HEAD), not the main tip",
          r.returncode == 0,
          f"rc={r.returncode} out={(r.stdout + r.stderr).strip()[-200:]} (branch clean vs its fork point {base_tip[:7]})")

    # case 4b (est-gbim): the shapes --name-only used to hide. A rename is
    # reported by --name-only as its POST image only, so R100 out of (or into)
    # graphify-out/ dodged the ban; quoting octal-escaped exotic names so the
    # prefix match failed; an embedded newline forged a fake entry. All must
    # now fail closed at exit 1 naming the graph path (or its former home).
    _, work = make_case(td, "rout")
    git(work, "checkout", "-qb", "feature/rename-out")
    git(work, "mv", "graphify-out/graph.json", "docs-graph.json")
    (work / "a.py").write_text("def a():\n    return 9\n")
    commit_all(work, "rename graph file out + source change")
    r = run_ban(work)
    check("integration: pure rename OUT of graphify-out/ is caught (pre-image)",
          r.returncode == 1 and "graphify-out/graph.json" in r.stdout,
          f"rc={r.returncode} out={(r.stdout + r.stderr).strip()[-160:]}")

    _, work = make_case(td, "rin")
    git(work, "checkout", "-qb", "feature/rename-in")
    git(work, "mv", "a.py", "graphify-out/a.py")
    commit_all(work, "rename source into the single-writer path")
    r = run_ban(work)
    check("integration: rename INTO graphify-out/ is caught (post-image)",
          r.returncode == 1 and "graphify-out/a.py" in r.stdout,
          f"rc={r.returncode} out={(r.stdout + r.stderr).strip()[-160:]}")

    _, work = make_case(td, "del")
    git(work, "checkout", "-qb", "feature/delete-graph")
    git(work, "rm", "-q", "graphify-out/graph.json")
    commit_all(work, "delete the graph file")
    r = run_ban(work)
    check("integration: deletion of a graphify-out/ file is caught",
          r.returncode == 1 and "graphify-out/graph.json" in r.stdout,
          f"rc={r.returncode} out={(r.stdout + r.stderr).strip()[-160:]}")

    _, work = make_case(td, "odd")
    git(work, "checkout", "-qb", "feature/odd-names")
    (work / "graphify-out" / "evil\n.json").write_text('{"x": 1}\n')
    (work / "graphify-out" / "spaces in name.json").write_text('{"x": 2}\n')
    commit_all(work, "newline- and space-named graph files")
    r = run_ban(work)
    check("integration: quoted / embedded-newline graph paths cannot dodge the prefix match",
          r.returncode == 1 and "evil" in r.stdout and "spaces in name.json" in r.stdout,
          f"rc={r.returncode} out={(r.stdout + r.stderr).strip()[-160:]}")

    # case 5 (est-gbim): exit-2 fail-closed — an unknown base-ref must never
    # read as green, and the parser must not guess on an unparsable diff.
    _, work = make_case(td, "badsbase")
    git(work, "checkout", "-qb", "feature/odd-names")
    (work / "b2.py").write_text("def b2():\n    return 1\n")
    commit_all(work, "source-only change")
    r = run_ban(work, base_ref="no-such-branch")
    check("integration: unknown base-ref → exit 2 (fail closed, never green)",
          r.returncode == 2, f"rc={r.returncode} out={(r.stdout + r.stderr).strip()[-160:]}")

# core unit: the parser consumes rename/copy records as BOTH endpoints — feed it
# synthetic name-status fields through a stubbed git to pin the record walker
# independent of git's own rename detection heuristics.
_orig_git_bytes = gpb._git_bytes


class _R:
    def __init__(self, rc, out):
        self.returncode, self.stdout = rc, out


try:
    gpb._git_bytes = lambda rd, *a: _R(0, b"R100\0graphify-out/graph.json\0moved.json\0M\0a.py\0")
    got = gpb.changed_files(".", "base")
    check("parser: rename record yields BOTH endpoints",
          got == ["graphify-out/graph.json", "moved.json", "a.py"], str(got))
    gpb._git_bytes = lambda rd, *a: _R(0, b"D\0graphify-out/graph.json\0")
    check("parser: deletion yields the removed path",
          gpb.changed_files(".", "base") == ["graphify-out/graph.json"])
    gpb._git_bytes = lambda rd, *a: _R(0, b"R100\0graphify-out/graph.json\0")  # truncated pair
    check("parser: truncated rename record → None (fail closed)",
          gpb.changed_files(".", "base") is None)
    gpb._git_bytes = lambda rd, *a: _R(0, b"nonsense\0x\0")
    check("parser: unrecognized status field → None (fail closed)",
          gpb.changed_files(".", "base") is None)
    gpb._git_bytes = lambda rd, *a: _R(128, b"")
    check("parser: git failure → None (fail closed)",
          gpb.changed_files(".", "base") is None)
finally:
    gpb._git_bytes = _orig_git_bytes

# --- graph_regen smoke: NO_CHANGES on an already-honest tree ----------------------
# Needs the graphify CLI — a DECLARED test dep (CI installs graphifyy==0.9.67):
# absent CLI FAILS naming the dep (same law as tests/test_graph_gate.py), and only
# SKIPs under the explicit opt-out DUCKWORK_ALLOW_SKIP_GRAPH_GATE=1.
_guard = graphify_dep_guard("graph_regen smoke")
if _guard is not None:
    fails += _guard  # fail-closed: a missing declared dep is a red, not a silent skip
else:
    _rspec = importlib.util.spec_from_file_location(
        "graph_regen_under_test", ROOT / "scripts" / "graph_regen.py")
    grg = importlib.util.module_from_spec(_rspec)
    _rspec.loader.exec_module(grg)
    ap = grg.build_parser()
    try:
        ap.parse_args([])
        ok = False
    except SystemExit:
        ok = True
    check("regen core: --repo-dir and --base-sha are required", ok)
    check("regen core: args parse", ap.parse_args(
        ["--repo-dir", "r", "--base-sha", "abc"]).base_sha == "abc")

    with tempfile.TemporaryDirectory(prefix="gr-test-") as td:
        repo = Path(td) / "repo"
        repo.mkdir()
        (repo / "scripts").mkdir()
        (repo / "a.py").write_text("def alpha():\n    return beta()\n\ndef beta():\n    return 1\n")
        (repo / ".gitignore").write_text("graphify-out/graph.html\ngraphify-out/cache/\ngraphify-out/cost.json\n")
        shutil.copy(ROOT / "scripts" / "graph_check.py", repo / "scripts" / "graph_check.py")
        shutil.copy(ROOT / "scripts" / "graph_regen.py", repo / "scripts" / "graph_regen.py")
        git(repo, "init", "-q")
        commit_all(repo, "init")
        env = {**os.environ, "GRAPHIFY_NO_LLM": "1"}
        r = subprocess.run(["graphify", "update", str(repo), "--force"],
                           capture_output=True, text=True, env=env)
        check("regen smoke: seed graphify update runs", r.returncode == 0, (r.stdout + r.stderr)[-160:])
        commit_all(repo, "chore(graph): seed")
        sha = git(repo, "rev-parse", "HEAD").strip()

        r = subprocess.run([PY, "scripts/graph_regen.py", "--repo-dir", str(repo),
                            "--base-sha", "deadbeef"],
                           capture_output=True, text=True, env=env)
        check("regen: HEAD != base-sha aborts (exit 1, no marker)",
              r.returncode == 1 and "NO_CHANGES" not in r.stdout and "FILES" not in r.stdout,
              f"rc={r.returncode} out={r.stdout.strip()[-160:]}")

        r = subprocess.run([PY, "scripts/graph_regen.py", "--repo-dir", str(repo),
                            "--base-sha", sha],
                           capture_output=True, text=True, env=env)
        check("regen smoke: honest tree at base-sha → NO_CHANGES, exit 0",
              r.returncode == 0 and "NO_CHANGES" in r.stdout and "FILES" not in r.stdout,
              f"rc={r.returncode} out={r.stdout.strip()[-160:]}")

        # a source edit makes the committed graph lag → FILES + the graph paths
        (repo / "c.py").write_text("def gamma():\n    return 3\n")
        commit_all(repo, "feat: add gamma")
        sha2 = git(repo, "rev-parse", "HEAD").strip()
        r = subprocess.run([PY, "scripts/graph_regen.py", "--repo-dir", str(repo),
                            "--base-sha", sha2],
                           capture_output=True, text=True, env=env)
        check("regen smoke: lagging source → FILES listing graphify-out paths, exit 0",
              r.returncode == 0 and "FILES" in r.stdout
              and any(line.startswith("graphify-out/") for line in r.stdout.splitlines()),
              f"rc={r.returncode} out={r.stdout.strip()[-200:]}")
        # the caller commits the regen (its chore(graph): commit); the decision
        # is idempotent: re-running over the committed regen says NO_CHANGES
        commit_all(repo, f"chore(graph): refresh at {sha2[:7]}\n\ngraph-base: {sha2}")
        r = subprocess.run([PY, "scripts/graph_regen.py", "--repo-dir", str(repo),
                            "--base-sha", git(repo, "rev-parse", "HEAD").strip()],
                           capture_output=True, text=True, env=env)
        check("regen smoke: --fix converges — committed regen re-runs NO_CHANGES",
              r.returncode == 0 and "NO_CHANGES" in r.stdout,
              f"rc={r.returncode} out={r.stdout.strip()[-160:]}")

print("ALL PASS" if not fails else f"FAIL {fails}")
sys.exit(1 if fails else 0)
