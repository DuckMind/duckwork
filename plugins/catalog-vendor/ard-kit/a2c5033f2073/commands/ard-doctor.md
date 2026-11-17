---
description: Preflight this ard-kit install (interpreter, wrappers, catalog, registry, harness)
argument-hint: [catalog.json] [registry-url]
---

Run the ard-kit preflight over `$ARGUMENTS` (first token = catalog file,
default `ai-catalog.json`; optional second token = registry URL, default
`$ARD_REGISTRY_URL` or `http://127.0.0.1:8390`):

1. Run: `ard-doctor --catalog <file> --url <url>`. From a plugin checkout the
   same thing is `python3 -m ard_kit.doctor` on POSIX and
   `python -m ard_kit.doctor` on Windows (`bin\ard-doctor.cmd` in cmd.exe,
   `bin/ard-doctor` in Git Bash); the report's own `interpreter` row names
   whichever one this machine has.
2. Read the report top to bottom. Every FAIL and WARN row carries a `hint:`
   line and a `next:` command — run the `next:` of the FIRST failure, because
   the rows below it are usually consequences of it.
3. `SKIP` is not a failure. It means a check could not run: an earlier one
   failed, or the harness does not ship inside an installed wheel. Report it as
   a skip instead of trying to fix it.
4. The exit status is the verdict: 0 = nothing failed (warnings allowed),
   1 = at least one FAIL. Report it along with the failing rows verbatim.

Run this right after installing or upgrading the plugin, and before blaming a
registry for an empty search.
