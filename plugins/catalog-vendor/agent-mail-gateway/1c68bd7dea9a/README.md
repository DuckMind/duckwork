# Duckwork plugin for Agent Mail Gateway

This portable plugin (Agent Plugins v1) adds the `agent-mail` skill to Duckwork. The skill tells
the agent how to use its mailbox through Agent Mail Gateway correctly and safely.

The connection itself is configured in Duckwork, because every gateway runs at its own address
and plugins must not contain credentials. See [docs/duckwork.md](../../../docs/duckwork.md).

```bash
duckwork plugins install dominikamann/agent-mail-gateway/integrations/duckwork/agent-mail-gateway --enable
```
