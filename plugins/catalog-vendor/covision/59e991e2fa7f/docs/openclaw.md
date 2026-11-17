# OpenClaw setup

The bundle declares the Covision Streamable HTTP MCP endpoint. For the production
OAuth client registration, configure the OpenClaw metadata document and then log
in:

```bash
openclaw mcp configure covision \
  --auth oauth \
  --oauth-client-metadata-url https://connector.covisionperformance.com/.well-known/mcp-client/openclaw.json
openclaw mcp login covision
openclaw mcp doctor
```

The browser login requires a Covision account, membership in an organization that
has enabled the connector, and individual consent. The current grant exposes only
`tasks:read`, `meetings:read`, and `knowledge:read`; it can be revoked in
Covision.
