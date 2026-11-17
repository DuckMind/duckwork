<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# ChorePilot plugin for Duckwork Agent

Duckwork Agent tools for a [ChorePilot](../../README.md) house: device status, lights, climate,
vacuum, blinds, appliances and the household chore board.

```bash
chorepilot mcp token add <person> --client duckwork          # on the ChorePilot machine
duckwork plugins install WestWaters/ChorePilot/duckwork/chorepilot --enable
```

The plugin is a thin, stdlib-only client of ChorePilot's MCP server (`chorepilot run` or
`chorepilot mcp --http`). ChorePilot decides everything from the token's person: water/heat
actions wait for that person's yes in Telegram or the dashboard, a kid's token queues requests
for a parent, unlocking is never available.

Disclosure: each tool call is one HTTP request to `CHOREPILOT_URL` with the bearer token in
`CHOREPILOT_TOKEN`. No other network calls, no files read outside the plugin, no background
processes, no telemetry. Plain `http://` is refused unless the address is this machine or a
private network.

Setup, remote access and tests: [docs/DUCKWORK.md](../../docs/DUCKWORK.md).
