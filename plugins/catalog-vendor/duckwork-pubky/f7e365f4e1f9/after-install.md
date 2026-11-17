# Start a Pubky agent

This plugin is a setup helper. It adds `/pubky` instructions and declares the
pinned `duckwork-pubky==0.2.3` package dependency, including the native Pubky
extension. Current Duckwork installs that dependency into its environment.

The setup helper loads on Duckwork 0.21.3 or later. Running a managed agent
requires Python 3.11–3.13, Duckwork 0.21.3 (schema 30), and a Pubky homeserver
on v0.11 or later. The launcher rejects unverified runtimes before touching
agent state. Use the verified Duckwork checkout documented in the README.
Release wheels support macOS and Linux; building from source requires Rust.

In the activated Duckwork environment, create and run an agent:

```sh
duckwork-pubky agent init default
duckwork-pubky run default
```

If dependency installation was disabled or failed, install the launcher first:

```sh
uv pip install duckwork-pubky==0.2.3
```

To attach an existing agent, use `duckwork-pubky agent attach <pubky-uri>`,
then `duckwork-pubky run <agent-id>`. Initialization asks Pubky Ring to authorize
access to the agent's directory.

Enabling this helper does not sync your current Duckwork profile. Always start
managed agents with `duckwork-pubky run`; the launcher prepares their dedicated
profiles and loads the runtime provider there.

Managed agents upload instructions, memories, skills, conversation database
snapshots, portable configuration, and workspace files to your remote Pubky
homeserver. Your homeserver operator can read this data; it is not end-to-end
encrypted. Configured credentials stay local, but conversations and workspace
files can contain sensitive data you or your tools put there.

Existing Duckwork 0.19 agents upgrade their conversation database on a staged
copy. After saving with this release, all devices running that agent need the
new runtime. Earlier checkpoints remain available in history.

[Full documentation](https://github.com/DuckMind/duckwork)
