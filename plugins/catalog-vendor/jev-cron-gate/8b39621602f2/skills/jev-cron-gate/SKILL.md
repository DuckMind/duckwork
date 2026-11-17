---
name: jev-cron-gate
description: Use when a cron job burns LLM runs doing nothing. Gate it with Jev.
---

# Jev cron wake gate

Duckwork cron runs a job's pre-run `--script` and skips the agent entirely when the script's
last stdout line is `{"wakeAgent": false}`. This plugin fills that slot with a Jev check:
one yes/no question over a small state snapshot, about 0.5s and a fraction of a cent.

## When to gate a job
Gate jobs whose runs are often no-ops: heartbeats waiting on a human, "check X and report"
loops, nightly synthesis on quiet days. Don't gate jobs where every run matters (deliveries
with a fixed schedule, reports someone reads daily) or no-agent script jobs (no LLM to save).

## Steps
1. `jev_cron_gate(action="setup", name=..., question=..., sources=..., job_id=...)`.
   - `question` is a statement where TRUE means the run is worth it. Name the job's actual
     purpose and what "nothing to do" looks like for it.
   - `sources` is what Jev sees. Give it what a person would glance at to decide: the queue
     file, the last log lines, a `{"changed": [...]}` check on the dirs the job works on.
     Keep it small; the state is capped at 6,000 chars (the tail is kept).
2. `jev_cron_gate(action="test", name=...)`. Check the score and the state preview make sense.
   Rewrite the question if the score contradicts what you'd decide yourself.
3. Attach with the returned command: `duckwork cron edit <job_id> --script jev_gate_<name>.py`.
   This replaces any existing pre-run script on the job; check `duckwork cron list` first.
4. After a few days, `jev_cron_gate(action="status")` shows runs, skips and skip rate per gate.

## Safety rails (built in)
- Fail-open: no key, network error, bad config or Jev error all wake the agent.
- `max_consecutive_skips` (default 4) forces a wake so a job can never stall silently.
- `url` sources are localhost-only. State is sent to TypeSafe: don't point sources at secrets.
