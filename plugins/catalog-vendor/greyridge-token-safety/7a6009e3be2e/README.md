# greyridge-token-safety (agent skill)

Drop-in `SKILL.md` (OpenClaw / Duckwork / Claude-style skills) that gives an agent a pre-trade
safety check for Base ERC-20 tokens via the Grey Ridge x402 API. Free preview needs only `curl`.

Install: copy `skills/greyridge-token-safety/SKILL.md` into your agent's skills directory, or `duckwork plugins install greyridge-token-safety` once catalogued.

Disclosure: the skill only tells the agent to run `curl` against https://x402-data-api.sigrunner.workers.dev (a third-party HTTPS service) with a token address; no credentials, no files read, no background processes, no telemetry.

API: https://x402-data-api.sigrunner.workers.dev · contact@greyridgesignals.ai
