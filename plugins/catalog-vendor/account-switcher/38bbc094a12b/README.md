# Duckwork Account Switcher — Codex & Claude switching for Duckwork Desktop (Windows)

A Desktop plugin for Duckwork on Windows that switches which **Codex** login and which **Claude**
subscription account every local Duckwork profile on this PC uses. One idle-only restart applies
either or both. On Duckwork 0.22 and later that restart is the gateway alone: Duckwork Desktop stays
open and reconnects. The status-bar dialog reports success only from a post-restart verification
receipt: an accepted request is never treated as a completed switch.

- Plugin ID: `account-switcher`
- Version: **1.2.3**
- Platform: **Windows only**
- Scope: local Duckwork profiles on this machine. Remote machines, the standalone Codex app, and
  Claude Code's own sessions are not touched.

## Status

Version **1.2.3** supports Duckwork 0.22, where Duckwork Desktop runs no backend of its own and the
gateway serves every chat: a switch now restarts only the gateway there. 1.2.2 answered the Duckwork catalog review: the plugin now touches Duckwork only through
public surfaces, and three documentation claims were made true (see
[docs/release-notes.md](docs/release-notes.md)). 1.2.1 fixed the button when the chat you have
open runs on another machine. 1.2.0 was the first public release.

| Area | State |
|---|---|
| Codex switching | **Proven live** on Windows 11 with two real accounts: real switches, which account pays measured on the wire, refusals, failures in the middle of a switch, a second profile, and a Duckwork update. |
| Claude switching | **Proven live** with two real accounts: real switches in both directions and together with Codex, and which account a real request uses. |
| First-time install | **Proven** on a blank Windows 11: Duckwork's official installer, then this plugin's `setup.cmd`, then a switch through the dialog. |
| License | MIT. See [LICENSE](LICENSE). |
| Official plugin catalog | Listed as `account-switcher`. |

Receipts are in [docs/receipts/](docs/receipts/). The full ledger of what has and has not been
run is [docs/acceptance.md](docs/acceptance.md).

## What it does

- **Codex.** Duckwork keeps its Codex logins in its own login store. A switch changes which login
  Duckwork tries first, in the first profile's store and in every profile that holds logins of its
  own; the other login stays as Duckwork's fallback. A profile with no Codex logins of its own uses
  the first profile's, so it follows the same switch. Identity comes from the account inside the
  login, never from a display label.
- **Claude.** The separately installed Claude subscription provider plugin points the `claude`
  command at a login folder through the `CLAUDE_SUBSCRIPTION_DIRECTSDK_CONFIG_DIR` variable. A
  switch writes that variable in every profile's `.env`, naming the login folder of the account
  you picked. Identity is verified with Anthropic, never inferred from the folder.
- **Both at once.** The dialog has one selector per provider; change either or both in one switch.
- **A warning when the wrong account pays.** If the selected Codex login is dead or exhausted,
  Duckwork silently falls through to the next one. The button then shows a warning and names the
  account that is really paying.

The switcher never creates, copies or stores credentials. It only changes **which existing,
verified login is selected**.

## Requirements

- Windows 11 with Duckwork and Duckwork Desktop, installed by Duckwork's official installer or install
  script. No separate Python is needed; the plugin uses the one Duckwork brings.
- For Codex switching: two or more Codex accounts signed in to Duckwork
  (`duckwork auth add openai-codex`, once per account).
- For Claude switching:
  - Claude Code (the `claude` command), from Anthropic's installer.
  - The Claude subscription provider plugin: `duckwork plugins install claude-subscription-directsdk`.

  This plugin does not bundle, fork or maintain that provider, and makes no claim about any
  provider's terms of service.

## Install

Unpack the release ZIP, open a terminal in that folder, and run:

```
setup.cmd
duckwork plugins enable account-switcher
```

Run them one at a time: `setup.cmd` asks questions and waits for your answers.

Then restart Duckwork Desktop, open **Capabilities → Plugins**, choose **Installed**, and turn on
the switch on the **Account switch** card. On newer Duckwork builds, click the card to open it and
turn on **Desktop** as well. Duckwork keeps a new plugin's button hidden until you do.

What each step does:

- `setup.cmd` copies the plugin's code into Duckwork, finds your Duckwork folders and the Codex
  accounts already signed in, asks for a short name for each, shows what it would write, and
  writes the settings file after you answer yes. It enables nothing, changes no account and restarts nothing. Run it again after
  signing in another account.
- `duckwork plugins enable` is Duckwork's own command.

### Three ways to set it up

Setup records which accounts you have and what to call them. It signs nobody in and switches
nothing. All three ways write the same settings file.

- **In the dialog.** The first time you click the account button (it reads **Account switch:
  set up**), the dialog lists the Codex and Claude accounts already signed in on this PC, asks
  for a short name for each, and saves. This is all a catalog install needs.
- **In a terminal.** `setup.cmd`, as above.
- **By your agent.** In the setup dialog, **Copy instructions for my agent** puts a short brief
  on the clipboard. It has the agent run `setup.cmd show` (changes nothing), ask you for the
  names, and run `setup.cmd auto "me@example.com=Personal" "claude:me@example.com=Family"`. Signing
  in and switching stay with you.

### Claude accounts

A Claude account that is already signed in under `<Duckwork home>\claude-auth` is found by setup.
To add and sign in another, once per account, with a short name of your choosing and the
account's email:

```
setup.cmd claude personal me@example.com
```

It adds the account to the settings and starts Claude's own sign-in. No browser opens by itself:
the sign-in link is put on your clipboard. Open it in a **private** browser window, sign in as
that account, approve, and paste the code the page shows back into the terminal. The plugin then
asks Anthropic who signed in; a login made as the wrong account is refused and its login file is
deleted from that folder, so the folder never holds a login for another account. To sign an
account in again later: `setup.cmd claude personal`.

### More than one profile

The switch covers every profile on the PC, so the plugin must be installed and enabled in each
one. For a profile named `work`:

```
setup.cmd profile work
duckwork -p work plugins enable account-switcher
```

Until that is done the dialog blocks the switch and names the profile and the command. Enable the
plugin only in profiles you have reviewed.

### Without setup.cmd

`setup.cmd` runs two scripts with Duckwork's own Python; they can be run directly with any Python 3:
`python install.py install --home <Duckwork home>` and `python setup_settings.py --home <Duckwork home>`.
The Duckwork home is normally `%LOCALAPPDATA%\duckwork`.

## Settings

The settings file lives outside the plugin's code, so updating or removing the plugin never
touches it:

```
<Duckwork home>\plugin-data\account-switcher\settings.json
```

`setup.cmd` writes it. [settings.example.json](settings.example.json) shows the shape.

| Key | Meaning |
|---|---|
| `duckwork_root` | The Duckwork home folder. |
| `duckwork_source` | The `duckwork-agent` folder inside it. |
| `desktop_exe` | The Duckwork Desktop program. |
| `gateway_service` | `null` when Duckwork starts its own gateway (every ordinary install). A Windows service name only if you run the gateway as a service yourself; `setup.cmd` finds it while that gateway is running, and `setup.cmd service <name>` sets it by hand. |
| `gateway_health_url` | Optional, and only with a Windows service: a loopback `/health` address. |
| `codex` | Account key → `{label, email}`. |
| `claude` | Account key → `{label, email, directory}`; `directory` is that account's login folder. May be empty. |

Labels are decoration. The email is the identity the plugin expects, and it is checked against the
login itself. Missing or invalid settings produce a plain message and no change.

## Using it

Click the account button in the Duckwork status bar (for example **Codex: Personal · Claude:
Work**). The dialog checks that Duckwork is idle and shows the selectors. Confirming performs one
transaction:

1. **Check** — nothing changed yet; the target login is confirmed with its provider.
2. **Freeze** — new work is held back at the gateway and at Duckwork Desktop.
3. **Stop** — Duckwork Desktop closes and the gateway stops. On Duckwork 0.22 and later only the
   gateway stops; Duckwork Desktop stays open.
4. **Apply** — the selection is written to every store and read back.
5. **Start** — the gateway and Duckwork Desktop start again (on 0.22 and later, the gateway alone).
6. **Verify** — new processes, every reopened backend, every stored order.

A switch takes about 40 to 70 seconds. Only a receipt that says `"state": "complete"`
(`<Duckwork home>\logs\account-switcher-last.json`) means the switch took effect.

If something fails while Duckwork is closed, the previous selection is restored and Duckwork is
reopened. If the switch itself is cut off (a crash, a power cut), reopen Duckwork Desktop: the
plugin clears what the interrupted switch left behind and the dialog says where it stopped.

## Update, roll back, uninstall

| Action | Command | Effect |
|---|---|---|
| Update | `setup.cmd` again, from the new release | Replaces the plugin's code only. Refuses over files it did not install or that were changed. Restart Duckwork Desktop afterwards. |
| Roll back | `python install.py rollback --home <path>` | Restores the previous plugin code. |
| Uninstall | `python install.py uninstall --home <path>` | Removes only the code it installed. Settings, logins and login folders stay. |

None of these change which account is selected. Once the plugin is listed in the official
catalog, prefer `duckwork plugins install account-switcher`, which installs from an exact
reviewed commit; `setup.cmd` run from the installed folder then only writes the settings. The
plugin contains no self-updater.

## Security

- The backend answers on the loopback interface only, behind Duckwork's own web authentication.
  The interface holds no credentials.
- No token, refresh token or account id enters the dialog, a log or a receipt.
- The plugin's own network calls are the provider checks: OpenAI's usage answer for the target
  Codex login, Anthropic's account answer for the target Claude login.
- If the target Claude login has expired, the plugin first runs the `claude` CLI once against a
  closed local port so the CLI renews its own token. That renewal goes to Anthropic and replaces
  the token, including the refresh token, in that account's Duckwork `claude-auth` folder.
- Restart scope is exactly Duckwork Desktop and the Duckwork gateway (on Duckwork 0.22 and later, the
  gateway alone). Nothing else is stopped,
  started, installed or configured.
- The plugin changes nothing inside Duckwork: no function of Duckwork is replaced, wrapped or
  rebound, and no private name is read. Whether Duckwork is idle is Duckwork's own answer.
- No telemetry, no credential synchronization, no automatic account rotation.

## Documentation

| File | What it covers |
|---|---|
| [USER-GUIDE.md](USER-GUIDE.md) | Plain-language walkthrough and troubleshooting |
| [TECHNICAL-GUIDE.md](TECHNICAL-GUIDE.md) | How it is built, and the traps already found |
| [docs/compatibility.md](docs/compatibility.md) | Verified Duckwork builds and the Duckwork interfaces used |
| [docs/acceptance.md](docs/acceptance.md) | What has been run, with receipts, and what has not |
| [docs/release-notes.md](docs/release-notes.md) | Changes per version |

## Tests

```
python -m pytest tests -q
npm ci
npm test
```

The backend suites use fixture logins and temporary folders; the interface suite runs against a
stand-in for Duckwork's plugin kit, not the real app. Current counts are in
[docs/acceptance.md](docs/acceptance.md).

## License

MIT. See [LICENSE](LICENSE).
