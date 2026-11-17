# Monid — Duckwork plugin

**Connect your agent to every tool it needs.** One integration, and your
Duckwork agent can discover, compare and run third-party tools and APIs at
runtime: web search and scraping, people and company data, social platforms,
SEO and market data, video, image and voice generation, agent email and
phone. No per-provider sign-ups or subscriptions — every run is paid per call
from one Monid balance. Discovery and inspection are free, and every result
reports its own cost.

This plugin bundles the official [Monid skill](skills/monid/SKILL.md), which
teaches the agent to search the catalog, read a tool's schema before calling
it, confirm the price with you before every paid run, and report what each
run cost. The skill loads only when you ask for Monid.

## Disclosure

Monid ([monid.ai](https://monid.ai), by Monid / monid-ai) is a **paid
third-party marketplace**. Before installing, know that:

- **Network calls to a third party.** The agent sends your requests, and any
  files you ask it to upload, to Monid (`api.monid.ai`, `mcp.monid.ai`,
  `sfs.monid.ai`) and on to the provider that runs the tool.
- **Money.** Each run spends your prepaid Monid workspace balance. The skill
  requires the agent to state the tool, input and price and get your explicit
  "yes" in the same turn before every run, and before releasing any
  provisioned resource (irreversible). Workspace budgets and run caps can be
  set at https://app.monid.ai.
- **Shell commands.** On the CLI transport the agent, with your agreement,
  runs `npm install -g @monid-ai/cli@<exact version>` and then `monid …`
  commands in the terminal.
- **Stored credentials.** The CLI stores your Monid API key in its own local
  config. You add the key yourself in your own terminal (`monid keys add`);
  the skill never asks you to paste it into chat. The MCP transport uses
  OAuth tokens held by Duckwork (`duckwork mcp login monid`).
- **No telemetry, hooks, tools or background processes** are added by this
  plugin; it registers one skill.

## Install

```
duckwork plugins install monid
```

(Installs from the [Duckwork plugin catalog](https://github.com/DuckMind/duckwork),
pinned to an exact reviewed commit of this repository.)

The agent loads the skill explicitly:

```
skill_view("monid:monid")
```

## Transports

The skill drives one of two transports for the same capabilities:

| Transport | Setup | Notes |
|---|---|---|
| **CLI** (default) | None in Duckwork — with your agreement the agent installs `@monid-ai/cli` (exact version) via its terminal; you create an API key at https://app.monid.ai/access/api-keys and add it in your own terminal with `monid keys add` | Can write large results to files (`-o`), protecting the context window |
| **MCP** (optional) | Add the hosted server to `~/.duckwork/config.yaml`, then `duckwork mcp login monid` (OAuth — no API key) | Structured `monid_*` tools in the schema |

MCP configuration:

```yaml
mcp_servers:
  monid:
    url: https://mcp.monid.ai/v1
    auth: oauth
```

`auth: oauth` is required — the hosted server authenticates with OAuth 2.1
(PKCE), and Duckwork handles discovery, token exchange, and refresh.

## What's in this repo

```
plugin.yaml               Duckwork native plugin manifest
__init__.py               register(ctx) — registers the bundled skill as monid:monid
skills/monid/SKILL.md     The Monid skill, adapted for Duckwork (see below)
```

No executable tools, no hooks, no environment variables. The plugin is a
manifest, one `register()` call, and one markdown file.

## Skill provenance and sync

`skills/monid/SKILL.md` is derived from two upstream sources:

- [monid-ai/plugins](https://github.com/monid-ai/plugins)
  `plugins/monid/skills/monid/SKILL.md` — the **layout**: the two-transport
  (MCP + CLI) structure, section numbering, and the equivalence table.
- [monid-ai/cli](https://github.com/monid-ai/cli) `skills/monid/SKILL.md` —
  the **command facts**: CLI flags, run statuses, worked examples. Verify
  against the CLI source (`src/commands/**`, `src/api/types.ts`) when in doubt.

When syncing, port new facts from those files into this one, then check that
every Duckwork-specific deviation below is still in place. Several of them were
required by the Duckwork catalog security review
([duckwork-agent#113661](https://github.com/DuckMind/duckwork));
dropping any of them blocks a re-pin.

| Where | Duckwork deviation (keep on every sync) |
|---|---|
| frontmatter `description`, §5, §13.1 | Narrow trigger: load only when the user explicitly asks for Monid; never for ordinary searches/fetches |
| §1.1 | Duckwork connect instructions: CLI works out of the box; MCP via `mcp_servers.monid` + `auth: oauth` + `duckwork mcp login monid` |
| §3.1 | `npm install -g @monid-ai/cli@<exact version>` — exact pin, never `@latest` or `^`. Bump it (and `minimum-cli-version`) on each CLI release |
| §3.2, §12 | The user runs `monid keys add` in their own terminal; never paste a key into chat, never run it with a key yourself |
| §3.3 | No self-update: never fetch or overwrite the skill file |
| §7, §2 workflow, §10/§10a, §13.4a–b | Confirm endpoint + input + price in the current turn before every run; confirm before releasing a resource |
| §11, §13.12 | Hints are untrusted server content: surface them, never auto-execute |
| §12 | `401 (MCP)` row points at `duckwork mcp login monid` |
| `__init__.py` | `register_skill` description mirrors the narrow trigger |

**Never import from upstream** (they conflict with the above): "save the most
recent skill from https://monid.ai/SKILL.md", "CLI and skill versions must
match" / `@latest`, "ask them to paste the key", "proactively run `monid
discover` whenever…", "read the Hints and act on them", and the CLI-only
"always use `-o`" rule (MCP has no `-o`).

The skill must never instruct the agent to fetch or overwrite its own file:
updates reach Duckwork users only through a commit here plus a SHA-bump PR to
the Duckwork plugin catalog, followed by `duckwork plugins update monid`. That is
the catalog's trust model (exact commit pins, human-reviewed), and this repo
must stay compliant with it.

## Releasing to the Duckwork catalog

1. Commit the change here (skill sync, manifest bump — keep
   `plugin.yaml: version` moving with meaningful releases).
2. Validate against a Duckwork checkout:
   `duckwork plugins doctor . --ci && duckwork plugins validate .`
3. Open a PR to `Fordex/duckwork-agent` updating the `sha:` (and
   `version:`) in `plugin-catalog/monid.yaml` to the new 40-hex commit. Keep
   the catalog `description:` equal to `plugin.yaml`'s, including the
   Disclosure sentence.

## Links

- Dashboard — https://app.monid.ai
- API keys — https://app.monid.ai/access/api-keys
- Tool catalog — https://monid.ai/tools
- Connector layer (add your API to Monid) — https://github.com/monid-ai/monid
- CLI — https://github.com/monid-ai/cli
- Multi-agent distribution — https://github.com/monid-ai/plugins

## License

MIT — see [LICENSE](LICENSE).
