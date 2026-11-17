# Publish scrub audit — 2026-09-24

Audit command (single fixed pass, excludes `.git`):

    grep -rniE '192\.168|haus|callindor|gaidin|rhuidean|jacob|fordex' \
      --include='*.py' --include='*.js' --include='*.md' \
      --include='*.json' --include='*.yaml' --exclude-dir=.git .

29 raw hits. Classification per hit: **GUARD** = assertion/pointer text that
enforces absence or is load-bearing for a portable-skill guarantee (kept
verbatim, allow-listed in `scripts/.scrub-guards`); **FALSE-POSITIVE** = the
substring `haus` inside the ordinary English word `exhaust*` (kept,
allow-listed by the `exhaust` guard regex); **EXPOSURE** = private estate
data that must not ship (rewritten in place or excluded from the publish
tree).

## GUARD — kept verbatim

| file:line | why |
|---|---|
| tests/test_skill_docs.py:16 | `assert "haus " not in skill.lower()` — the ban itself; its own text necessarily contains the banned token. |
| tests/test_packaging.py:84→85 | old blacklist assertion naming the excluded owner-local example. Rewritten to a neutral whitelist (no member under `examples/` outside the public trio) — equivalent-or-stronger guarantee with zero estate strings. |

## FALSE-POSITIVE — `haus` inside `exhaust*` (kept)

tests/test_failures_0923.py:15,186,187,254,292,293 · wf.py:212,419,463,465,484,504 ·
desktop/plugin.js:784,801 (`react-hooks/exhaustive-deps`). All are the words
"exhausted / exhaustion / exhaustive"; verified by `grep -v exhaust` dropping
all 14 lines. Allow-listed via the `exhaust` guard pattern.

## EXPOSURE — removed from the publishable surface

| file:line | disposition |
|---|---|
| examples/callindor-move-plan.json:2 | host name in example name; whole `examples/` dir excluded from the publish tree by `scripts/make_public.py` (examples stay out of the pack per scripts/pack.py too). |
| examples/torture-v3.json | also owner-local (worktree paths); excluded with the dir. |
| tests/test_papercuts_0922.py:1,30,31 | docstring "haus feedback" → neutral; fixture hosts `gaidin`/`rhuidean` → neutral `alpha`/`beta`; template-render assertion kept equivalent (items[1] still renders `probe beta #1`). |
| tests/test_packaging.py:84 | see GUARD row above — rewritten to neutral whitelist assertion (kept assertions equivalent, removes the string). |
| tests/test_papercuts_0922b.py:2 | docstring "haus feedback drain" → "owner feedback drain". |
| tests/test_failed_events_77.py:2 | docstring "haus-verb-roadmap" → "verb-roadmap". |
| tests/test_wait_payload_76.py:2 | docstring "haus-verb-roadmap" → "verb-roadmap". |
| tests/test_edge_routing.mjs:18-20 | node ids `callindor`/`rhuidean` used as graph fixtures → neutral `hub-a`/`hub-b`; geometry assertions are rect-relative, so equivalence holds. |
| plugin.yaml:9 | `author: duckwork (Fordex user build)` → `author: duckwork` (no invented org attribution in a public manifest). |

## Publish-tree exclusions (scripts/make_public.py)

`examples/**`, `docs/PUBLISH-SCRUB.md`, `.git*`, `__pycache__`,
`tests/home*`, `*.log`, plus `scripts/.scrub-guards` self-exemption from the
refusal audit (the allow-list necessarily quotes guard tokens). Any non-guard
hit in a copied file → exit 1 printing `file:line`.

Post-scrub verification: re-running the same grep over the staged tree must
return zero hits (evidence pasted in the lane's final report).
