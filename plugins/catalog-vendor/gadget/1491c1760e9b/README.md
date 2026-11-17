<div align="center">

  <a href="https://github.com/DuckMind/duckwork">
    <img src="https://github.com/user-attachments/assets/ac2f5702-c842-4b2e-9340-737481fa0ece" width="96" height="96" alt="Fordex Duckwork mark" />
  </a>

  # Duckwork Gadget

  **Give your Duckwork a place on your desk.**

  This is the Duckwork gateway plugin for [Duckwork Gadget](https://github.com/DuckMind/duckwork) devices.
  Hold a button on a small ESP32 board, ask a question, and hear your own Duckwork answer.

  <sub>POWERED BY <a href="https://github.com/DuckMind/duckwork">DUCKWORK AGENT</a> &nbsp;·&nbsp; COMMUNITY PLUGIN &nbsp;·&nbsp; VERSION 0.3.0</sub>

  <br /><br />

  [Install it](#install) &nbsp;·&nbsp; [What it adds](#what-it-adds) &nbsp;·&nbsp; [What it does on your machine](#what-it-does-on-your-machine) &nbsp;·&nbsp; [Website](https://github.com/DuckMind/duckwork)

</div>

![A dithered marble bust of Duckwork listening to a small handheld gadget on a stone plinth](../docs/images/banner.webp)

## Powered by Duckwork

Duckwork Gadget adds a messaging platform to the [Duckwork Agent](https://github.com/DuckMind/duckwork) gateway. Each gadget is a chat: you speak, Duckwork's speech-to-text turns it into a message, your agent answers with its usual tools, memory and skills, and the reply is shown on the device and spoken through Duckwork's text-to-speech. Unknown devices go through Duckwork's own pairing codes, and command approvals appear on the device as yes/no questions.

This directory is the plugin. The rest of the [repository](https://github.com/DuckMind/duckwork) holds the device firmware, a [browser installer](https://github.com/DuckMind/duckwork), a Raspberry Pi client and a desktop simulator.

## Install

You need Duckwork Agent 0.21.6 or newer, and a speech-to-text provider and voice set up in Duckwork if you want to talk to the gadget.

```bash
duckwork plugins install https://github.com/DuckMind/duckwork --enable
duckwork gateway setup
```

Choose **Duckwork Gadget** in setup and restart the gateway when it asks. Then set up a board from the [installer](https://github.com/DuckMind/duckwork) or try the [desktop simulator](https://github.com/DuckMind/duckwork). The [Connect Duckwork guide](../docs/connect-duckwork.md) covers each step.

## What it adds

| | |
| --- | --- |
| **A gateway platform**<br />`gadget`, a WebSocket endpoint devices connect to. Each device is a direct-message chat, so sessions, `/stop`, `/new` and pairing work as on any platform. | **Three agent tools**<br />`gadget_devices` lists connected gadgets, `gadget_display` shows a short card on a screen, and `gadget_action` runs an action a device declares, such as an LED or a relay. |
| **A CLI**<br />`duckwork gadget info`, `devices`, `pair`, `forget`, `update` and `tile`. | **Over-the-air updates**<br />`duckwork gadget update` sends new firmware to a connected gadget. |
| **A dashboard**<br />Gadgets list the agent's sessions (idle, busy or waiting for approval) and status tiles set with `duckwork gadget tile`. Session state comes from Duckwork's plugin hooks. | |

## What it does on your machine

Read this before you install.

- **Opens a network port.** The gateway listens for gadgets on WebSocket port 8765 at `/gadget`, on all interfaces (`0.0.0.0`) by default. Set `host` in the platform's config to narrow it. Traffic is plain `ws://` unless you set `tls_cert` and `tls_key`. For access outside your network, the [remote access guide](../docs/tailscale-funnel.md) shows a setup that adds TLS.
- **Who can connect.** A new device must be approved with a Duckwork pairing code (`duckwork gadget pair`), unless you list its id in `GADGET_ALLOWED_USERS`. `GADGET_ACCESS_TOKEN` adds a shared token every device must present. `GADGET_ALLOW_ALL_USERS` skips pairing for any device and is meant for development only. Secrets are read through Duckwork's profile-scoped secret helpers.
- **Answers approvals from the device.** When the agent asks to run a dangerous command, a paired gadget shows the command exactly as it will run, and its buttons answer it as **allow once** or **deny**. A paired device can therefore approve commands for its own chat. It never grants "always". A command that does not fit one line of the device's screen as-is can only be denied there; approve it on the host. The question lasts as long as Duckwork's approval timeout (`approvals.timeout`, 300 seconds by default).
- **Lets a paired device switch Duckwork profiles.** Only when `profiles` is set in the default profile's platform config (`[work, home]`, or `all`): on a multiplexed gateway, a device approved in the default profile can then pick one of those profiles. The plugin writes nothing into other profiles: each one approves the device through its own pairing flow, and the device shows the command to run (`duckwork -p <profile> pairing approve gadget <code>`). Revoking the device in the default profile sends it back there and stops it switching.
- **Sets a home channel.** By default (`auto_home: true`) the first approved device becomes the gadget platform's home channel, so scheduled messages for that platform go to it.
- **Runs `ffmpeg` locally** to convert spoken replies that are not plain WAV, when `ffmpeg` is installed.
- **Downloads firmware only when you ask.** `duckwork gadget update <device> --latest` downloads the newest release's `manifest.json` and the board's image from this repository's GitHub releases, checks the image's size and SHA-256 against that manifest, and sends it to the device. Release files carry GitHub build provenance attestations (`gh attestation verify <file> --repo Adolanium/duckwork-gadget-sdk`). Without `--latest`, it sends a file you name.
- **Watches session state for the dashboard.** Plugin hooks tell it when a session starts or ends a turn and when it waits for an approval. Paired gadgets see each session's platform, the last four characters of its id and that state, never what was said. Set `dashboard: false` in the platform's config to turn this off.
- **Writes its own data**, under `<duckwork home>/plugin-data/gadget/`: the device list (`devices.json`), staged firmware updates while they install, the dashboard's tiles (`dashboard.json`), a marker per device that has switched profiles (`owner-bound/`), and, only with `battery_log: true`, a CSV of each device's battery readings. When a device switches to another profile, it also writes that profile's pairing approval, as `duckwork -p <profile> pairing approve` would.
- **Uses Duckwork's services**, which may be cloud services depending on your Duckwork setup: speech-to-text for what you say, text-to-speech for replies, and Duckwork's image cache when the agent shows an image on a gadget. The plugin itself sends nothing else off your machine. There is no telemetry.
- **Runs inside the gateway.** No separate background process. It stops when the gateway stops.

## Limit who can reach the port

On a home network, bind the platform to the interface your gadgets use, and serve `wss://` if anything else shares that network. In `~/.duckwork/config.yaml`:

```yaml
platforms:
  gadget:
    enabled: true
    extra:
      host: 192.168.1.20          # this machine's LAN address; 127.0.0.1 for a local tunnel or simulator only
      tls_cert: /path/cert.pem    # with tls_key, the gateway serves wss://
      tls_key: /path/key.pem
```

Point each gadget at `wss://<host>:8765/gadget`; the device must trust the certificate's issuer. Restart the gateway after the change. The [remote access guide](../docs/tailscale-funnel.md) sets up TLS through Tailscale instead.

## Compatibility

The plugin uses public plugin APIs plus a few gateway internals that a platform adapter needs: the pairing store, the approval resolver, the TTS tool and session context. [`compat.py`](compat.py) lists each one. It checks them before the adapter starts, so a Duckwork that has changed them fails with a message instead of a traceback. CI runs the plugin against a pinned Duckwork commit and against Duckwork `main` on a schedule. [Duckwork integration](../docs/duckwork-integration.md) explains each seam.

## Remove it

```bash
duckwork plugins disable gadget
duckwork plugins remove gadget
```

Delete `<duckwork home>/plugin-data/gadget/` to forget paired devices and staged updates.

<div align="center">
  <br />
  <sub>Independent community project, not affiliated with or endorsed by Fordex. MIT license.</sub>
</div>
