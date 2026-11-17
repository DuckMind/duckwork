# Ultra-review: the trust plane of 0.19.0

Reviewed: `ard_kit/trust.py` (712 lines) end to end, plus every caller of it —
`ard_kit/registry.py`'s federation gate and the CLI's three source modes.
Fixed in: **0.19.1**, branch `gate/trust-0.19.1`.

Ten findings, all resolved: one CRIT, five WARN, four NIT. Every fix carries a
targeted-flip proof (below), so each one is a check that fails if the fix is
undone rather than a check that happens to pass.

Nothing here is committed. The operator decides when the branch merges.

## Findings

| ID | Sev | What was wrong | Fix | Flip |
|----|-----|----------------|-----|------|
| R1 | CRIT | Attached-payload JWS: the signature was checked over `parts[1]` while the claims were read from the **outer** object. Forged outer claims therefore carried a genuine signature — measured VERIFIED for `urn:air:evil.example:agent:pwn`. | canonical-equality gate between the outer claims and the signed payload | F1 |
| R1c | judgement | `fresh_ok is None` fell through to VERIFIED: an attestation with no readable date was accepted, and `--max-age-days` was silently inert on it. | the ladder now treats `None` as UNSUPPORTED, not as absence of a problem | F10 |
| R2 | WARN | `resp.read()` on a peer response was unbounded — a peer answering 4 GiB OOMs the registry. | read `trust.MAX_BODY + 1`, raise past the cap, log the upstream as failed | F6 |
| R3 | WARN | JWKS selection took the first key with a matching-or-absent `kid`, applied no `use`/`key_ops` filter (an `use=enc` key was accepted for signing), and tried exactly one candidate — so a correct key sitting second in the set produced a false SUSPECT. | filter candidates by `use`/`key_ops`, then try every survivor | F2, F3 |
| R4 | WARN | `fetch_manifest` follows cross-host redirects, but `hosted_from` was computed from `args.url`. Hosting evidence was credited to the domain **asked**, not the domain that answered — a redirect turns the strongest verdict into a lie. | `hosted_from = host_of(final_url)` | F4 |
| R4-NIT | NIT | `--url` had no scheme allowlist, so a local directory path yielded VERIFIED with authority `'file'`. | http(s) only, exit 2 otherwise | in-suite |
| R5 | WARN | `_INVISIBLE` missed the TAG block U+E0000–U+E007F and the Hangul fillers — both are established prompt-smuggling carriers. VS16 U+FE0F stays excluded on purpose: emoji presentation, not concealment. | both ranges added | F5, F5b |
| R6 | NIT | The catalog path exited **0** on UNSUPPORTED while the attestation path exited **1**, contradicting `main`'s own docstring. Fail-open, in a CLI whose entire job is to be a gate. | both returns test `_FLAGGED` | F8, F8b, F9, F9b |
| R7 | NIT | A dead upstream produced neither a `peers[]` entry nor a log line: federation degraded to a local answer with no trace, indistinguishable from a peer that legitimately had nothing. | one stderr line per failed upstream | F7 |
| R8 | WARN | `UNSUPPORTED` was **unreachable** from the catalog/URL path. The scheme finding is a member of `findings`, so `if findings:` always won and everything collapsed to SUSPECT. Every spec-legal non-did:web identity — which §4.5.1 explicitly permits — was reported as tampering. Measured before: `did:key -> SUSPECT`, `UNSUPPORTED reachable in catalog path? False`. | the unresolvable-scheme finding no longer triggers SUSPECT on its own; worst-wins is untouched | F11 |
| R8b | NIT | The finding text read `'did'` for a `did:key:…` identity, hiding the one part an operator can act on. | report `did:<method>` | F12 |
| R9 | WARN | **Found by the R8 fix's own blast radius.** R8 made UNSUPPORTED reachable, which silently changed the meaning of `registry.py`'s `== trust.SUSPECT`. Pre-R8 that comparison was equivalent to `in _FLAGGED`, because `verdict_entry` could never return UNSUPPORTED; post-R8 it is not, and a §4.5.1-legal did:key/SPIFFE peer row now lands on it. The behaviour was kept — dropping UNSUPPORTED would reject every row from a peer that identifies by SPIFFE, which is the same over-reach R8 removed, one layer up — but the decision was accidental and nothing pinned it. | `ponytail:` comment naming the ceiling and the upgrade path, plus a served/dropped assert pair in the federation check | F13 |

R9 is the one worth generalising: **a fix that makes a previously unreachable
value reachable silently rewrites the meaning of every equality comparison
against that value elsewhere in the codebase.** The tell was that
`registry.py` was the only module testing a verdict without going through
`_FLAGGED` — the asymmetry read as an oversight, and pre-R8 it made no
difference, so nothing would ever have failed.

## Deliberately not fixed

- The root untracked Duckwork `plugin.json` still carries a description that
  predates the trust plane. Its *version* is synced to 0.19.1 (bumped by hand
  rather than waiting for `ardkit-plugin-sync.timer` at 04:40); its *copy* is
  listing text, and the operator has that family parked as plan item `b2`.
- The "1537 entries" figure in `docs/decisions.md` (Known trade-offs) still
  reads low against today's catalog. That number belongs to a dated bench
  measurement, not to a live claim, and rewriting it would falsify the record
  it is quoting.

## Baselines, measured before and after

All four re-run against 0.19.1 on 2026-09-05. B6 was added afterwards, for a
reason given under the table.

| # | Command | Result |
|---|---------|--------|
| B1 | `trust --url https://ora.ai --quiet` | exit **0**, `# manifest https://ora.ai/.well-known/ard.json`, `# 5 entries: VERIFIED 5, SUSPECT 0, UNSUPPORTED 0, UNVERIFIED 0` |
| B2 | `GET ora.ai/api/ard/attestation/resend.com` | HTTP 200, 468 bytes |
| B3 | `trust --attestation /tmp/att_resend.json --jwks https://ora.ai/.well-known/jwks.json` | exit **0**, `VERIFIED resend.com Ed25519 signature verified (kid '6YCgGgT5…') (issued 2026-09-04T22:14:02.405Z (0d old))` |
| B4 | `trust --catalog data/ard/station-catalog.json --quiet` | exit **1**, one SUSPECT (`scripts:check_jules_status`, three U+0010 findings), `# 1707 entries: VERIFIED 0, SUSPECT 1, UNSUPPORTED 0, UNVERIFIED 1706` |
| B5 | same, after the source script was fixed | exit **0**, `# 1707 entries: VERIFIED 0, SUSPECT 0, UNSUPPORTED 0, UNVERIFIED 1707` |
| B6 | `python3 bench/bench.py` against the live 0.19.1 registry | exit **0**, tool lane `P@1=0.64 P@5=1.00 MRR=0.793 not-found=0/25`, mcp lane `P@1=0.92 P@5=1.00 MRR=0.958 not-found=0/12` — identical to the pre-0.19 record in `docs/decisions.md` |

B6 exists because B1-B5 all exercise the trust CLI and the attestation path,
while 0.19.x also put trust verdicts *into `/search` responses* — a change to
the retrieval surface that no row of the original gate covered. Ranking did not
move: both lanes reproduce the numbers recorded before the trust plane landed,
on a catalog that had grown from 1537 to 1707 entries in between. Had a verdict
field displaced a scoring field, this row is where it would have shown up.

B1's `hostedFrom` line is R4's fix visible in the output: the manifest is
credited to the URL that answered.

B4 is the invariant to watch, and the entry count is **not** part of it —
`ard-catalog-refresh.timer` rewrites that file hourly, so 1705/1706/1707 are
three generations of the same catalog, not drift caused by these fixes. The
result held across two catalog generations spanning the fixes: no station entry
carries a non-did:web identity, so R8 changed no station verdict, and
`UNSUPPORTED` stayed at 0 both times.

B4's single SUSPECT was a real defect, not a false positive — two raw U+0010
bytes a script's docstring carried into the catalog — which is what made it
actionable rather than noise. It was fixed at the source (B5), and deliberately
**not** by making the catalogizer strip control characters: a catalogizer that
sanitizes on the way in would leave the trust plane nothing to find, laundering
exactly the class of defect it exists to surface. The finding belongs to whoever
wrote the bytes.

## The flip gate

A new assert is only real if reverting its fix fails the suite. `/tmp/flips.py`
patches the shipped source, runs `check_trust()` in a subprocess, restores the
files in a `finally` block, and hash-verifies the restore. A leg that leaves the
suite green is reported `VACUOUS`, not passed.

Run 5: `FLIP_EXIT=0`, **all 16 detected**, restore OK ×3.

```
F1  R1  attached-payload canonical match    DETECTED (True, "Ed25519 signature verified (kid 'k1')")
F2  R3  jwks use/key_ops filter             DETECTED (True, "Ed25519 signature verified (kid 'k1')")
F3  R3  try every candidate                 DETECTED (False, 'signature did not verify')
F4  R4  credit the host that answered       DETECTED ('https://elsewhere.example/.well-known/ard.json', 0)
F5  R5  TAG block in _INVISIBLE             DETECTED TAG-block smuggling not caught
F5b R5  Hangul fillers in _INVISIBLE        DETECTED Hangul filler not caught
F6  R2  peer body cap                       DETECTED ([], [{'base': 'http://big.example', 'returned': 0, …}])
F7  R7  dead-upstream log line              DETECTED AssertionError
F8  R6  catalog exit code                   DETECTED (0, {… 'UNSUPPORTED': 1})
F8b R6  catalog UNSUPPORTED leg             DETECTED (0, {… 'UNSUPPORTED': 1})
F9  R6  attestation exit code               DETECTED (0, {'verdict': 'UNSUPPORTED', …})
F9b R6  attestation SUSPECT leg             DETECTED (0, {'verdict': 'SUSPECT', …})
F10 R1c freshness None -> UNSUPPORTED       DETECTED {'verdict': 'VERIFIED', …}
F11 R8  UNSUPPORTED reachable in ladder     DETECTED {'identifier': 'urn:air:registry.example:mcp:openspace', …}
F12 R8b did:<method> in the finding text    DETECTED ["identity scheme 'did' is not did:web"]
F13 R9  gate serves an UNSUPPORTED peer row DETECTED []
```

F13's `[]` is the regression it pins: when the gate was widened to
`in _FLAGGED`, the served-row list went empty.

### Four vacuity traps this method caught

Worth keeping, because all four were my own asserts looking green while testing
nothing:

1. **Substring-matching verdict names in the printed summary.** All four names
   always appear in the counts line, so `assert "UNSUPPORTED" in out` passes
   unconditionally. Fixed by asserting the counts dict.
2. **An oversized-but-invalid-JSON peer body.** `json.loads` raised before the
   cap was ever consulted, so the cap went untested. Fixed by serving valid
   JSON that is honestly over the limit.
3. **Asserting only one member of `_FLAGGED` per exit path.** A fix that handles
   SUSPECT and forgets UNSUPPORTED stays green. Fixed by splitting each into
   two legs (F8/F8b, F9/F9b).
4. **The R9 shape above** — an equality comparison whose meaning changed
   because a fix made a new value reachable. No assert was wrong; the code
   under test silently became different code.

Also load-bearing: `/tmp/flip_backup/` is refreshed before every mutation run.
The working tree holds uncommitted fixes, so `git checkout` would destroy them.

## Landing gate

All four steps pass on 0.19.1:

1. `python3 selfcheck.py` → `SELFCHECK_EXIT=0`.
2. Targeted flip gate → 16/16 detected, `FLIP_EXIT=0`, restore verified.
3. `python3 -m build --no-isolation` → `BUILD_EXIT=0`; METADATA
   `Version: 0.19.1`; both fix markers present inside the wheel; `zipimport`
   reports `version 0.19.1` and `did:key -> UNSUPPORTED`.
4. Recatalogize into a temp path → byte-identical to the live catalog
   (`DIFF_IDENTICAL`, 2175201 bytes both).

Version carriers all agree at 0.19.1: `ard_kit/__init__.py`, `pyproject.toml`,
`.qoder-plugin/plugin.json` (the three `check_versions()` enforces) plus the
untracked root `plugin.json`. `check_versions()` matches those by regex rather
than `tomllib` because `tomllib` is 3.11+ and the floor here is 3.10.

No `ard-kit-0.19.1.zip` was built: the plugin zip belongs to the AppHub lane
(`scripts/ops/apphub_resubmit_v2.py`), which is parked pending the operator's
`b2` decision.

## Surfaces read and left alone

Traced while following R2/R7/R9, found sound, recorded so the next reviewer
does not re-walk them:

- The MCP `ard_verify` tool takes an identifier only and never fetches — a
  fetch driven by model input would be an SSRF surface. The operator CLI keeps
  `--url`, now behind an http(s) allowlist.
- `trust.MAX_BODY` is a single ceiling applied to every untrusted remote read
  in the package, not a per-call-site constant.
- A peer's `score` is clamped into 0..100 and its `totalResults` is distrusted
  via `max(claimed, returned)`, with `bool` checked before `int` because `bool`
  is an `int` subclass.
- Peer rows are never given `hosted_from`. An aggregator relaying third-party
  entries is doing its job, and demanding hosting there would condemn every
  row it relays.
- Each upstream's fetch is inside its own `try`, so a peer answering valid JSON
  of the wrong shape skips rather than taking down the local search.

## Not hunted

Out of scope for this pass, and not claimed as clean: `catalogize.py`'s
extraction boundary, the scorer and its ranking, cursor/paging semantics,
bearer auth, and the `package.json` bin parsers. These are exercised by
`selfcheck.py` but were not read line by line here.
