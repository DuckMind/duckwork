# Operator playbook (measured lessons)

Authoring rules for build sprints, fleets of children, and babysitting long runs.
The graph vocabulary lives in [grammar.md](grammar.md), the read model and recovery
reference in [operations.md](operations.md); this file collects the failure modes
observed across many build waves, each rule earned by watching a run die. Terms
used here are defined on first use: the **effective fingerprint** (efp) is the
content hash every node definition carries — when the stored efp equals the hash
of the current definition, the node is current; **interrupted** is the run state
for unfinished work with no verified live runner (see operations.md).

## Build-sprint lanes (parallel agent lanes on one repo)

- **One runner per worktree.** Pre-create every lane's worktree yourself before
  `run`; the goal says "your worktree ALREADY EXISTS, never create one". Two runs
  on the same worktrees — e.g. after a gateway restart killed the first wave and
  you relaunched without noticing the old run resumed too — put two children in
  one branch; the survivor spends its whole budget diagnosing the collision. Use
  a distinct `lane_key` per worktree so the in-flight dedupe refuses the second
  launch.
- **The timeout wall, not the turn cap, is the binding limit** on a slow route:
  work out turns × realistic per-call latency before you pick a `timeout`. On a
  route where each call takes ~80 s, a 90-turn child needs ~2 h — a 3600 s
  timeout kills it around turn 45 with everything uncommitted. A wave where half
  the lanes hit the timeout wall with zero commits shows the `timeout` was set
  from the shape preset instead of measured latency: set explicit `timeout` ≥
  `max_turns` × real per-call latency, or cut `max_turns`.
- **Commit before the timeout kills the lane** — the repo's
  `scripts/lane_recover.py` replays a dead lane's journaled `write_file`/`patch`
  tool calls from its session database into a restore directory, so an
  uncommitted tree is recoverable but lossy; a committed WIP ("`git add -A &&
  git commit -m 'WIP (recovered)'`") is not. Encourage lanes to commit early and
  often in the goal; read a dead lane's commits before paying to re-run it.
- **Merge in dependency order and run the FULL suite after each merge**, never
  after the batch — regressions show up as one existing test failing, and batch
  attribution is guesswork.
- **Lane scratch homes:** lanes commit their scratch `DUCKWORK_HOME` (state.db,
  SOUL.md, run dirs) unless the fixture home is under `tests/` and gitignored.
  The scrub audit and graph gate catch it, but only after you built over it.
- **Size the plan from measured timings, not from hope.** Before choosing lane
  count, timeout walls, or depth, open the last run's `events.jsonl` and compute,
  per node: the wall time of each finished item (`item.finished` minus
  `item.started` per fan-out index) and the spread between the fastest and slowest
  item (the stragglers). From those numbers you can see the realistic single-item
  time, the serial floor for the whole workload, how much a straggler tail adds,
  and how many lanes the work splits into cleanly. Splitting into lanes only pays
  when the items are large relative to that per-item time AND their write-sets are
  disjoint; otherwise the barrier and merge cost eats the gain. Synthesize over
  short per-lane manifests, merge on arrival.
- Give lanes two items each with `file:line` anchors **in the goal**. A lane given
  seven items and "find the code" spends its budget on recon; lanes handed the
  previous wave's recon findings started at code and shipped.
- **For authored work, route the review node to a consenting second profile from
  the start** (the `profile` node field plus the target's `workflow_team.json`
  consent — see operations.md). A review node running under the same profile that
  wrote the change answers for its own work — don't burn a node on it.

## Fleet children (audits, censuses, sweeps)

- **Write-first contract on flaky providers:** children create the artifact file
  FIRST and append findings after every 1–2 probes; the final answer is a pointer
  line. A connection-error death otherwise loses a finished investigation whose
  evidence already landed.
- **FILE-FIRST for big payloads:** any child whose answer can exceed a few KB
  writes the artifact to a file and returns only `{path, ≤200-char summary}` — a
  huge JSON answer line-truncates and fails schema, losing finished work.
- **Size the fan-out to the container's memory cgroup** (`memory.max` /
  `memory.current`), not host RAM — children are processes inside it; an OOM kill
  mid-wave takes parent and children and discards everything not mirrored.
- **Durable ground:** copy every lane artifact out of ephemeral scratch into a
  durable directory the SAME turn the wave lands; later waves read only durable
  copies.
- A lane emitting the SAME tool error repeatedly is looping, not working:
  `status` shows rising idle with flat counts — `stop` it (or amend it out) and
  run its 3–5 probe commands yourself; sibling artifacts usually hold the answer.
- Every child gets the same hard-rules preamble in `context`: read-only on
  production, writes only under one named scratch dir, forbidden hosts named,
  honest-unknown valid, invented evidence not, cite exact commands + values.
- **Fan-out waiting and committing are separate rules:** with `quorum` unset the
  node waits for EVERY item (no straggler cancellation) but COMMITS at majority
  (`len(items)//2 + 1`) — one flake in a lane of 3+ still commits with partial
  credit and survivors in `output.items`. Set `quorum:<n>` explicitly when you
  want early straggler cancellation or a stricter/looser commit bar. When the
  stragglers may still land useful work, add `quorum_drain_s:<seconds>` (>= 0,
  only legal with `quorum`): the kill is deferred by one drain window armed at
  the quorum moment — anything that lands inside it commits, and only what is
  still running at the deadline is cancelled. Default `0` = immediate cancel at
  quorum. And read
  `failed_items`/`failed_detail` on a committed node — done does not mean every
  item passed.

## Babysitting (read the status model, not `ps`)

- **Stall detection:** a running node whose idle grows with flat `api_calls` is
  stalled — `steer` it or `stop` + amend; don't wait it out.
- **The host kills a long tool call at its own deadline** — typically around 420 s
  on the default concurrent-batch setup, but host-dependent, not a plugin
  constant. `wait` self-yields in 330 s segments with a "call wait again" note —
  loop on `wait` until terminal, and never let your own sleeps approach that
  deadline.
- **STALENESS law for any external observer:** a node record stays present with
  its OLD efp (effective fingerprint) while a re-run is in flight — the new
  record replaces it only at commit. Freshness = stored efp EQUALS current
  `wfcommon.efp(byid, node)`; efp presence proves era, not currency. Reuse
  `wfcommon.node_rec`; never invent a second validity rule.
- Failed fan-out nodes still commit survivors (`output.items` + `failed_detail`)
  — read them before rebuilding; and inspect a capped child's partial files
  before paying to re-run it.
- Recover publication-only failures publication-only: keep the finished
  investigation, amend only the failed handoff with an explicit fenced-JSON
  result contract. CLI banners around bare JSON can make a substantively
  finished review fail schema parsing.

## Ergonomics

- **Never hand-transcribe graph JSON over ~2 KB** — build the graph as a Python
  dict, `json.dumps` + `json.loads` to validate, then emit the compact string
  verbatim (or write it to a file and use `graph_path`). Generated graphs launch
  first try; hand-pasted ones waste calls on bare `not valid JSON` errors.
- **Model routing: pin provider+model when it matters.** A literal id that is a
  profile alias's TARGET can resolve differently than the alias (HTTP 400/404
  from the wrong route), and an alias can preflight its bare name to the provider
  and die 404 (`opus` → `anthropic/opus` while the alias meant `claude-opus-5-5`).
  For anything but the profile default model, pass
  explicit `provider` + literal `model`, read the `run` response's resolved route
  table — and check the child's served-model stamp before trusting execution.
- Bound reasoning effort as well as turns on recon nodes: set an explicit effort
  level, make recovery consume existing artifacts, narrow unfinished checks;
  raising the timeout alone does not make a child write its conclusions.
- For a graph you'd build the same way again: `save` it with a trigger
  description (plus `source` for provenance). One-offs stay in their run dir.
