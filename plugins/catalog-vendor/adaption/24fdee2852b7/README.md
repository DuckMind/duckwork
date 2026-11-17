# Adaption Plugin for Duckwork Agent

Connect [Duckwork Agent](https://duckwork-agent.fordex.com) to
[Adaption](https://adaptionlabs.ai) for dataset management, fine-tuning, and
AutoScientist workflows.

The setup has two parts:

- **The Adaption MCP server** gives Duckwork the tools. You add it once and sign
  in with your Adaption account in the browser.
- **This plugin** adds three skills that teach Duckwork how to use those tools.
  It is an [Agent Plugins](https://agent-plugins.org) package, which Duckwork
  installs natively.

## Installation

### Duckwork Desktop

1. **Add the MCP server.** Open this link, which pre-fills the server for you
   to confirm:

   ```
   duckwork://mcp/install?name=adaption&config=eyJ1cmwiOiJodHRwczovL2FwaS5wcm9kLmFkYXB0aW9ubGFicy5haS9hcGkvdjEvbWNwIiwiYXV0aCI6Im9hdXRoIiwib2F1dGgiOnsiY2xpZW50X2lkIjoiYWRhcHRpb24taGVybWVzLXBsdWdpbiJ9fQ
   ```

   Or open **Capabilities → Connectors → Add your own**, choose **Edit
   mcp.json**, and add:

   ```json
   {
     "mcpServers": {
       "adaption": {
         "url": "https://api.prod.adaptionlabs.ai/api/v1/mcp",
         "auth": "oauth",
         "oauth": {
           "client_id": "adaption-duckwork-plugin"
         }
       }
     }
   }
   ```

   The `oauth` block is required: Adaption does not support dynamic client
   registration, which Duckwork Desktop falls back to without it.

2. **Sign in.** Click **Authenticate** on the `adaption` server, then
   **Open in browser**. Choose the organization and click **Authorize**.
3. **Install the skills.** Open **Capabilities → Plugins → Install from Git**,
   enter `adaptionlabs/adaption-duckwork-plugin`, keep the agent plugin checked,
   and confirm. Then enable **adaption** in the plugins list.

   Or open:

   ```
   duckwork://plugin/install?repo=adaptionlabs/adaption-duckwork-plugin&enable=1
   ```

Both links only open a confirmation dialog in Duckwork Desktop; nothing is
installed until you confirm.

### Duckwork CLI

#### 1. Add the Adaption MCP server

```bash
duckwork config set mcp_servers.adaption.url https://api.prod.adaptionlabs.ai/api/v1/mcp
duckwork config set mcp_servers.adaption.auth oauth
duckwork config set mcp_servers.adaption.oauth.client_id adaption-duckwork-plugin
duckwork mcp login adaption
```

Duckwork opens the Adaption sign-in page. Choose the organization and click
**Authorize**. Tokens are cached under `~/.duckwork/mcp-tokens/` and refreshed
automatically.

To sign in again later, for example after revoking access:

```bash
duckwork mcp login adaption
```

On a remote host, follow Duckwork' guide for OAuth over SSH, or use an API key
as described below.

#### 2. Install the skills

```bash
duckwork plugins install adaptionlabs/adaption-duckwork-plugin --no-enable
duckwork plugins enable adaption
```

Start a new session, or run `/reload-mcp` in a running one, to pick up the
tools. Run `skills_list` to see the installed Adaption skills.

### Headless use with an API key

For CI or a gateway with no one to complete a browser sign-in, use an Adaption
API key instead of OAuth. Create one at
[adaptionlabs.ai/app/settings](https://adaptionlabs.ai/app/settings?tab=api_keys),
then:

```bash
duckwork mcp add adaption --url https://api.prod.adaptionlabs.ai/api/v1/mcp --auth header
```

Answer yes when Duckwork asks whether the server requires authentication, then
paste the API key when it asks for a bearer token. Duckwork stores it in your
profile's `.env` as `MCP_ADAPTION_API_KEY`, not in `config.yaml`. To skip the
prompt, set `MCP_ADAPTION_API_KEY` in that `.env` before running the command.

### Why the MCP server is not bundled

Agent Plugins packages can declare MCP servers in `mcp.json`, but that format
has no way to request OAuth, and Duckwork only signs in to servers configured
with `auth: oauth`. A bundled server would connect without credentials and
fail. Adding the server as shown above gives Duckwork the OAuth settings it
needs.

### Local development

Duckwork discovers packages in `~/.duckwork/plugins/<name>/`. Copy a checkout
there to test changes before they are pushed:

```bash
git clone https://github.com/DuckMind/duckwork
rsync -a --delete --exclude .git adaption-duckwork-plugin/ ~/.duckwork/plugins/adaption/
duckwork plugins enable adaption
```

Re-run `rsync` and start a new session after every change.

## Features

### 📊 Dataset Management (11 tools)

- **Import** datasets from HuggingFace, Kaggle, or Google Sheets
- **Adapt** datasets with Adaption's processing pipeline
- **Augment** datasets with synthetic domain/general rows
- **Translate** and **localize** dataset content
- **Combine** multiple datasets
- **Export** processed results

### 🎯 Fine-tuning (5 tools)

- Browse available **base models**
- Get **hyperparameter recommendations**
- Launch **AutoScientist training runs**
- Monitor **training progress** and results

### 🔬 Invent (2 tools)

- Explore available **domains and subdomains**
- **Generate synthetic datasets** from natural language descriptions

## Available Skills

| Skill | Description |
|-------|-------------|
| `adaption-dataset` | Dataset import, processing, and transformation workflows |
| `adaption-training` | AutoScientist training run management |
| `adaption-invent` | Synthetic data generation with Invent |

## Example Usage

> "List my Adaption datasets"

> "Import this HuggingFace dataset and adapt it for fine-tuning"

> "Start fine-tuning on my adapted dataset and pick a suitable base model"

> "Generate 1000 customer service examples using Invent"

> "Check the status of my training job"

## What this plugin does on your machine

- The plugin contains only skills, which are Markdown instructions. It ships
  no code, hooks, shell commands, or background processes.
- The Adaption MCP tools send requests to `api.prod.adaptionlabs.ai` with your
  OAuth token or API key. Datasets you import or generate are processed by
  Adaption.
- Adaptation, augmentation, translation, localization, dataset generation, and
  AutoScientist training runs spend Adaption credits. The skills tell Duckwork
  to request a cost estimate before launching. This is guidance in the skill
  instructions, not a check enforced by Duckwork.

## Requirements

- Duckwork Agent with Agent Plugins support (`duckwork update` to get the latest)
- An Adaption account

## Support

- **Documentation**: [docs.adaptionlabs.ai](https://docs.adaptionlabs.ai)
- **Issues**: [GitHub Issues](https://github.com/DuckMind/duckwork)
- **Email**: support@adaptionlabs.ai

## License

MIT License - see [LICENSE](LICENSE) for details.
