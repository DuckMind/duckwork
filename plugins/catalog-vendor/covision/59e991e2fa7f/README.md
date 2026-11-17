<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Covision Agent Plugin

A vendor-neutral Agent Plugins v1 bundle for Covision. It provides a Covision
skill and declares the production Streamable HTTP MCP endpoint:

`https://connector.covisionperformance.com/mcp`

Covision remains the source of truth for identity, organization access, records,
and audit history. The connector currently exposes read-only access to assigned
tasks, accessible meetings and briefs, and published Covision knowledge.

## Install

Install the bundle from GitHub in a supported agent runtime, then follow the
runtime-specific OAuth configuration:

- [Duckwork setup](docs/duckwork.md)
- [OpenClaw setup](docs/openclaw.md)

OAuth grants require a Covision account, organization membership, connector
enablement by an organization administrator, and user consent. A grant is scoped,
expires, and can be revoked in Covision.

## Security

This repository contains no client secrets, access tokens, credentials, customer
data, or private Covision documentation. Do not add them. The MCP server uses
OAuth authorization code flow with PKCE and returns only data allowed by the
current user’s Covision permissions.

## Development

Validate the JSON manifests:

```bash
node --check scripts/validate.mjs
node scripts/validate.mjs
```

The package has been shaped for the Agent Plugins v1 layout supported by Duckwork
and OpenClaw. Runtime authentication is validated separately against a user’s
actual Covision organization and consent grant.

## License

[Apache-2.0](LICENSE)

## OpenClaw directory

Covision is available on ClawHub as a verified read-only skill: `@covision-admin/covision`. It uses the same MCP connection instructions in [docs/openclaw.md](docs/openclaw.md).
