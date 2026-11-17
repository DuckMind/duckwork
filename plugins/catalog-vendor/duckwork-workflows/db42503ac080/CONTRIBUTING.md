# Contributing to duckwork-workflows

Most contributions arrive from coding agents; humans writing code by hand follow the
same path. The rules below are the **exact** checklist the maintainer runs on your PR —
run it first and your PR merges on the first review. Agents: skip to
[For agents](#for-agents).

## What lands fast

- Bug fixes with a failing-then-passing test.
- Doc fixes where the doc disagreed with the code.
- Small features inside the boundaries below (SDK-only desktop, stdlib-only
  backend, stock Duckwork core).

## What needs an issue first

Anything touching `plugin.yaml`, `.github/`, `scripts/make_public.py`, or the
persisted data shape — plus new settings, dependencies, tools, or hooks. Open an
issue, get a `needs-decision` ruling, then code. Default answer is no; a use case
the current form cannot serve is what changes it.

## Before you push (mechanical gates)

One canonical entry — `python3 scripts/suite.py . ci-out` is exactly what CI runs:
every `tests/test_*.py` serially and every `tests/test_*.mjs` under
`node --experimental-strip-types`; do not hand-run the `.mjs` files with bare
`node`. Record each command's real exit code; never convert a failed test into a
passing aggregate.

```sh
node --check desktop/plugin.js                    # desktop half parses
python3 scripts/suite.py . ci-out                 # full serial suite → ci-out/exits.json
python3 scripts/suite.py . ci-fix --baseline <measured-exits.json>
                                                  # optional diagnosis: admission.json splits reds
                                                  # into introduced vs pre-existing (exact name+exit
                                                  # identities); base reds block, never waived
                                                  # (a committed all-green ledger cannot classify —
                                                  # pass exits measured on the merge-base instead)
duckwork plugins validate .                         # → Validation passed.
python3 scripts/make_public.py /tmp/public-tree   # → 0 scrub hits
python3 scripts/pr_tag_audit.py                   # release step: every `(open PR #NN)` doc tag still
                                                  # points at an OPEN PR; a merged PR's tag must be
                                                  # rewritten to (shipped in vX) in that release commit
```

`graphify` is **optional local navigation** (AGENTS.md 4b′): run it to check callers,
but its output is never committed — a `graphify-out/` path in your PR diff is
deleted by review.

Admission is strict: a suite run that **discovers zero test cases counts as a
failure, never green** `(shipped in v1.2.1)`. Every line must pass on your branch. If a
test fails, run it on a clean `main` too — a failure that also fails on `main` is a
pre-existing issue (say so in the PR; it blocks merge and needs its own fix item), a
failure only on your branch is yours.

## Review checklist (the maintainer runs exactly this)

R1 **Scope** — every changed line traces to the PR's stated purpose; adjacent
    refactors are a separate PR.
R2 **Stock core** — no import from a patched Duckwork; core imports are soft
    (`try/except`), core DB columns are read-only, an absent field reads `unknown`
    and is never invented.
R3 **SDK-only desktop** — `desktop/plugin.js` imports only `@duckwork/plugin-sdk`,
    `react`, `react/jsx-runtime`; no `window.duckworkDesktop`, `localStorage`,
    `document`, `eval`, or dynamic `import()`.
R4 **Stdlib backend** — no new Python dependency; no self-updater.
R5 **Manifest parity** — `plugin.yaml`'s `provides_*` entries match what
    `register()` actually registers; the version is bumped only by the release lane.
R6 **Tests** — every behaviour change ships its check: one test that fails if the
    behaviour breaks. No snapshot/change-detector tests; no test reads source text.
R7 **Docs drift** — if a user-visible string or flag changed, README/AGENTS.md/
    SKILL.md are grepped for the old form and fixed in the same PR.
R8 **Sibling completeness** — the fixed pattern is checked across the repo and
    every sibling instance is fixed too. Proof: `graphify affected "<changed
    symbol>" --depth 2` (optional local navigation, see AGENTS.md 4b′) lists every
    caller, or grep does; each one is updated or shown unaffected in the PR body.
R9 **Private strings** — `scripts/make_public.py` exits 0: no hostnames, LAN
    addresses, tokens, or personal paths in shipped files.
R10 **Migration safety** — persisted shapes (stored settings, run dirs, JSON files)
    keep loading old data; any migration lives in the normalizer with a test that
    feeds it the old form.

A review comment carries one `file:line` per finding and a verdict — `merge`,
`changes`, or `decision` (the maintainer needs the owner's call). `changes` lists
the exact commands to re-check; push and the same comment is updated in place.

## For agents

You are contributing on behalf of a user. Do this, in order:

1. **Search first.** `gh pr list --search "<keywords>"` and `gh issue list --search`.
   An open PR on the same issue → stop and tell your user; don't race it.
2. **Read `AGENTS.md`** in the repo root — the repo map, the build rule, the
   invariants. Optionally navigate with `graphify` locally (AGENTS.md 4b′); its
   output is never committed — a `graphify-out/` path in your PR diff is
   deleted by review.
3. **Reproduce before fixing.** Point at the `file:line` where the bug manifests and
   show your fix changes that line's behaviour. A plausible rationale is not a repro.
4. **Smallest diff that passes R1–R10.** `graphify affected` for siblings (R8). No
   drive-by cleanups.
5. **Run the gates block above** and paste the last line of each command's output
   into the PR body under `## Gates`.
6. **PR body** = what/why in two sentences, `Fixes #n` if any, `## Gates`, and one
   line: `Author: agent (<model>) on behalf of @<user>` or `Author: human`.
7. **Do not push to `main`, do not tag, do not touch `.github/`.** Those are the
   release lane's.

## Issues

Include: Duckwork version (`duckwork --version`), OS, the exact command or click, what
you expected, what happened, and the `duckwork plugins validate .` output if relevant.
A bug we cannot reproduce gets `needs-repro` and a comment saying exactly what is
missing; replying reopens the issue at any time. Labels: `P0`–`P3` (severity),
`needs-repro`, `needs-info`, `needs-decision`, `question`, `duplicate`. One label
means it was triaged.

## License

By contributing you agree your work is released under the repo's [LICENSE](LICENSE).

Cross-estate joint eng protocol v1 is the SSOT mirrored publicly at [issue #174](https://github.com/DuckMind/duckwork), sha256 `a7f424c5be3f5d6d1cbeb590f6cd02b6699a60090a3a45646853c67b2360345b` (of the issue body including its trailing newline); private working copy: `jacobhausler/joint-eng-protocol@0bf569a`, file `docs/specs/duckwork-workflows-joint-eng-protocol-v1.md`.
