# Agent Analytics Duckwork Plugin
<img width="1489" height="1056" alt="image" src="https://github.com/user-attachments/assets/5c619893-ae0b-425b-97f3-c65d1cbebc28" />

Dashboard-only read plugin for Duckwork.

v1 scope:
- browser-login-first for existing Agent Analytics accounts
- project selection inside the Duckwork dashboard
- read-only project summary, pages, events, and insights
- empty states that point users back to the Agent Analytics Duckwork skill when setup is not done yet

## Install in local Duckwork

Install from GitHub with the Duckwork plugin installer:

```bash
duckwork plugins install Agent-Analytics/agent-analytics-duckwork-plugin --enable
duckwork dashboard
```

Update an existing install:

```bash
duckwork plugins update agent-analytics
duckwork dashboard
```

Clean reinstall:

```bash
rm -rf ~/.duckwork/plugins/agent-analytics-duckwork-plugin  # legacy install path, safe to remove
duckwork plugins install Agent-Analytics/agent-analytics-duckwork-plugin --force --enable
duckwork dashboard
```

The plugin appears as a `Signals` item in the Duckwork web dashboard's left sidebar, using a monochrome Agent Analytics logo as its menu icon.

## Telemetry

This plugin includes telemetry. Usage of this plugin is reported to Agent Analytics so we can understand how the product is used and improve the experience.

## Development

```bash
npm install
npm test
npm run build
```
