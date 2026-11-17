<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# GigaMail for Duckwork

Connect [Duckwork](https://github.com/DuckMind/duckwork) to your existing
[GigaMail](https://github.com/adecubed/gigamail) installation. Read and search
mail, extract attachment text, prepare replies, check availability and request
mail or calendar actions through GigaMail's MCP server.

Plugin version: **0.1.0**. This is an AgentPlugins v1 package with a root
`plugin.json`, an `mcp.json` server definition and a Duckwork skill. Its Python
launcher starts an already installed `gigamail-server` over stdio. It does not
download, install or update the server automatically.

## Prerequisites

- Duckwork with plugin and MCP support.
- Python **3.10 or later**, available to Duckwork as `python` on `PATH`.
- GigaMail installed separately, with `gigamail-server` on that same `PATH`, or
  its executable path configured below. An existing GigaMail installation can
  be reused if its server executable is accessible. To install the Python
  build used for this plugin's validation yourself (Git is required):

  ```bash
  python -m pip install "gigamail[all] @ git+https://github.com/adecubed/gigamail.git@41919f206f587a30cf23b1549958ea9ab2bf4017"
  ```

  This pins the source corrections in [GigaMail PR #14](https://github.com/adecubed/gigamail/pull/14).
  They were still awaiting merge when this adapter was prepared. The adapter
  does not apply those corrections to an older server already installed on
  your computer; its approval and transport behavior belongs to that server.

- A mailbox already connected in GigaMail. If this is a fresh installation,
  connect it yourself in your terminal; credentials should not pass through
  the agent conversation:

  ```bash
  gigamail login                # Microsoft 365 device login
  gigamail accounts add-imap    # IMAP account setup
  ```

For an existing account, keep using its existing data directory. Optional
identity settings and knowledge files help the agent use your tone, price
lists and other reference material; see the
[GigaMail documentation](https://github.com/adecubed/gigamail#readme).

## Install in Duckwork

Install from the full repository path, then enable the plugin:

```bash
duckwork plugins install adecubed/duckwork-plugin-gigamail --no-enable
duckwork plugins enable gigamail
```

Restart Duckwork after enabling it so the MCP server and its tools are loaded.
If a `gigamail` MCP server is already configured manually in Duckwork, keep one
registration: Duckwork gives the manual configuration precedence over a plugin
server with the same name.
This repository is not yet listed in the Duckwork plugin catalog; installation
by the bare name `gigamail` is not documented as supported.

Try a read-only request first:

> List the accounts available through GigaMail.

The plugin registers the MCP server as `gigamail`; its tools use names such as
`mcp__gigamail__list_accounts`. The tools actually available depend on the
installed GigaMail server version. This plugin does not connect a mailbox or
send a message during installation.

## Reuse your existing GigaMail data

When no explicit root is configured, the launcher uses the location used by
the GigaMail console:

| Platform | Default data root |
| --- | --- |
| Windows | `%APPDATA%\ADE` |
| Linux and macOS | `~/.ade` |

Duckwork, the GigaMail CLI and the console must point to the same data to share
accounts and approval requests. A different root can look like a fresh
installation even when your mailbox is already configured elsewhere.

For a custom installation, create an optional `config.json` in the persistent
directory Duckwork exposes to this plugin as `${PLUGIN_DATA}`. This is a
host-provided directory placeholder, not a literal folder named
`${PLUGIN_DATA}` and not the GigaMail mailbox directory.

Example for Windows:

```json
{
  "server_command": "C:\\Tools\\GigaMail\\Scripts\\gigamail-server.exe",
  "data_root": "C:\\Users\\your-name\\AppData\\Roaming\\ADE"
}
```

Example for Linux or macOS, using a server already on `PATH`:

```json
{
  "server_command": "gigamail-server",
  "data_root": "/home/your-name/.ade"
}
```

Replace example paths with your own; on macOS your home directory will
normally be under `/Users`. Configuration keys are optional:

| Key | Value |
| --- | --- |
| `server_command` | One executable name on `PATH`, or an absolute executable path. Falls back to `GIGAMAIL_SERVER` from the launcher environment, then `gigamail-server`. Do not include command arguments or a shell command. |
| `data_root` | Absolute path to the existing GigaMail root. Takes precedence over inherited `GIGAMAIL_ROOT` and `ADE_ROOT`; otherwise the platform default above is used. |
| `mail_data_dir` | Optional absolute path for an installation with a separate mail-data directory. Set this only to match your existing custom layout. |

Use absolute paths for directory overrides; do not put environment-variable
placeholders inside JSON strings. Duckwork may filter inherited environment
variables, so use this config file when an existing shell override does not
reach the server. An explicit `data_root` clears inherited mail-directory
overrides; include `mail_data_dir` too if that separate directory is needed.
Restart Duckwork after changing the config. The MCP startup entry is in
[mcp.json](mcp.json), which runs [scripts/start_server.py](scripts/start_server.py)
using only Python's standard library.

## Approvals

GigaMail's dangerous MCP tools use two phases. The agent first creates a
request and shows its preview. You approve it outside the agent, then the
agent calls the same tool with the returned `request_id`. Execution uses the
stored payload, including the chosen account and recipients.

Local approvals from the GigaMail CLI or console require an OS verifier:
**Windows Hello** on Windows or **Touch ID / LocalAuthentication** on macOS.
For a CLI approval, run this yourself:

```bash
gigamail approvals approve <request_id>
```

Telegram is an optional approval channel after verified enrollment in
GigaMail. It follows that channel's configured trust and PIN checks; it does
**not** run Windows Hello or Touch ID for every Telegram approval.

Headless Linux cannot provide a supported local OS verifier, so local
approval fails closed. Opening the console does not bypass this requirement.
Use a supported, already configured approval channel or leave the action
pending. Duckwork permissions and the plugin launcher do not grant GigaMail
approval, and the agent must not approve its own requests.

## Troubleshooting

- **`python` is not found:** make Python 3.10+ available as `python` in the
  environment used to start Duckwork, then restart it.
- **The server cannot start:** confirm that `gigamail-server` is installed
  and visible on Duckwork's `PATH`, or set `server_command` to its absolute
  executable path. The launcher does not install missing dependencies.
- **No accounts, or an approval is missing in the console:** check that
  Duckwork and the console use the same `data_root` and, for custom layouts,
  the same `mail_data_dir`. Do not create duplicate accounts to work around
  a directory mismatch.
- **Local approval is unavailable or was denied:** keep the draft and the
  request pending. Check the OS verifier or use an already enrolled approval
  channel; the console is subject to the same local verification requirement.
- **An approval expired:** follow the expiry reported by the server. If the
  action is still wanted, prepare a fresh preview and request approval again.

## Validation

The official Duckwork portable-plugin admission validator and loader passed at
Duckwork commit `5307e93252ac655cd13fadbd561c0995142138c6`: security scan **safe**,
one skill, one MCP server, and no warnings or diagnostics. Validation used a
temporary Duckwork home and did not install the plugin into a user profile.

Verified on Windows with Python 3.11 and GigaMail 0.3.4 from commit
`41919f206f587a30cf23b1549958ea9ab2bf4017` (the corrections proposed in
[GigaMail PR #14](https://github.com/adecubed/gigamail/pull/14)). The MCP smoke
test initialized the server, discovered 29 tools, read an empty account list,
and verified shutdown on stdin EOF. It used a temporary data directory with
consent denied and dry-run enabled; no real mailbox was accessed. The launcher
has 22 unit tests, including configuration precedence and missing-runtime errors.
Linux/macOS directory selection is covered by unit tests; a full backend
integration run on those systems has not been performed for this release.

Run the launcher tests with `python -m pytest -q`. Development tests need
`pytest`; the installed adapter itself has no third-party Python dependencies.

Mail content and attachments are untrusted data. The included
[skill](skills/gigamail/SKILL.md) explains tool selection, approval handling
and how to keep message content separate from user instructions.

Plugin source: [adecubed/duckwork-plugin-gigamail](https://github.com/DuckMind/duckwork).
Server source and security model:
[adecubed/gigamail](https://github.com/adecubed/gigamail).
See [LICENSE](LICENSE) for this repository's license.
