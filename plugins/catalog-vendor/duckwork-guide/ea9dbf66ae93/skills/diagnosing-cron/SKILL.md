---
name: diagnosing-cron
description: Diagnose Duckwork cron job issues — jobs not firing, scheduler dead, wedged fire-claim, timezone issues, and delivery failures.
version: 1.0.2
metadata:
  duckwork:
    tags: [duckwork, cron, scheduling, troubleshooting]
    related_skills: [duckwork-configuration-guide, diagnosing-gateway]
---

# Diagnosing Cron Jobs

Goal: reduce any cron problem to one concrete fix — a schedule expression, a gateway restart, or a delivery target. Cron jobs are agent sessions that fire on a schedule.

## 1. Configuration shape

```yaml
# ~/.duckwork/config.yaml
cron:
  allow_agent_scheduling: true   # default: false — allows agent to manage cron jobs
```

Jobs are created via `duckwork cron create` or the cronjob tool:

```bash
duckwork cron create "0 9 * * 1-5" \
  "Pull yesterday's commits from the repo at ~/work/project, summarize what changed" \
  --skill git-summary \
  --name "Weekday standup prep" \
  --deliver telegram
```

## 2. How to inspect

- `duckwork cron status` — scheduler health (gateway process, ticker heartbeat, last successful tick)
- `duckwork cron doctor` — grouped, per-job issues (exits 1 if any finding)
- `duckwork cron list` — all jobs, states, next_run times
- `duckwork cron runs <job_id> --limit 20` — execution ledger (not just the job row)
- `duckwork cron run <job_id>` — trigger the job immediately (for testing)
- `duckwork logs` — view recent Duckwork logs
- `~/.duckwork/logs/agent.log` — scheduler messages
- `~/.duckwork/logs/errors.log` — warnings and errors

## 3. Pitfalls (symptom → cause → fix)

1. **Job not firing** — (a) scheduler not running (gateway down); (b) `next_run_at` parked in the past beyond 15-minute grace window; (c) wedged fire-claim. → Run `duckwork cron status`; check `duckwork cron doctor`; restart gateway (`duckwork gateway restart`).
2. **Job shows `last_run_at: null` and `last_status: error`** — known issue (#21867): `action='run'` only set `next_run_at = now` but didn't execute. → Fixed in v0.21.2+; upgrade Duckwork; use `duckwork cron run <job_id>` to test.
3. **Job fires at wrong time** — (a) timezone mismatch (cron uses UTC); (b) schedule expression wrong. → Verify cron expression; check system timezone; use `duckwork cron list` to see next_run times.
4. **Job runs but delivery fails** — (a) deliver target (telegram/discord/etc.) not configured; (b) token expired; (c) platform API error. → Check deliver target config; verify platform tokens; check `duckwork logs` for delivery errors.
5. **Job runs but produces no output** — (a) skill not installed; (b) skill error; (c) model/provider issue. → Check `duckwork cron runs <job_id>` for output; verify skill installed; check model config.
6. **Scheduler dead** — (a) gateway not running; (b) ticker heartbeat missing; (c) resource exhaustion. → Run `duckwork cron status`; check `duckwork gateway status`; restart gateway; check system resources.
7. **Job stuck in "running" state** — (a) job crashed but state not updated; (b) concurrent execution blocked. → Check `duckwork cron list` for state; restart gateway; check for duplicate jobs.
8. **Agent can't create cron jobs** — `cron.allow_agent_scheduling` not set to true. → Set `cron.allow_agent_scheduling: true` in config.yaml.

## 4. Localization workflow

1. `duckwork cron status` — verify scheduler is alive.
2. `duckwork cron doctor` — check for per-job issues.
3. `duckwork cron list` — verify job exists and is active.
4. `duckwork cron runs <job_id> --limit 5` — check execution history.
5. Match the failure: not firing → pitfall 1; wrong time → pitfall 3; delivery fails → pitfall 4.
6. Apply the fix, `duckwork cron run <job_id>` to test, and verify with `duckwork cron list`.

## 5. Cross-references

- `duckwork-configuration-guide` — for $DUCKWORK_HOME resolution and config.yaml structure
- `diagnosing-gateway` — for gateway connectivity and platform issues
- `diagnosing-bot-mode` — for bot routine/cron integration

## Report

This skill diagnoses cron job issues — jobs not firing, scheduler dead, wedged fire-claim, timezone issues, and delivery failures. When you run the diagnostic workflow, present findings in the standard format below.

### Summary
Your cron job is not firing because the scheduler is not running — the gateway process is down. The cron ticker heartbeat is missing and `next_run_at` is parked in the past beyond the 15-minute grace window.

### Findings
| Severity | What | Evidence |
|---|---|---|
| HIGH | Gateway process is down — scheduler not running | `duckwork cron status` shows `scheduler: stopped`; `duckwork gateway status` shows `gateway: not running` |
| MEDIUM | `next_run_at` parked in the past beyond grace window | `duckwork cron list` shows `next_run_at: 2026-10-07T09:00:00Z` (yesterday) |

### Recommended Fix
Run `duckwork gateway restart` to bring the gateway (and scheduler) back up, then verify with `duckwork cron status` and `duckwork cron list`. If the job still does not fire, run `duckwork cron run <job_id>` to test it manually.

### References
- `~/.duckwork/logs/agent.log` — scheduler messages
- `~/.duckwork/logs/errors.log` — warnings and errors
- `duckwork_cli/cron.py` — cron CLI commands
- `cron/jobs.py` — job execution logic

*Facts re-verified 2026-09-21 against upstream source at commit `cedf4a3d78675283fa93e4e6ea2d6212bf414667`: `duckwork_cli/cron.py`, `cron/jobs.py`; plus the official docs (duckwork-agent.fordex.com/docs/user-guide/features/cron). Re-verify before reuse.*
