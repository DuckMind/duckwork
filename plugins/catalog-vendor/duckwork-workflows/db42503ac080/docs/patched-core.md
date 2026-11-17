# Patched core: typed turn-cap deaths (optional)

> **DELETE THIS FILE when upstream PR #121041 merges.** After that release, stock
> duckwork writes the field natively, the patch is a no-op, and the two install
> branches below collapse into one.

**Stock duckwork? Skip this file entirely.** The plugin works on a stock install and
degrades honestly: without the patch, a node that dies on its turn cap is recorded
with `error_class=unknown` (partial output and child log are still preserved). It
never crashes, never misbehaves — one event field just stays untyped. Applying the
patch is an operator choice; the plugin never patches your core by itself.

## What the patch adds

Workflow children are spawned as `duckwork chat --query-file -Q --max-turns N` and
report through the quiet turn report (`DUCKWORK_QUIET_TURN_REPORT_FILE`). Stock duckwork
writes `{pid, exit_code, error, reply}` there — enough to know a child died, not
*how*. The CLI's machine-readable turn outcome (`turn_exit_reason`) is exported only
by the `-z` usage-file path, which this spawn contract does not use.

The patch threads the loop's typed outcome into the quiet report as
`turn_exit_reason` (e.g. `max_iterations_reached(60/60)`), touching
`duckwork_cli/quiet_single_query.py`, `duckwork_cli/cli_single_query.py`, and
`tests/duckwork_cli/test_quiet_single_query.py`. A writer that never heard of the
field still produces a valid record; a failed turn still exits 1 — the field is
additive.

## What the plugin gains

`_typed_error_class()` in `wf.py` reads the child's turn report and returns
`("cap_exhausted", reason)` **only** when `turn_exit_reason` is the loop's own
budget-depletion stamp. With the patch: `node.failed` carries typed
`error_class="cap_exhausted"` plus the reason, and the retry gate stops treating a
budget death as maybe-transient. Without it: the field is absent, the function
returns honest nothing, and the death keeps the prose-free `unknown` class.
Nothing on stdout can prove a turn-cap death — the runner will not grep prose for
it, which is exactly why the typed channel matters.

## The patch

Same content as the nightly carry `carried/core-turn-report.patch`
(base commit `fcd6e78`, 2026-09-24):

- sha256: `0d7108260af3775def898829b230d7c2ca3fff554be432c5635d1cb9642ca8b3`

Check your copy before applying:

```sh
sha256sum core-turn-report.patch   # macOS: shasum -a 256
```

## Apply (source install only)

From the root of a duckwork **source** checkout (a `pip install -e` / built-from-source
install — a packaged binary has nothing to patch):

```sh
# from the build-source root, with the patch file beside you
git apply core-turn-report.patch
```

Run the patch's bundled tests (expect 7 passed; unpatched the same file is 3 failed):

```sh
python3 -m pytest tests/duckwork_cli/test_quiet_single_query.py -q
```

## Verify

One-liner proving the patched writer/reader round-trips the typed reason:

```sh
python3 - <<'EOF'
import os, tempfile
from duckwork_cli.quiet_single_query import write_turn_report, read_turn_report
p = os.path.join(tempfile.mkdtemp(), "turn.json")
write_turn_report(p, exit_code=1, error="boom", reply="",
                  turn_exit_reason="max_iterations_reached(60/60)")
assert read_turn_report(p, os.getpid())["turn_exit_reason"] == "max_iterations_reached(60/60)"
print("patched OK")
EOF
```

Or the grep check: `grep -c turn_exit_reason duckwork_cli/quiet_single_query.py` → `>= 3`.

After patching, a workflow node that exhausts `max_turns` should arrive as
`node.failed` with `error_class="cap_exhausted"` on the next run — the read model's
`turn_report` tier note flips from `untyped (core patch not applied)` to typed.
