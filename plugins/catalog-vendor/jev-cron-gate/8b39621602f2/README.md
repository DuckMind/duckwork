# jev-cron-gate

Skip Duckwork agent cron runs that would do nothing.

Agent cron jobs often wake up, spend a full LLM run, and report "still waiting." Duckwork cron
already supports a wake gate: if a job's pre-run script prints `{"wakeAgent": false}` as its
last line, the agent run is skipped. This plugin fills that slot with a
[TypeSafe Jev](https://docs.typesafe.ai) check. Jev scores one yes/no question ("would
running now do useful work?") over a small snapshot of the job's state, in about 0.5s and
for a fraction of a cent.

## Install

```bash
duckwork plugins install jev-cron-gate --enable
# TypeSafe key in your profile .env (JEV_API_KEY also works):
echo 'TYPESAFE_API_KEY=...' >> ~/.duckwork/.env
```

## Use

Ask the agent to gate a job, or call the tool yourself:

```text
jev_cron_gate(action="setup", name="heartbeat", job_id="3ce7f1ea833a",
  question="Running the agent now would make real new progress, rather than re-reporting that it is still waiting on approval.",
  sources='[{"file": "~/proj/APPROVALS.md"}, {"file": "~/proj/log.jsonl", "tail": 900},
            {"changed": ["~/proj/src"]}]')
jev_cron_gate(action="test", name="heartbeat")      # dry run: score + state preview
duckwork cron edit 3ce7f1ea833a --script jev_gate_heartbeat.py
jev_cron_gate(action="status")                      # runs, skips, skip rate per gate
```

Sources are what Jev sees: `{"file", "tail"}`, `{"changed": [paths]}` (modified since the
agent last ran?), `{"url"}` (localhost only), `{"text"}`. The combined state is capped at
6,000 characters.

## Safety

- **Fail-open.** A missing key, bad config, network error or Jev error wakes the agent.
- **No silent stalls.** After `max_consecutive_skips` skips in a row (default 4), the agent is woken anyway.
- **Data leaves the machine.** The state snapshot is sent to TypeSafe. Don't point sources at secrets.
- Stdlib only, no hooks. Each decision is logged to `<DUCKWORK_HOME>/jev-cron-gates/log.jsonl`.

## Config

`<DUCKWORK_HOME>/jev-cron-gates/<name>.json`: `question`, `sources`, `skip_below` (default 0.2),
`max_consecutive_skips` (default 4). The tool writes it for you.

MIT licensed.
