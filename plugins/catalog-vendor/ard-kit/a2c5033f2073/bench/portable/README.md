# Portable retrieval benchmark

A deterministic, self-contained benchmark for the ard-kit retrieval scorer.
It answers one narrow question reproducibly: **given a small harmless fixture
corpus and a frozen set of gold labels, does the production scorer surface the
right capability, and how big is the answer?**

This is the portable sibling of [`bench/bench.py`](../bench.py). That one measures
the **live station registry** (`127.0.0.1:8390` + a bearer token from
`~/.config/secrets`) against a **ripgrep** baseline over the whole workstation —
useful, but it needs station directories and a secrets file, and it *compares*
retrieval rather than *pinning* it. This harness needs neither: it runs from a
clean checkout with no station paths and no secrets, and it freezes the result so
any change is visible.

## What it measures (honestly named)

- **Search quality** — P@1, P@5, MRR against frozen gold labels.
- **Response size** — HTTP response **bytes**. Bytes are **not** tokens spent;
  they are the wire size of the answer the scorer returns.
- **Latency** — wall ms/query, in-process. Non-deterministic, so it is reported
  but **excluded from the frozen digest**.

This is **retrieval quality, not agent task success**. Whether discovery through
ard-kit actually helps an agent pick the right tool with less context is a
separate A/B experiment, not this benchmark.

## Run it

```bash
python3 bench/portable/harness.py --selfcheck   # pure-helper asserts; no server/network
python3 bench/portable/harness.py               # run, report, compare to expected.json
python3 bench/portable/harness.py --freeze      # pin this run into expected.json
python3 bench/portable/harness.py --json out.json   # machine-readable report
```

The runner catalogizes `corpus/` in a subprocess (`--host bench.local`),
normalizes the corpus absolute root to `<CORPUS>` so served bytes are identical
wherever the checkout lives, then serves the normalized catalog through the
**real** `ard_kit.registry.make_handler` on an ephemeral `127.0.0.1` port with
`token=None` and POSTs each query to `/search` — true wire bytes, no
re-implementation of the scorer.

## The corpus and the gold labels

`corpus/` is 13 inert fixtures across all four catalogize lanes — 5 scripts
(`.py`/`.sh`), 2 package `bin` commands, 3 `SKILL.md` skills, 3 MCP cards
(`.mcp.json` + `.mcp.ard.json` sidecar). Nothing in it executes; the harness only
reads docstrings and metadata, and there are no secrets or network endpoints.

`refs.json` holds 23 frozen queries in three groups:

- **en** (15) — one per fixture tool plus two deliberately ambiguous
  **multi-gold** queries. Gold labels list *every* correct tool, so a tie between
  two fitting capabilities is a pass, not an arbitrary pick.
- **ru** (5) — reported as their own group. `kind=cyrillic-blind` queries are
  pure Cyrillic, which the `[a-z0-9]+` tokenizer reduces to an **empty token
  set**: the scorer then returns the whole catalog at score 0 and the intended
  tool is **not** ranked. `kind=latin-rescue` queries carry a latin/acronym token
  (`csv`, `json`, `pdf`) that survives and rescues the right tool. This contrast
  is the honest headline finding — **measured, not fixed here**.
- **negative** (3) — capabilities the corpus does not have. A correct scorer
  returns empty (`totalResults=0`): it can say "no such capability".

Gold keys are the identifier tail after `urn:air:<domain>:`, so they stay valid
whatever domain the corpus is catalogized under.

## Frozen baseline (corpus v1)

| group | P@1 | P@5 | MRR | notes |
|-------|-----|-----|-----|-------|
| en | 1.00 | 1.00 | 1.000 | not-found 0/15 |
| ru | 0.60 | 0.60 | 0.600 | cyrillic-blind 0/2 ranked, latin-rescue 3/3 |
| negative | — | — | — | correctly-empty 3/3 |

The authoritative `digest`, `catalogSha` and `codeSha` live in `expected.json`.
The digest covers corpus version, domain, page size and every outcome **except
latency**, so it is stable across environments: the same corpus produces the same
digest on the station and in an independent checkout at a different absolute path
(verified). A run that does not match `expected.json` prints *which* of
digest / catalogSha / codeSha drifted, separating "retrieval behavior changed"
from "corpus changed" from "scorer code changed".

## Freeze discipline

Labels were authored against the **real** `search_catalog` output over the
fixture corpus, not predicted, and are frozen. **Do not re-freeze
`expected.json` to make a regression look like a pass.** Re-freeze only when the
change is intended — and never rewrite `refs.json` gold labels to flatter the
numbers. The scorer-tuning rationale (why the fold and field weights stay as
they are) is in [`docs/decisions.md`](../../docs/decisions.md); this harness does
not touch the production scorer.

## Layout

```
bench/portable/
  harness.py     # catalogize -> normalize -> serve real handler -> query -> report/freeze
  refs.json      # 23 frozen gold labels (en / ru / negative), multi-gold aware
  expected.json  # frozen reproducibility reference: digest + catalogSha + codeSha + outcomes
  corpus/        # 13 inert fixtures: scripts/, skills/, bin/ + package.json, .mcp.json
```
