<!-- Modified by Fordex for Duckwork distribution on 2026-11-17: fork-owned names and paths rebranded; original authorship and notices retained. -->
# Govee for Duckwork

Control [Govee](https://www.govee.com) lights from [Duckwork Agent](https://github.com/DuckMind/duckwork). Ask "turn the desk lamp warm white at 40%" or "put the living room strip on Aurora", and Duckwork changes that light, then reads its state back to check the change landed.

Unofficial. It isn't affiliated with or endorsed by Govee. It uses Govee's public [developer API](https://developer.govee.com/reference/get-you-devices) (the current `openapi.api.govee.com` platform, not the legacy one).

## What you get

One tool, `govee_lights`, and a bundled skill, `govee:lights`, that tells the agent how to use it safely.

| Action | What it does |
|---|---|
| `list` | Lists your lights with names, device IDs and the capabilities each model supports. |
| `state` | Reads power, brightness, color, white temperature and online status. |
| `scenes` | Lists the light's static and dynamic scenes. |
| `power` | Turns a light on or off. |
| `brightness` | Sets brightness in percent. |
| `color` | Sets an RGB color (`#RRGGBB`). |
| `temperature` | Sets white temperature in Kelvin. |
| `scene` | Applies a scene by name. |

```json
{"action":"list"}
{"action":"brightness","device":"Desk","value":40}
{"action":"color","device":"Desk","value":"#FF8800"}
{"action":"scene","device":"Desk","value":"Aurora"}
```

Device names above are made up. `device` takes an exact device ID or a name that matches one light exactly (case-insensitive). Ambiguous or partial names are refused, so the agent never changes the wrong light.

Only lights are supported. Heaters, plugs and other appliances are deliberately left out. Segment control, music mode, DIY scenes and snapshots aren't in this version.

## Requirements

- A **Govee API key**. Request one in the Govee Home app under Profile > Settings > Apply for API Key; Govee emails it to you. Save it as `GOVEE_API_KEY`. `duckwork plugins install` prompts for it.
- Duckwork 0.21.2 or later. No Python dependencies; it uses only the standard library.

## Install

```bash
duckwork plugins install promptclickrun/duckwork-govee
duckwork plugins enable govee
```

The tool shows up in your next session.

## How it stays safe

- **Checks before sending.** Every command is validated against what that model advertises: the capability must exist, and brightness, color and temperature must sit inside the device's own range. A scene name must match one scene exactly.
- **Checks after sending.** After a change it reads the light's state up to twice, about 2 seconds apart. The result reports `accepted` (Govee took the command) and `verified` (the read-back matches). The skill tells the agent to call a change done only when it's verified.
- **No retries.** A failed or rate-limited command is never resent automatically. Govee allows 30 state and scene requests per minute per device, so this isn't a tool for animations or rapid polling.

## Privacy and behaviour disclosure

- **Network:** it calls `https://openapi.api.govee.com/router/api/v1/` only: `user/devices`, `device/state`, `device/scenes` and `device/control`. Redirects are refused so the key can't be sent anywhere else. Requests time out after 15 seconds and responses are capped at 2 MB.
- **Credentials:** it reads `GOVEE_API_KEY` through Duckwork' secret lookup. It never writes, logs or returns the key, and errors never include Govee's response bodies.
- **Writes:** it changes a light only when the agent calls a control action. It stores nothing on disk.
- No shell commands, no background processes, no telemetry, no self-updating.

## Development

```bash
python -m unittest discover -s tests
duckwork plugins validate . --install-deps
```

Tests use made-up devices and a fake transport. They never touch a real light or the network.

## License

Apache-2.0
