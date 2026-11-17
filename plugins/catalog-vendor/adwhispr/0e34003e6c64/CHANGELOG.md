# Changelog

All notable changes to this project are documented in this file.

## 1.0.1 - 2026-10-12

- Mark the AdWhispr server `untrusted` for Duckwork, so Duckwork asks before every write or spend tool (launches, budget and targeting changes, resume, video render approval) and refuses them in cron and headless runs. Read-only research tools, annotated `readOnlyHint: true` by the server, keep running without a prompt. (Catalog review feedback.)

## 1.0.0 - 2026-10-11

- Initial Duckwork Agent distribution with twenty-four skills across competitor ad research, ad cloning, and campaign execution.
- Connect to the hosted AdWhispr MCP server (`https://adwhispr.com/api/mcp`) through pinned `mcp-remote@0.1.49`, so portable installs can complete OAuth until Agent Plugins v1 can carry remote OAuth configuration natively.
- Paused-creation, two-step confirmation, and approval-before-charge safeguards in every execution and cloning skill.
- Repository validation matching the Duckwork catalog admission command.
