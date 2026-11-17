# Workflow examples

Batteries-included [`wf/1`](../references/grammar.md) graphs you can run with the
seeds declared in their descriptions (`workflow run graph_path=...`), fork as a starting point, or shelve into your
library (`workflow save graph_path=... name=...`). Each file's top-level
`description` is the full contract — seeds it expects, arms it can take, and
what each node owns; this page is just the map.

Every example with a `receipts/<name>/author-run.json` beside it has been **run
for real** against a live target: the receipt pins the graph digest and the run
ids of the laps that proved each arm (including the halt arms — a template
whose failure path has never fired is a decoration). The rows without a receipts
dir are validated cold (structural tests + `validate`), not smoke-run — treat
them as blueprints, not proofs.

Every example ships with a derived diagram — table, queue, and the
DIAGRAM LAW v1 layout spec live in [diagrams/README.md](diagrams/README.md) — the
repo docs tree; the runtime zip ships maps and graphs, not art.

## basics/ — one idea each, read these first

| File | Shape | Teaches |
|---|---|---|
| [`smoke.json`](basics/smoke.json) | 1 echo node | The smallest legal graph; zero tokens. |
| [`approve-publish.json`](basics/approve-publish.json) | draft → human gate → single arm | The two gate laws: a human `gate` holds until released, and complementary `when` + `on_skip: "prune"` branches route exactly one arm. |
| [`branch-on-verdict.json`](basics/branch-on-verdict.json) | judge → verdict-branch pair | Routing on a *machine* answer instead of a human one. |
| [`exchange-run.workflow.json`](basics/exchange-run.workflow.json) | echo → courier → leaf | Byte portability: a graph travels save → library → re-run and the hand-off is proven by re-reading committed records, never chat memory. |

## build/ — fan-out, barriers, ledgers

| File | Shape | Teaches |
|---|---|---|
| [`triage-route.workflow.json`](build/triage-route.workflow.json) | intake → classifier → route pair | Queue triage: a boolean the grammar *can* see (`has_urgent`) routes either a human escalation or a rule-driven batch; each arm hangs only on its own route gate. |
| [`bulk-transform.workflow.json`](build/bulk-transform.workflow.json) | manifest → per-item lanes → audit | Barrier fan-out: the audit reconciles `all_results` against the declared manifest *and* re-checks the filesystem — evidence-without-command is a failed lane. |
| [`census-fanout.workflow.json`](build/census-fanout.workflow.json) | roster → no-quorum barrier → tally | Deterministic tally over N machines: every item answered or *named missing*, counts computed from the record, a dead gauge prints as a loud red row, never silent loss. |
| [`quorum-probe.workflow.json`](build/quorum-probe.workflow.json) | raced probe ‖ reconciled barrier | The speed/coverage contrast in one run: `quorum` cancels stragglers (report them honestly); the no-quorum barrier reconciles survivors against a master catalog. |

## review/ — independent judgment

| File | Shape | Teaches |
|---|---|---|
| [`blind-council.workflow.json`](review/blind-council.workflow.json) | blind seats → synthesis | Independent review: seats never see each other, synthesis must carry a verify-list; seats pin capability *classes*, not vendor models. |
| [`portable-review.workflow.json`](review/portable-review.workflow.json) | recon → 2-way fan-out → synth | A review that runs on any estate with no host vocabulary in its goals. Seeded run: `run_context` `target_dir` = the directory to review (every node spawns in an empty per-node work dir, so the target must be named). |
| [`escalation-ladder.workflow.json`](review/escalation-ladder.workflow.json) | builder → verifier → branch | Verify-then-branch: a fresh verifier outranks the builder's claim; verified lands behind a human gate, failed escalates the *whole packet* to a human hold. `after_partial` keeps a partially-dead verifier from darkening the packet. |

## release/ — the SDLC back half

| File | Shape | Teaches |
|---|---|---|
| [`issue-to-pr.workflow.json`](release/issue-to-pr.workflow.json) | triage → halt ‖ work → verify → gate → publish | The distilled *→PR lifecycle: abort *before* investment on non-work, baseline-then-delta testing, and a publish arm that cannot run unless the verify arm said ok. |
| [`release-lifecycle.workflow.json`](release/release-lifecycle.workflow.json) | preflight → prep → **verify** → publish → **await-ci** ‖ channel checks → closeout | Fail-closed drift: an *independent* verify node catches a bump that touched one artifact but not another and structurally halts; await-ci is a **machine gate** parking on a fixed probe argv while CI finishes (zero tokens while parked). |
| [`submit-pr.workflow.json`](release/submit-pr.workflow.json) | preflight → validate → draft → gate → submit → **verify** | The reusable *→PR stub: whatever built the branch (issue-to-pr, a hand session, anything), this owns 'code done' → 'PR verified live' — secret-scan preflight, the repo's own validation re-run by the workflow itself, a human submit gate, and an independent API read-back that never trusts the submitter's word. Plug it in wherever; never merges. |
| [`gated-publish.workflow.json`](release/gated-publish.workflow.json) | draft → owner gate → one arm | The template-of-templates for human-authorized publishes. |
| [`machine-watch.workflow.json`](release/machine-watch.workflow.json) | zero-token poll → release on exit 0 | Scheduled watching: `until_argv` machine gate, `lane_key` dedup for cron double-fire. |

## ops/ — incident & fleet

| File | Shape | Teaches |
|---|---|---|
| [`incident-response.json`](ops/incident-response.json) | alert → sweep → verdict-branch → recovery probe → close | Full incident lifecycle: verdict-branch gate pair, machine recovery probe with human escalation, merge-gated close. Adapt the lanes to your stack. |

## Running one

For portable-review, choose an existing directory containing at least two
readable files. Pass its absolute path explicitly: every agent starts in its
own work directory, not the directory containing the graph.

```jsonc
workflow { "action": "run",
           "graph_path": "/abs/path/to/clone/examples/review/portable-review.workflow.json",
           "run_context": { "target_dir": "/abs/path/to/files-to-review" } }
```

Then `wait` on the returned `run_id`. Without a target this is not a useful
review; an empty target cannot supply the review fan-out.

For issue-to-pr:

```jsonc
workflow { "action": "run",
           "graph_path": "/abs/path/to/clone/examples/release/issue-to-pr.workflow.json",
           "run_context": { "repo_dir": "/abs/path/to/clone", "issue_file": "/abs/ISSUE.md", ... } }
```

`graph_path` is resolved by the door on the machine running it — pass the
absolute path, not a repo-relative one. Seeds for each graph are listed in its
`description`. Author settings (model,
provider, effort) come from your plugin settings block — the templates
deliberately don't pin them. Then `wait` on the returned `run_id` until the
terminal status; held gates surface in the same call.
