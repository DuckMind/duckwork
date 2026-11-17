# AgentPlaybooks Tools for Duckwork

![AgentPlaybooks Tools for Duckwork](https://github.com/DuckMind/duckwork)

This Agent Plugins package installs the `agentplaybooks-tools` Duckwork skill. It
guides setup of AgentPlaybooks skills, MCP servers, and federated OpenAPI tools
in the selected Duckwork profile, including the authentication those connections
need.

The package itself does not copy credentials, edit configuration in the
background, or register tools. It guides you through the AgentPlaybooks CLI and
Duckwork profile setup. Review each plan before applying it.

## Install

```bash
duckwork plugins install matebenyovszky/agentplaybooks/packages/duckwork-portable/agentplaybooks-tools --no-enable
duckwork plugins enable agentplaybooks-tools
npm install -g @agentplaybooks/cli@0.7.0
apb --version
```

Duckwork needs Node.js 20 or newer to run the CLI. Install the CLI separately;
installing this skill does not install npm packages or require a hosted account.
For a remote Duckwork gateway, Node.js and `apb` must be available on the gateway
host/container, and commands must target the profile that runs there. Installing
the skill into a remote profile does not install the CLI on your Mac or gateway.

## Guided setup (CLI 0.7.0)

Run these commands on the gateway host/container, in the project directory.
`--profile=work` selects a named profile beneath the installation home;
`--duckwork-home=/path` selects the installation home explicitly. Use the same
selection for setup, connect, memory setup and diagnostics.

```bash
apb login
apb duckwork setup <playbook-guid> . --profile=work
apb duckwork setup <playbook-guid> . --profile=work --apply
apb duckwork doctor <playbook-guid> . --profile=work --check
```

The preview checks Node.js, Duckwork, destination permissions and credential
presence, then lists the playbook files to restore and the profile config to
merge. Restore includes complete skill trees and their bundled resources. Hosted
MCP/OpenAPI definitions stay behind the playbook's single MCP endpoint. Existing conflicts
stop the whole setup. Hosted tools use a single playbook MCP connection; upstream
service keys remain in the AgentPlaybooks vault.

The default connection references `APBKS_KEY_AGENTPLAYBOOKS`. Configure a
playbook-scoped key in the selected profile's secret environment; `apb login`
separately authenticates skill downloads with your account key. `--tools-only`
skips file restoration and account login. Keys are never copied into config.

`--apply` verifies MCP initialization and tool listing using this process's
key environment, without invoking any tool. A missing/rejected key gives exit
code 2 even if the files were installed: configure the key, restart the gateway
and rerun `doctor --check` from that environment. A variable declared in the
profile's `.env` is reported separately; it does not prove the running gateway
loaded it. `doctor` without `--check` makes no network calls.

## Connect playbook tools to Duckwork

To let Duckwork call a hosted playbook's MCP tools, including its federated
MCP/OpenAPI services, preview a playbook-scoped connection:

```bash
apb login
apb connect <playbook-guid> --target=duckwork
```

After reviewing the plan, apply it:

```bash
apb connect <playbook-guid> --target=duckwork --apply
```

The plan reports which key environment variable the connection expects. Set a
playbook-scoped API key in the selected Duckwork profile's secret environment.
For an account-wide connection, use `apb connect --account --target=duckwork`
instead and set `AGENTPLAYBOOKS_API_KEY`.

To install a private playbook's skills into the local project, separately preview
and apply `apb pull <playbook-guid> .` followed by
`apb sync . --target=duckwork`. The pull restores the skills; sync registers them
in Duckwork's profile. Public skills can also be installed directly from a
playbook's `/.well-known/skills/` URL.

## Authentication and secrets

- `apb login` authenticates the CLI to AgentPlaybooks with a user API key. The
  key is stored in the CLI credential store, not in a skill or playbook file.
- `apb connect --account --target=duckwork` configures the account MCP connection.
  It refers to `AGENTPLAYBOOKS_API_KEY`; configure that secret in the environment
  used by the selected Duckwork profile and restart Duckwork if needed. An account
  key can reach account-wide tools, so prefer a scoped connection when it covers
  the required workflow.
- `apb connect <playbook-guid> --target=duckwork` configures a single playbook
  connection. Its plan shows the environment variable name (by default
  `APBKS_KEY_AGENTPLAYBOOKS`). Use a playbook-scoped key with only the
  permissions the connection needs, and set it in Duckwork's profile secret store
  or environment, never in `config.yaml`, `mcp.json`, or the skill.
- Federated MCP and OpenAPI credentials belong in the AgentPlaybooks vault.
  Duckwork can call the playbook's tools without putting those upstream secret
  values in the Duckwork configuration.

Use `apb sync` to register skills and merge MCP definitions already present in
the local playbook project into Duckwork. Review its plan before applying it.

## Safety

`apb sync`, `apb pull`, and `apb connect` show a plan and make no local changes
without `--apply`. `apb pull --apply` and `apb sync --apply` write to the
selected Duckwork profile. `apb push --apply` uploads the reviewed project
configuration to AgentPlaybooks. Secret values are never included in that
upload.

See the [CLI guide](https://github.com/matebenyovszky/agentplaybooks/tree/main/packages/cli)
and [Duckwork integration guide](https://github.com/DuckMind/duckwork)
for details.

MIT licensed; see `LICENSE`.
