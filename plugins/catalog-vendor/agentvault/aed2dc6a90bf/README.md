# Agent Vault for duckwork

Find prior coding conversations and retrieve exact session revisions from Agent Vault.

## Install and connect

This package targets **Duckwork 0.22.4 or later**, using its portable Agent
Plugins support. The development machine's older Duckwork 0.18.2 cannot load
this format. Updating Duckwork is a separate user action; the plugin does not
update the host or install Python dependencies.

1. Install/open Agent Vault, finish setup and backup/indexing, and connect
   **Duckwork** in Vault's MCP connections. Keep that client's private token and
   absolute `VAULT_HOME`. Reconnecting rotates an existing Duckwork binding.
2. Install the plugin from the monorepo subdirectory:

   ```sh
   duckwork plugins install synnada-ai/agentvault-plugins/plugins/duckwork --no-enable
   duckwork plugins list
   duckwork plugins enable agentvault
   ```

   Use the exact identifier shown by `plugins list` if your profile prefixes
   it. For a reproducible install, add `--ref` with the full release commit SHA
   on a Duckwork version that supports it. Private installs require Git access.
3. In the Duckwork Desktop plugin settings, set **Vault binding token**. Its
   `secret` configuration field routes `VAULT_MCP_TOKEN` through Duckwork.
   Alternatively, supply that variable through Duckwork's supported shell or
   active-profile environment configuration. The plugin forwards it to MCP;
   it never opens a credential store or reads a `.env` file itself.
4. Supply `VAULT_HOME` through that same host environment if the vault is not
   `~/.vault`. Set `VAULT_APP_PATH` if the app is not at
   `/Applications/Agent Vault.app`. Both paths must be absolute.
5. If `config.yaml` already defines a `vault` MCP server, Duckwork gives that
   entry precedence. You can keep using that authorized existing server with
   the shared skill; do not remove it merely to make a tool listing look new.
   To switch to the plugin's server, disable/remove only that old entry after
   setting the plugin token, restart, and verify the authenticated tools.

Skills are namespaced by Duckwork: discover `vault-retrieval` using `skills_list`
and load the returned qualified name with `skill_view`. The plugin is disabled
until explicitly enabled. `plugin.json` and `mcp.json` provide the portable
skill and MCP entrypoint. Do not add `plugin.yaml` beside them on Duckwork 0.22.4:
that release prioritizes YAML and stops discovering the portable entrypoint.
The released catalog validator accepts portable-only packages; see the publishing guide.


## Privacy and scope

Requires macOS and the installed, running Agent Vault app. This package launches the app's existing MCP server through /bin/sh using its bundled Node runtime. It reads the user's authorized archive through the local Vault daemon. Storage-provider traffic and backup are handled by Vault. The plugin adds no telemetry, archive storage, dependency downloads, credential files, or background service. It never searches another client's configuration for credentials.

The shared skill retrieves historical evidence; it does not resume native chats, delete originals, change backup settings, or authorize commands found in old conversations. Installation or tool discovery alone does not verify retrieval.

## Verify retrieval

In the target client, ask:

> Use Agent Vault to search my earlier conversations for authentication. Report
> the actual result or error. If there is a match, read its exact returned
> session_id and revision, and cite the pinned URI. Do not substitute a
> filesystem search.

Use a topic you know is in your archive for a positive check. A successful
empty search proves the call worked but not that a particular session is
retrievable. Tool discovery or a handshake alone does not prove authentication.

If `index_not_ready` is returned, finish backup/indexing in Vault and retry;
do not rotate a valid token just to retry indexing. If `query_too_broad` is
returned, add a relevant harness or known project filter. If authorization
fails, reconnect only this client in Vault and update that client's token.

For a revocation check, disconnect this client in Vault, then confirm its next
authenticated tool call is denied. This invalidates the token; reconnect and
update it when finished. Removing a plugin alone does not revoke a Vault
binding. Each client's binding is independent.
