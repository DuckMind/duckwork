# Duckwork surfaces: scheduled work and delivery

Use Duckwork features only when they genuinely improve the advertising workflow. Do the requested
analysis first; scheduling and presentation come after the answer.

## Scheduled work

Duckwork exposes scheduled tasks through the `cronjob` tool. It can create, list, pause, resume, edit,
run, and remove one-time or recurring jobs.

Good advertising uses include:

- a weekly cross-platform performance review;
- a mid-month budget-pacing check;
- a recurring check for disapproved ads; and
- an alert when CPA or spend crosses a user-approved threshold.

When creating a scheduled advertising task:

1. Attach the relevant Adspirer skill.
2. Set the brand project's absolute work directory so the run can read `BRAND.md` and `STRATEGY.md`.
3. Name the connected Adspirer MCP toolset when the Duckwork surface exposes toolset selection.
4. Prefer creating the job paused when the prompt could write to an ad account; let the user review
   it before enabling recurring execution.
5. State that every run consumes Adspirer tool calls like an interactive session.

Weekly is the normal default for a performance review. Daily is appropriate only when the account's
spend and risk justify the additional calls. `get_usage_status` is free and shows remaining quota.

Scheduled runs must not make unattended budget, bid, launch, archive, or deletion changes. Schedule
read-only reporting and monitoring by default. If the user needs server-side monitoring that runs
independently of their Duckwork gateway, use Adspirer's `monitoring_and_reporting` router instead.

## Delivery and privacy

Duckwork cron results can return to the originating conversation, a local file, or a configured
messaging destination. Advertising performance, spend, customer lists, and lead-form submissions
are confidential. Confirm the destination before sending client data outside the current local
session.

If the user wants an email brief or a persistent threshold alert, Adspirer's server-side monitoring
tools are the better fit. Discover them with `{"action": "list_tools"}` on the
`monitoring_and_reporting` router.

## Failure behavior

- If the Adspirer MCP connection is unavailable, do not invent metrics; report the connection error.
- If authentication expired, ask the user to run `duckwork mcp login adspirer`.
- If the scheduled job lacks access to the brand workspace, update it with the correct absolute work
  directory instead of recreating brand context from guesses.
- If quota is exhausted, say where the run stopped and what remains.
