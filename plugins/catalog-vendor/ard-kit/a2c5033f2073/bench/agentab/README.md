# Agent A/B benchmark

A **pilot** behavioural benchmark for ard-kit. It answers one narrow question the retrieval
numbers cannot: **given the same small fixture corpus, the same model, the same
settings and the same budget, does discovering tools through ard-kit help an
agent pick the right tool with less context and fewer wasted actions than plain
filesystem search + read?**

This is the sibling of [`bench/portable`](../portable/README.md). That harness
*pins the scorer* — P@1/P@5/MRR, response bytes and latency against a frozen
digest, deterministically — and its README says outright that "whether discovery
through ard-kit actually helps an agent pick the right tool with less context is
a separate A/B experiment, not this benchmark." **This is that experiment.** It
reuses the same corpus, the same gold intents (`bench/portable/refs.json`) and
the same real `ard_kit.registry` handler, but drives a live tool-calling agent
instead of scoring retrieval.

## What it measures (honestly named)

- **Tool-selection success** — the agent's FINAL pick is in the gold set. Not a
  top-5 hit: the agent must commit to one tool (or decline) via `submit_answer`.
  This scores *picking the right tool NAME* only — it does **not** verify argument
  correctness, a successful invocation, or that the output was useful. "Task
  success" would overclaim; the honest name is tool selection.
- **Actual token spend** — `usage.total_tokens` summed over every LLM round-trip
  in a run. Real tokens from the LLM endpoint, not response bytes. **Total only:**
  no input/output/cached split and no pricing, so this is a context-efficiency
  signal, not a proportional cost/bill claim. A response that carries no `usage`
  now increments a per-run `usage_gaps` marker (and the sum is treated as a lower
  bound) instead of silently counting as 0; the frozen run below predates the
  marker, so it cannot show whether every response reported usage.
- **Tool calls / LLM steps / wall ms** — how much thrash it took to decide.
- **Wrong-tool rate** — committed to a tool that is not in gold.
- **Correct-stop** — on the `negative` group (no tool fits), did the agent say
  `none` instead of forcing a tool?

An LLM is **not deterministic even at temperature 0** (see *Spread* below), so
every task runs `--repeats` times and we report **aggregates + spread**, never
one lucky example. There is deliberately **no frozen digest** here: pinning a
stochastic subject would be false precision. That is the honest counterpart to
the portable benchmark's pinned digest.

## The two modes

Same model, same system-prompt shape, same `--max-steps` and `--token-cap`, same
`submit_answer` contract. Only the discovery surface differs:

| mode | tools | what it is |
|------|-------|------------|
| **A** (baseline) | `list_dir` / `read_file` / `grep` | plain filesystem search + read, sandboxed to the corpus root — path-escape (including via symlink) is rejected, not followed |
| **B** (ard-kit) | `ard_discover` → `ard_inspect` | POST `/search` then GET `/inspect` against the real registry handler |

## Run it

```bash
python3 bench/agentab/ab.py --selfcheck          # hermetic: scripted stub caller, NO network/LLM/server
# live runs: point ARD_AB_BASE_URL / ARD_AB_API_KEY at your OpenAI-compatible endpoint
ARD_AB_BASE_URL=http://127.0.0.1:8000/v1 ARD_AB_API_KEY=... \
  python3 bench/agentab/ab.py --repeats 3         # A and B over all 23 tasks (live LLM calls)
python3 bench/agentab/ab.py --modes B --group negative
python3 bench/agentab/ab.py --model glm-5.3 --repeats 5 --json out.json
python3 bench/agentab/ab.py --rescore results_qwen3.8-max_r3.json  # offline re-score of a saved run, read-only (no LLM)
```

`--selfcheck` asserts the pure scoring/aggregation helpers and drives both loops
with a stub caller, so it is safe to wire into CI. The live runs make real LLM
calls against an OpenAI-compatible endpoint chosen by `ARD_AB_BASE_URL` /
`ARD_AB_API_KEY` (defaults are a neutral local gateway) and are **not** part of
any mandatory selfcheck.

## Frozen result — model `qwen3.8-max`, repeats 3, catalogSha `395eb6372cea`

69 runs per mode (23 tasks × 3 repeats). All 138 machine-readable runs are in
[`results_qwen3.8-max_r3.json`](results_qwen3.8-max_r3.json).

| metric | A (filesystem) | B (ard-kit) | Δ (B vs A) |
|--------|---------------:|------------:|-----------:|
| tool-selection success | 98.6% (68/69) | 100% (69/69) | +1.4 pts |
| wrong-tool | 0% | 0% | — |
| tokens mean (median) | 5632.4 (4302) | 2479.7 (2249) | **−56%** |
| tool calls mean | 6.6 | 3.3 | −50% |
| LLM steps mean | 5.7 | 3.3 | −42% |
| wall ms mean | 8803.5 | 4535.7 | −48% (~2× faster) |
| negative correct-stop | 8/9 | 9/9 | +1 |

Per group the modes are identical on the positives — **en 45/45, ru 15/15** —
and differ only on the negatives (A 8/9, B 9/9).

## Honest findings

- **In this pilot ard-kit led every axis** — under half the tokens, half the
  calls, ~2× faster, and a perfect negative correct-stop. Not tuned to flatter
  ard-kit: corpus, gold labels and prompts are shared with the retrieval
  benchmark and results may favour either mode. **But tokens/calls/steps are the
  trustworthy delta, not wall-ms:** every A run executed before every B run
  (`for mode in A,B`), so B *may* have hit a warm endpoint/caches — the A-before-B
  ORDER is proven, the warmup mechanism is not measured — and the ~2×
  time gap is confounded and needs an interleaved schedule before it is claimed.
  One budget-exhausted A run vs zero in B is also too small a sample for a
  reliability conclusion.
- **Mode A's one failure is NOT proven structural.** On the negative task
  *"mix a multitrack drum recording"* (no such tool) one mode-A repeat burned the
  whole 12-step budget and never submitted (`ans=None`, 14958 tokens, 12 calls),
  but the other two repeats of the SAME task stopped correctly with `none` (6 and
  7 steps). No per-step trace is saved, so we cannot even confirm the budget went
  to `grep` — this is one budget-exhausted run, not a reproducible structural
  failure. What the data does support: confirming ABSENCE by grepping a filesystem
  *can* run long, and a registry that answers `totalResults=0` reports **no match
  for that query** in one step — narrower than proving no suitable capability
  exists, and on this task A usually reached the same `none` anyway.
- **A retrieval-metric failure did NOT sink the agent — but this artifact does
  not prove *why*.** The portable benchmark proved the scorer is cyrillic-blind
  (ru P@1 = 0.60; on pure-Cyrillic queries the `[a-z0-9]+` tokenizer yields an
  empty token set and the intended tool is *not ranked*). Yet both modes score
  **ru 15/15** here. `ard_discover` does return each row's identifier **and
  description** even at score 0, so the agent *could* read descriptions
  semantically and recover what rank drops — **or it could simply have translated
  the query to English first**. This run records only aggregates and the final
  answer (no per-step `ard_discover` args, returned identifiers or scores), so the
  frozen JSON **cannot tell the two apart**. "Descriptions recovered it" is a
  hypothesis, not a result — publishing an external-action trace is a next step
  below. The scorer limitation itself is real, measured in `bench/portable`, and
  not fixed here.
- **Spread at temp=0 is real.** Mode A on *"validate that a file is well formed
  json"*: r0 = 4 calls / 3610 tok, r1 = 8 calls / 4298 tok, r2 = 8 calls /
  4302 tok — same model, same task, same settings. This is why the harness
  reports aggregates over N repeats and refuses a frozen digest.

## Scope of this pilot

- **Fixture, not field.** 23 synthetic tasks over a **13-card** catalog, and
  `refs.json` was authored with the production scorer in view — positives are
  near-verbatim from card descriptions, negatives deliberately use lexicon absent
  from the corpus. Fine as a regression-style set; *discovery-friendly*, not an
  independent control.
- **Pagination barely bites.** `ard_discover` caps at `pageSize=8` over 13 cards,
  so the right card is nearly always in the first page here; at real scale it may
  not be.
- **Equal information, unequal assembly.** Both modes draw on the *same* corpus:
  mode A can `read_file`/`grep` every raw file — including the `.mcp.ard.json`
  sidecar whose descriptions the catalogizer merges into mode B's cards, and the
  script docstrings / skill descriptions behind them — so no descriptive content
  is hidden from A. The measured delta is the *cost of assembling* that content
  into a pick (tokens/steps/calls), not privileged access. Soft spot: `SYS_A`
  names `.mcp.json` but not the `.mcp.ard.json` sidecar, so A is *pointed* at the
  description-less file even though the rich one is discoverable.

## Next controls (named, deliberately NOT run yet)

- **Mode C — static compact catalog, no search.** Inline the same 13 cards and
  forbid `ard_discover`. If C ≈ B, today's value is *auto-assembling a legible
  catalog*, not the scorer, and search only pays once the corpus is too big to
  inline. The single most informative control.
- **Interleave A/B** on a fixed schedule to de-confound wall-time.
- **Record a per-run external-action trace** (`ard_discover` args → returned
  identifiers/scores → next call → answer) to settle the cyrillic question.
- **Split usage** into input/output/cached and apply rates; count API vs tool calls.
- **An independently-worded control set** with harder negatives and a bigger catalog.

## Honesty discipline

Do not cherry-pick a lucky repeat, and do not tune the corpus or the prompts to
make ard-kit look good. The subject is stochastic: re-run with enough
`--repeats` and report the aggregate, including runs where mode A wins or ties.
This harness does **not** touch the production scorer — mode B reuses the real
`ard_kit.registry` handler via `harness.serve()`, read-only.

Scoring is strict: the final answer is normalized as ONE whole identifier (name,
path or URN), and prose, enumerations and contradictions (`csv_to_json word_count`,
`none, use weather-lookup`) are rejected rather than token-matched. Re-scoring the
frozen 138 runs offline under this rule (`--rescore`, read-only, no LLM calls)
changed **0** verdicts — every stored answer was already a single clean identifier
or a bare `none` — so the numbers above stand as published.

## Layout

```
bench/agentab/
  ab.py                        # agent loop: modes A/B, scoring, aggregation, hermetic --selfcheck
  results_qwen3.8-max_r3.json  # one frozen live run: summaries + all 138 runs (no digest by design)
  README.md
  # reuses ../portable/{corpus,refs.json,harness.py} — no separate task set
```
