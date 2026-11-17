# Meeting Overlay — docs

Native Duckwork desktop plugin (right-docked pane + status-chip), a phone-mirror
PWA, and a Hammerspoon menu-bar controller, for the `meeting-mode` copilot: live
transcription of a call, an answer panel, capture-source + model switching, and
on-card web/THI research.

## Architecture

```
call audio ──► Multi-Output device (Speakers + BlackHole 2ch) ──► your ears
                      └─► BlackHole ──► listen.py (faster-whisper, LOCAL)
   phone mic ──► /ws/audio ──► pwa_server.py (same whisper)           ─┐
                                                                       ├─► rolling.txt (tail)
                                                                       └─► full.txt  (append)
                                             │
   ┌── desktop pane (polls /transcript + /answers + /settings) ◄───────┤
   ├── Hammerspoon 👂 menu — toggles the launchd daemon ────────────────┤
   └── answer.py (LLM loop) ──► answer.txt + answers.json ─────────────┘
                                    └─► save / recap → <vault>/Records/…/*.md
```

- **`desktop/plugin.js`** — the Duckwork pane (native plugin SDK). Polls the
  backend REST namespace `/api/plugins/meeting-overlay/*` every 2s.
- **`dashboard/plugin_api.py`** — FastAPI router (`/transcript`, `/answers`,
  `/status`, `/mode`, `/model`, `/run`, `/assist`, `/request`, `/sessions`).
  `/status` liveness `pgrep`s the listen daemon's absolute path, so the daemon
  must be launched with that path.
- **`scripts/pwa_server.py`** — the phone PWA server: serves `scripts/static/`
  and ingests the phone mic over `/ws/audio`.
- **`scripts/install.sh`** — installs the durable launchd agents + tailnet serve
  (see "Install").
- **`~/.hammerspoon/meeting_listener.lua`** — the menu-bar controller (👂/🤐).
  Toggles the launchd agent, switches capture source + model, fires the engine.
- **`scripts/answer.py`** — the LLM answer loop.
  `--action what|followup|research|recap|save`, `--model host|local|off`
  (`glm`/`qwen` accepted as legacy aliases). Streams `answer.txt` (live panel)
  and appends the `answers.json` deck; `save`/`recap` export to Records.

## Install

Two scripts take a fresh machine to a running, durable system:

1. **Audio** — `scripts/setup.sh`: installs BlackHole and creates the
   Multi-Output device (one-time).
2. **Services** — `scripts/install.sh`: writes + bootstraps the two durable
launchd agents (`com.oz.meeting-pwa` on `--port 9877`, `com.oz.meeting-watch`
for record mode) and exposes the phone PWA on the tailnet
(`tailscale serve --https=9876 9877`). Idempotent — re-run after a
`tailscale serve reset` to heal the mapping.

The PWA daemon itself binds **only to `127.0.0.1` by default**. Tailscale Serve
is therefore the intended phone path: it retains Tailnet identity and proxies
to the local listener. A direct LAN listener is intentionally not enabled by
installation. If it is required, start it explicitly with `--lan` and a
high-entropy `--token-file` with mode `0600`; every HTTP route and audio
WebSocket then require that token before they can read or change meeting state.

The desktop `com.oz.meeting-listener` agent is written at runtime when a desktop
capture source is toggled (its `MEETING_INPUT` is mode-specific), so it needs no
install step.

## Answer engine

| Action | `--action` | What it produces |
|---|---|---|
| 🗣 What should I say? | `what` | short in-the-moment phrasing (last ~90s) |
| 🔁 Follow-up questions | `followup` | 3–4 next questions |
| 🔬 Research | `research` | background/context/framing from model knowledge + transcript |
| 📋 Recap | `recap` | LLM summary (Decisions / Action items / Open questions) and save |
| 📦 Save | `save` | transcript-only save to Records (no summary) |

The three ask modes (`what` / `followup` / `research`) are mutually-exclusive,
persisted listen modes: selecting one arms the record-mode watch loop to drop a
card of that type whenever the transcript grows. **Live web / THI research** is a
separate on-demand path — each answer card carries `web` and `thi` inline actions
that queue a `web-research` / `thi-research` request seeded with that answer's
text, handed to the Duckwork agent to run.

## Model states

| Model | Meaning |
|---|---|
| `host` | the Duckwork system default (hosted, auto-resolved) |
| `local` | local ollama fallback (offline) |
| `off` | no model engaged — transcription keeps flowing, no answers or cards |

Both model chips are toggles: click the selected one to turn it off. `glm` /
`qwen` are accepted as legacy aliases for `host` / `local`.

## Capture sources

Four capture sources, one at a time (no cross-source merge/echo):

| Source | Label | Captures |
|---|---|---|
| `phone` | 📱 Phone | this phone streams its own mic — see "Phone PWA" |
| `mic` | 🎤 Mic | this Mac's built-in microphone |
| `blackhole` | 💻 Audio | system/computer audio (the other side of a call on this Mac) |
| `both` | 🔊 Both | computer audio + mic together, tagged `[audio]` / `[mic]` |

The desktop daemon's underlying `MEETING_INPUT` is `blackhole` (default), `mic`,
`both`/`merge`, or a device name; the pane exposes the same set as these four
sources.

## Status semantics

- green dot / 👂 = daemon alive (listening)
- amber / stale = daemon dead, transcript older than 30s
- gray / idle = daemon dead, transcript fresh or never ran

## Daemon lifecycle

- The durable agents are owned by `scripts/install.sh` (PWA + record-mode watch,
  both `KeepAlive` + `RunAtLoad`); the desktop listener is generated at runtime.
- Launch the desktop listener with the **absolute script path** (the liveness
  `pgrep` needs it):
  `~/.duckwork/duckwork-agent/venv/bin/python ~/.duckwork/skills/meeting-mode/scripts/listen.py`
- Own anything long-running under **launchd**, not a chat session — a daemon
  spawned from a Duckwork terminal dies with that session (the root cause of a
  5-day STALE state).

## Phone PWA (remote mic)

An installable PWA mirrors this panel on a phone over the Tailscale tailnet and
streams the phone's own microphone back into the SAME transcript. The phone is a
room mic — not a call-audio tap (call audio is not exposed by any OS/PWA API).

| Part | Location | Role |
|---|---|---|
| server | `scripts/pwa_server.py` | FastAPI; serves the bundle + `/ws/audio`; runs the same whisper + VAD/energy/min-duration gates as `listen.py` |
| bundle | `scripts/static/` | `index.html` + `manifest.webmanifest` + `sw.js` + icons |
| source | `phone` | the phone streams its own mic; no local daemon is started |

- **Mic path**: `getUserMedia → ScriptProcessor → Int16 PCM 16k mono → /ws/audio`.
- **Install**: `scripts/install.sh` writes + bootstraps the `com.oz.meeting-pwa`
  agent (`--port 9877`, `KeepAlive`) and runs `tailscale serve --bg
  --https=9876 9877`. Then open the `.ts.net` URL in mobile Safari/Chrome →
  Share → Add to Home Screen. `getUserMedia` requires the Tailscale HTTPS secure
  context — a plain `http://<LAN-IP>` origin is blocked.
- **Tailnet-only trust posture**: the PWA has no application-level auth/CSRF
  boundary, and its HTML rendering still lets server-controlled transcript/record
  values reach the DOM. Accepted only while the PWA stays tailnet-only; this ends
  if it is exposed beyond the tailnet or used for more sensitive records.

## Known constraints

- **macOS 15.4 aggregate devices are GUI-only.** `AudioHardwareCreateAggregateDevice`
  is declared but returns `'nope'` at runtime. The Multi-Output device
  (Speakers + BlackHole, BlackHole on Drift Correction) is created in
  Audio MIDI Setup. Name it whatever you like — the daemon taps the system
  default output, not a hard-coded device name.
- **Continuity Camera is REMOVED from this build** — it is Bluetooth/Wi-Fi
  proximity only, cannot run over Tailscale, does not work with Managed Apple
  IDs (work phones), and its mic only surfaces while the camera is actively in
  use.
- Menu-bar label text is single-line (native macOS menu) — keep captions short;
  the status line and tooltip carry the detail.

## Future work (someday-maybe)

- **Phone call-audio capture** — capturing the audio of a call made *on* the phone
  is permanently out of scope: no OS/PWA API exposes cellular call audio. The
  shipped phone surface is the room-mic PWA (above); this item stays scoped to
  call-audio only, not the phone PWA.