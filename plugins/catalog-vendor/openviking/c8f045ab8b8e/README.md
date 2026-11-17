# OpenViking for Duckwork

OpenViking gives Duckwork Agent long-term memory and tools to search your knowledge.
It captures conversations, extracts useful facts and recalls them in later chats.

## Get started

Run these commands in the Duckwork profile you want to use:

```bash
duckwork plugins install openviking --enable
duckwork memory setup openviking
duckwork
```

Accept the dependency prompt during installation. In setup, choose how you
use Duckwork, then choose a connection.

### Personal or Shared

Duckwork uses conversation history to follow the current chat. OpenViking saves
extracted facts as long-term memory for use in later chats. These are separate.

Common memory is not linked to a sender. Sender memory is linked to the person
who sent a message through Telegram, Discord or another messaging platform.
Both modes recall common memory under the same OpenViking user.

| Usage | What it does |
|-------|--------------|
| **Personal Agent** | Recalls common memory and the current sender's memory. Keeps your existing conversation history settings. |
| **Shared Agent** | Shares conversation history within each group or thread. Recalls common memory and all senders' memories under the same OpenViking user. |

Choose Personal for an assistant that recalls memory for the current person.
Choose Shared for a team that wants to share recalled memories. Shared Agent
asks for confirmation before changing conversation history settings. Different
groups keep separate histories, even in Shared mode. Restart the gateway if
setup changes its session settings.

Personal does not change existing history settings. If a group already shares
history, choosing Personal leaves that history shared. Neither mode changes
data access rights. Use separate OpenViking users and keys when people need
separate access.

### Choose a connection

| Connection | What you need |
|------------|---------------|
| **Quick Local** | A language model already configured in Duckwork. Setup installs a local server and embedding model. |
| **OpenViking Service (VolcEngine Cloud)** | A service API key for VolcEngine's [managed OpenViking cloud service](https://www.volcengine.com/product/openviking-service?utm_source=github&utm_medium=referral&utm_campaign=readme). |
| **Custom** | Your server URL and credentials. Setup can also reuse a saved `ovcli.conf`. |

For the cloud service, activate it and create an API key in the
[OpenViking console](https://console.volcengine.com/vikingdb/openviking/region:openviking+cn-beijing?utm_source=github&utm_medium=referral&utm_campaign=readme).
Open **User Management**, then **API Key**. You do not need to install a server
or configure local models.

After setup, chat as usual. Memories become available after the captured
conversation is committed and OpenViking finishes extraction. The plugin
requests a commit at 20,000 pending tokens by default, at session end and when
switching sessions.

The plugin sends conversation turns, tool results and edits to `MEMORY.md`
and `USER.md` to your OpenViking server. Memory extraction can use a remote model.

## Quick Local

Quick Local reuses your Duckwork language model for memory extraction. A local
embedding model prepares text for memory search. The language model must use
a supported static API key or Duckwork's local llama.cpp server. OAuth logins
are not supported. See [model support](CONFIGURATION.md#quick-local-model-support).

Setup checks the language model, downloads the embedding model and starts the
server before it finishes. It saves a copy of the model credentials in this
profile's private server configuration. Downloads need access to PyPI, GitHub
and Hugging Face.
The model download is about 46 MB. Other packages add more than 1 GB per profile.

Prebuilt packages are available for Apple Silicon with macOS 14 or newer,
Linux x86-64 or ARM64 with glibc 2.31 or newer, and Windows x86-64. On other
platforms, setup asks before building from source. This needs development
tools and can take several minutes. You can use Custom instead.

Each Duckwork profile has its own server, data and port. If the saved port is
occupied, Quick Local selects a free port. Run setup again after changing the
Duckwork model or API key. Your data and downloaded model are kept.

Quick Local installs the latest compatible OpenViking 0.5 release. Version
0.5.0 includes the [fix](https://github.com/volcengine/OpenViking/pull/5548)
for overlapping local embedding calls that could crash 0.4.22 and 0.4.23.
Run Quick Local setup again to upgrade an existing private runtime. This
does not upgrade a separately managed Custom or OpenViking Service server.

The server keeps running after Duckwork exits. These commands are optional:

```bash
duckwork openviking local status
duckwork openviking local stop
duckwork openviking local start
duckwork openviking local restart
```

Stopping keeps the data. A running Duckwork session or gateway can start the
server again when memory is used. Close those sessions or disable OpenViking
memory if you want it to stay stopped. Turns completed while the server is
starting or recovering are not captured.

Switching to OpenViking Service or Custom stops this profile's Quick Local
server and keeps its data. `local start` and `local restart` work only while
Quick Local is selected.

## Custom server

Run OpenViking in its own Python environment or container. For a new local
server, run these commands there:

```bash
openviking-server init
openviking-server doctor
openviking-server
```

Then run `duckwork memory setup openviking` and choose Custom. For setup to
start a stopped local server, `openviking-server` must be on `PATH`.

## Check status

```bash
duckwork memory status
```

`available` means the provider is configured. It does not confirm server
health or successful memory extraction. For Quick Local, use
`duckwork openviking local status` to check the server.

## Update

```bash
duckwork plugins update openviking
```

Restart Duckwork or the gateway afterward. Your connection settings and server
data are kept. Updates use the version reviewed in the Duckwork catalog.
For direct source installs, use the [source update command](CONFIGURATION.md#pinned-source-installation).

To update a Quick Local server, run `duckwork memory setup openviking` again and
choose Quick Local. Setup selects the latest compatible OpenViking 0.5 release
and restarts the server if needed. Normal chat and recovery use the installed
server without checking for updates.

If validation fails after installing a runtime update, chat keeps using the healthy
existing server while it keeps running. If that process stops, recovery can start
the installed runtime before setup validation has passed. The update still needs
validation, even if the server is ready. `duckwork openviking local status` reports
this pending state. Correct the reported problem and run
`duckwork memory setup openviking` again, then choose Quick Local. Setup validates
the update before requesting a restart.

## Existing users

If a Duckwork update removes its built-in OpenViking provider, it attempts to
install the catalog plugin for profiles already using OpenViking. Your settings
and server data are kept. If installation fails, run the install command above
in that profile.

Older Duckwork releases load their built-in copy first. On those releases,
keep using `duckwork memory setup openviking`. Quick Local and the external
plugin's changes become available when that copy is removed.

## Tools

Duckwork calls these tools when needed. You do not need to run them yourself.

| Tool | What it does |
|------|--------------|
| `viking_search` | Search memories and knowledge. |
| `viking_read` | Read content at a `viking://` address. |
| `viking_browse` | List files and directories. |
| `viking_remember` | Submit a fact for memory extraction. |
| `viking_forget` | Delete one exact memory file. |
| `viking_add_resource` | Add a URL or document to the knowledge base. |

## Remove

Close Duckwork sessions and stop the gateway for this profile. For Quick Local,
run `duckwork openviking local stop`. Select another memory provider or disable
OpenViking memory, then run:

```bash
duckwork plugins remove openviking
```

Removal does not stop a running server or delete the runtime, model and data
in `$DUCKWORK_HOME/openviking/`.

## Requirements

- Python 3.11 or newer in the Duckwork environment.
- OpenViking Service, Quick Local or a reachable OpenViking server.
- OpenViking 0.2.14 or newer for Custom connections.

Tested with Duckwork v2026.9.24 and the Duckwork main commit used in
[CI](../../.github/workflows/duckwork-plugin-tests.yml).

## Config

The wizard saves the connection settings. For optional recall settings,
model support, backups and memory recovery, see [Advanced configuration](CONFIGURATION.md).
For development and migration notes, see [DEVELOPMENT.md](DEVELOPMENT.md).
This directory uses the [MIT license](LICENSE).
