<div align="center">

# Render for Duckwork

Use Render's existing skills and tools from Duckwork to deploy, debug and manage applications.

[![Duckwork plugin](https://img.shields.io/badge/Duckwork-plugin-6C47FF)](https://duckwork-agent.fordex.com/docs/developer-guide/plugins) [![Render skills](https://img.shields.io/badge/Render-20_skills-000000)](https://github.com/render-oss/skills) [![MIT license](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

[Quickstart](#quickstart) · [Try it](#try-it) · [How it works](#how-it-works) · [Troubleshooting](#troubleshooting)

</div>

This community plugin bundles Render's maintained skills and connects Duckwork to the [Render MCP server](https://render.com/docs/mcp-server). MCP (Model Context Protocol) is how Duckwork discovers and calls Render's tools. A first check can list the workspaces your account can access without changing anything.

The skills come from [render-oss/skills](https://github.com/render-oss/skills). Included files are unchanged. This package is maintained by [Ojus Save](https://github.com/ojusave); catalog inclusion is subject to Fordex review.

## Quickstart

### Prerequisites

- [Duckwork installed and connected to a model](https://duckwork-agent.fordex.com/docs/getting-started/installation), with portable plugin and remote MCP support. If these features are unavailable, run `duckwork update` first.
- A Render account and a [Render API key](https://dashboard.render.com/u/settings#api-keys) for the workspaces you intend to use.
- For Blueprint validation and command-line operations, the [Render CLI](https://render.com/docs/cli) installed on the same computer or server as Duckwork.

Run the following commands in your computer's terminal, from any directory. They install the plugin on the machine running Duckwork.

### 1. Prepare Duckwork and install

Enable Duckwork's MCP support, then install the plugin without enabling it:

```bash
duckwork pm install --extra mcp
duckwork plugins install ojusave/render-duckwork-plugin --no-enable
```

Review Duckwork's source and security prompts. The package adds skills and a remote tool connection. It has no custom runtime code or plugin-specific Python dependencies; the first command installs Duckwork's MCP support. Successful installation leaves it disabled until you enable it.

### 2. Add your Render key

Ask Duckwork where the active profile stores environment settings:

```bash
duckwork config env-path
```

Open the printed file in a text editor. Create it if it does not exist. Add this line, replacing the example value with your API key:

```dotenv
RENDER_API_KEY=your_render_api_key
```

Save the file. This key lets Render's server act with your account's permissions. Keep it in that profile file, outside your project and plugin repository. Do not paste it into chat. If you already keep `RENDER_API_KEY` in the active profile or a Duckwork-supported secret manager, use that existing value.

### 3. Enable and check the connection

```bash
duckwork plugins enable render-platform
duckwork plugins list
duckwork plugins show render-platform
```

The plugin should show as enabled. Start a new Duckwork chat so it discovers the added skills and tools, then use the read-only prompt below to verify the connection. If you use Duckwork through its messaging gateway, restart it with `duckwork gateway restart` after changing plugins or credentials.

Duckwork asks for approval when the Render server does not explicitly mark a tool as read-only. This currently includes the workspace listing. Review the requested tool and choose **Allow once** for that check. Unattended runs reject calls that need approval. Your account permissions still apply.

If you already configured a server named `render` in Duckwork, that configuration takes precedence over the package's connection, including its authentication and approval settings. See [existing connections](#existing-render-connection) before relying on the package's defaults.

## Try it

Start Duckwork in the same terminal:

```bash
duckwork
```

Ask:

```text
Use the Render plugin's skills to check that my Render connection works.
List the workspaces I can access, but do not select a workspace or change anything.
```

When Duckwork asks to run `list_workspaces`, choose **Allow once**. Success means Duckwork returns the workspaces from the real Render connection. An empty list or authentication error needs investigation before deploying anything.

An abbreviated response from a successful run, with workspace names omitted:

```text
Your Render connection works. The read-only workspace listing returned:
[workspace names omitted]
No workspace was selected and nothing was changed.
```

For a local configuration task, open Duckwork in your application's directory and ask:

```text
Use the Render deployment skill to prepare a render.yaml for this project.
Use paid compute, explain the proposed resources, and validate the file with
Render's CLI. Do not deploy, commit, push or change existing services.
```

This produces a local deployment configuration. A valid file is not a deployed application. Review it before asking Duckwork to create or modify Render resources; those operations can incur charges.

## How it works

```mermaid
flowchart TD
    H["Duckwork on your computer or server"] --> S["Bundled Render skills"]
    H --> M["Render MCP server"]
    M --> R["Your Render workspace"]
```

[plugin.json](plugin.json) describes the package and its approval setting. [mcp.json](mcp.json) supplies the HTTPS endpoint and a reference to `RENDER_API_KEY`; Duckwork resolves the key from the active profile when connecting. [skills/](skills/) contains the existing Render instructions, references and templates.

Duckwork and local file operations run on your computer or server. Render tool requests go to Render's hosted MCP server and can inspect or change resources in your account. CLI operations use the Render CLI's own authentication on the host. The package adds no background process or telemetry.

This plugin does not move terminal execution into a sandbox. The separate [Render Sandboxes plugin](https://github.com/DuckMind/duckwork) provides that behavior and is not required here.

## Included skills and source

The package includes deployment, debugging, monitoring, MCP setup, CLI use, Blueprints, web and private services, static sites, background workers, cron jobs, Workflows, environment variables, disks, domains, networking, Postgres, Key Value, scaling and Heroku migration.

The dedicated `render-docker` skill is excluded from this initial release because Duckwork's catalog scanner rejects a cleanup command in its Dockerfile example. The upstream skill is unchanged. Other included skills retain their original Docker-related guidance. Remaining scanner warnings in the included examples are disclosed in the catalog submission.

[upstream.json](upstream.json) records the exact Render source commit and every included file's checksum. Updates are reviewed package releases; an installed plugin does not download new skill instructions automatically.

## Troubleshooting

### Plugin installed but skills are missing

Check `duckwork plugins list`, enable `render-platform`, and start a new chat. Ask Duckwork to list its available skills. Plugin skills have qualified names assigned by Duckwork, so let the agent discover them rather than guessing a name.

### Missing or rejected API key

Run `duckwork config env-path` and confirm that you edited the active profile's file. Check that the key is still valid for your Render account, then restart Duckwork and retry the read-only workspace prompt. Keep the key out of screenshots and logs you share.

### Existing Render connection

A `render` entry under `mcp_servers` in your Duckwork configuration overrides this plugin's connection. Keep it if it is intentional. If you want the plugin to own the connection, back up that entry and run `duckwork mcp remove render`, then restart Duckwork. The package's connection and approval setting apply once the override is removed.

### CLI reports a different workspace

MCP and the Render CLI keep separate workspace selections. If a CLI command reports that a service belongs to another workspace, run `render workspace current --output json` in the terminal on the machine running Duckwork. Compare that workspace with the one you selected in chat.

Use `render workspace set YOUR_WORKSPACE_ID` to select the intended workspace, replacing `YOUR_WORKSPACE_ID` with the ID returned by Render's workspace list. Run `render workspace current --output json` again to verify the selection before retrying. If this is a temporary test, restore your previous selection afterward. See the [CLI workspace instructions](https://render.com/docs/cli#common-commands).

### Blueprint validation is unavailable

Install the Render CLI using its [official instructions](https://render.com/docs/cli), authenticate with `render login`, and check `render --version`. A working MCP connection does not install or authenticate the CLI.

## Disable or remove

```bash
duckwork plugins disable render-platform
duckwork plugins remove render-platform
```

Restart Duckwork afterward. Removal takes away the package's skills and connection; it does not delete Render services or the API key you added to your profile. Remove that key separately if nothing else uses it, or revoke it in Render account settings.

## Maintainers

The source record and package checks live in [upstream.json](upstream.json), [scripts/verify_package.py](scripts/verify_package.py) and [validation/results.json](validation/results.json).

Update skill files from a reviewed commit of `render-oss/skills`, preserve their contents and license, update the source record, and validate the resulting package. A catalog update requires a new PR with the full commit identifier so Fordex can review the exact version.

## License

[MIT](LICENSE). Render owns the upstream skill content; this repository provides its Duckwork packaging.
