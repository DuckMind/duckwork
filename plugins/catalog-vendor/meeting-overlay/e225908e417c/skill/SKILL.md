---
name: meeting-mode
description: "Use when live-listening to a call via the HUD. Rolling transcript → assist/recap/notes answers."
version: 1.0.0
author: taxbax
license: MIT
platforms: [macos]
metadata:
  duckwork:
    tags: [meeting, hud, transcription, copilot, live, audio]
---

# meeting-mode

Turn the Duckwork HUD into a live meeting copilot: it listens to the other
side of a call (via a BlackHole audio loopback), keeps a rolling transcript,
and answers on demand — "what should I say", "recap", "notes", "follow up".

## Start here — system docs + the 30-second health check

Full system documentation (concept, stack, architecture, connections, file inventory,
install→first-answer, maintenance, roadmap, **operations**) lives in the vault at
`Documentation/recorder/RC-00 … RC-09`. **RC-09 is the operational reference** — runtimes,
ports, state dir, settings schema, env vars, routes, and a diagnosis playbook.

```bash
launchctl list | grep meeting            # listener / pwa / watch all present?
pgrep -f "answer.py --action watch" | wc -l   # MUST be 1 (the durable record-mode loop)
tail -3 ~/.duckwork/meeting-transcript/watch.out # "idle (auto_assist off)" or "chunk …"
curl -sS http://127.0.0.1:9877/ -o /dev/null -w "%{http_code}\n"   # PWA up?
```

If cards aren't appearing on a call, that trio (watch agent alive → flag on → transcript
growing) is the diagnosis, in that order.

## How it works

```
meeting app ──► Multi-Output Device (Speakers + BlackHole 2ch) ──► your ears
                                              └─► listen.py (faster-whisper) ──► rolling.txt
                                                                                      │
                                                              HUD + this skill ──────┘
```

- `scripts/listen.py` captures system audio (BlackHole) by default and streams
  faster-whisper transcriptions into `~/.duckwork/meeting-transcript/rolling.txt`.
- This skill reads that file live and generates answers **on demand** — never
  continuously — so latency stays low and context stays clean.

### Input source (BlackHole vs mic)

`MEETING_INPUT` selects what the daemon captures. **Both are first-class
modes** — pick by where the call lives, not by preference:

| Value | Captures | Use when |
|---|---|---|
| `mic` | the built-in microphone, acoustically | **the call is on a DIFFERENT computer/phone** — this Mac sits near you and hears the conversation through its mic |
| `blackhole` (default) | system audio (the other side of a call on this Mac) | Zoom/Meet/Teams on this machine |
| any device name | that specific device | e.g. `MEETING_INPUT="my-mic"` for a specific mic |

```bash
# Call on another computer -> mic hears it
MEETING_INPUT=mic ~/.duckwork/duckwork-agent/venv/bin/python ~/.duckwork/skills/meeting-mode/scripts/listen.py

# Call on this Mac -> system audio via BlackHole
~/.duckwork/duckwork-agent/venv/bin/python ~/.duckwork/skills/meeting-mode/scripts/listen.py
```

Note: the daemon taps **one** source at a time. The mic does not conflict
with the HUD's native voice (voice is opt-in, and macOS shares the mic across
clients) — but the meeting daemon and an active HUD voice session shouldn't
run on the mic simultaneously; use one or the other.

## Before first use (one-time setup)

```bash
brew install blackhole-2ch switchaudio-osx
```

Then create the Multi-Output Device (so you still hear the call while it's
tapped). See `scripts/setup.sh` / the aggregate-device helper. Set the system
default output to that Multi-Output Device.

Start the daemon (Duckwork venv already has all deps):

```bash
~/.duckwork/duckwork-agent/venv/bin/python ~/.duckwork/skills/meeting-mode/scripts/listen.py
```

Run as a background process so it survives the session:
`terminal(background=true)` or a `no_agent` cron job.

## Commands (what to type in the HUD)

| Say | Action |
|---|---|
| `assist` / `what should I say` | Read last ~90s of `rolling.txt`; suggest phrasing / answer the last question heard. Keep it short — HUD is a narrow bar. |
| `recap` | Read `full.txt`; structured summary: decisions, action items, open questions. |
| `notes` | Read `full.txt`; clean meeting notes. |
| `follow up on X` | Search `full.txt` for X; draft a follow-up. |

### The answer panel

Every command above writes its answer to `~/.duckwork/meeting-transcript/answer.txt`
**after** composing it. The live overlay (below) polls that file and shows the
answer in its hero panel. Compose the answer first, then write it verbatim to
`answer.txt` so the overlay and the HUD reply agree.

## The live overlay (native desktop plugin)

The overlay is a **native Duckwork desktop plugin** — a real pane in the app,
built on the desktop-plugin SDK — not a web page. It lives at
`~/.duckwork/plugins/meeting-overlay/`:

```
~/.duckwork/plugins/meeting-overlay/
├── plugin.yaml              # agent half (plugins.enabled gate)
├── dashboard/
│   ├── manifest.json        # { "name": "meeting-overlay", "api": "plugin_api.py" }
│   └── plugin_api.py        # FastAPI router: /transcript /answer /status /request
└── desktop/
    └── plugin.js            # right-docked pane + status-bar chip
```

The pane shows the live transcript, the latest `answer.txt` in an "Assist"
hero panel, and a status dot (green = daemon listening, amber = stale, gray =
idle), polled every 2s through `ctx.rest` + the app's `useQuery`. Enable it:

1. **Desktop half** — Settings → Plugins → toggle **Meeting Overlay** on
   (then ⌘K → *Reload desktop plugins* if the pane hasn't appeared).
2. **Python half** — already in `config.yaml` `plugins.enabled`; restart the
   app / gateway once so the backend imports `plugin_api.py`.

The pane docks right; drag it wherever, or dock it into the main workspace.
Start the daemon to go live — the dot turns green and the transcript streams.

## Hard rules

1. **Always read the transcript file live** (`read_file` on
   `~/.duckwork/meeting-transcript/rolling.txt` / `full.txt`) — never answer
   from model memory.
2. **Run `scripts/status.py` first.** A stale transcript (>30s) means the
   daemon died or the routing broke — say so, don't answer from stale text.
3. **One answer per prompt.** No continuous generation.
4. **Keep answers short** — the HUD bar is narrow; the user reads while talking.

## Pitfalls learned (verified live)

- **Hosted model routes through Fordex OAuth, not OpenRouter.** The default model
  `z-ai/glm-5.3-flash` is served by the Fordex Portal: a short-lived `agent_key` JWT in
  `~/.duckwork/auth.json`, refreshed via `duckwork_cli.auth_fordex.resolve_fordex_runtime_credentials`,
  endpoint `https://inference-api.fordex.com/v1/chat/completions`. The `.env`
  `OPENROUTER_API_KEY` is STALE and returns 401 from background processes — never use it for
  hosted-model calls; it is fallback-only.
- **`hs.task.new` argument order is `(callback, streamCallback, command, args)`.** Passing the
  executable path first (where the callback function goes) silently spawns nothing — every menu
  action "runs" but no process starts, and `isRunning()` stays false so toggle state never flips.
- **Qwen3's thinking chain leaks into content.** Ollama 0.9.6 ignores `think: false` for qwen3;
  the reasoning text is embedded in `message.content` separated by a ` response` token. Strip
  everything up to the LAST ` response` marker (whitespace-agnostic) and keep the tail.
- **Qwen3 4B is the local floor, not 1.7B.** 1.7B is noticeably worse for meeting synthesis;
  `qwen3:4b` (~2.5GB) is the offline fallback. The model auto-loads on first inference and
  auto-unloads after ~5min idle (`OLLAMA_KEEP_ALIVE`) — no preloader needed.
- **macOS 15.4 aggregate devices are GUI-only.** `AudioHardwareCreateAggregateDevice`
  is *declared* in `AudioHardware.h` but returns OSStatus `1852797029` (fourCC `'nope'`)
  at runtime — the skill's earlier "absent from SDK" wording is wrong; the function exists
  but is deliberately dead. Create the Multi-Output Device in Audio MIDI Setup (drivable
  via computer_use with `mode=som`; the window is `Audio Devices` with an
  `AXMenuButton "Create Aggregate Device"` / bottom-left `+`).
- **The daemon's liveness check is brittle.** The overlay's `_daemon_alive()` runs
  `pgrep -f "meeting-mode/scripts/listen.py"`. Launch it with the **full absolute path**
  in argv — `python "$HOME/.duckwork/skills/meeting-mode/scripts/listen.py"` — never
  `cd dir && exec python listen.py`, or the pgrep pattern never matches and the status dot
  stays STALE even while the daemon is transcribing fine.
- **Own it under launchd, not a chat session.** A daemon started from a Duckwork terminal is
  a child of that session and dies with it (the 5-day STALE state was this exact failure).
  The launchd agent `com.oz.meeting-listener` (`~/Library/LaunchAgents/`) + a Hammerspoon
  menu-bar controller (`~/.hammerspoon/meeting_listener.lua`) is the durable setup: enable =
  `launchctl bootstrap`, disable = `bootout`, mode (mic vs blackhole) = the `MEETING_INPUT`
  env var in the plist.
- **This user's multi-output device is a custom aggregate** (Speakers + BlackHole 2ch,
  BlackHole on Drift Correction) and is already the default output — don't recreate it. The
  skill's "4 clicks you must do yourself" may already be done; check `SwitchAudioSource -c -t output`
  and `system_profiler SPAudioDataType` first.
- **Verify the tap with a real phrase, not a tone.** A 440 Hz loopback probe fails (PortAudio
  `-50`, and BlackHole won't `sd.play` a tone). The reliable check: `say "test phrase"` (which
  routes through the default output → BlackHole) then read `rolling.txt` back — a fresh
  timestamped line means the whole chain works.
- **False positives (keyboard clicks, vape pulls, taps) need three gates, not one.**
  `vad_filter=True` alone still transcribes impulsive non-speech. Add (1) an RMS energy
  floor BEFORE transcription (`MEETING_ENERGY_FLOOR`, default `0.02` — clicks are peaky but
  low-RMS vs sustained speech), (2) a min-duration gate AFTER transcription
  (`MEETING_MIN_POST_MS`, default `600` — an isolated click produces a vanishingly short
  segment; drop it unless it has a long word), and (3) `word_timestamps=True` so segment
  durations are available to judge. Tune the floor/duration env vars, don't hand-edit the
  thresholds.

## Mean Judge meeting records

File a meeting recap or action list as a cabinet sheet only when it carries reusable operational knowledge. Resolve the topic cabinet first. Use Register lineage only for a qualified decision.

## Records export (vault tree + searchable filenames)

Exports go to `<vault>/Records/YYYY/MM/<Mon–Sun week>/<subject>.md`. The filename is
a **model-generated searchable subject** ("shoulder-surgery-scheduling-insurance-follow-up.md"),
not a date slug. A week spanning two months lives in the month owning most of its days,
with a `week-YYYY-MM-DD.md` pointer note in the other month. `Save to vault` = transcript
only (no LLM summary); `Recap` = LLM summary + save. Both are exports; neither auto-runs.

## Cross-surface contract (one action name, three surfaces)

The answer engine's action names are a contract shared by `answer.py`, the desktop
`plugin.js`, and the Hammerspoon menu — a change in one must land in all three or the
stale surface calls a now-invalid flag. When you removed `--watch` and renamed
`prepare` → `save`, the menu bar still passed `--watch 20` and `--action prepare`,
which argparse rejects (a silent no-op the user sees as a dead menu). After any action-set
change, `grep` the removed name across `plugin.js` AND `.hammerspoon/meeting_listener.lua`,
not just the file you edited.

## Phone PWA (remote mic)

A standalone PWA mirrors the panel on a phone over Tailscale and streams the phone
mic back into the SAME transcript. Served by `scripts/pwa_server.py` (FastAPI,
launchd agent `com.oz.meeting-pwa`, local port 9877) with the static bundle in
`scripts/static/` (index.html + manifest.webmanifest + sw.js + icon-192/512.png).

### Accepted tailnet trust deficiency

The current PWA has no application-level authentication, authorization, or CSRF
boundary, and its HTML-string rendering still permits server-controlled transcript
or record values to reach unsafe DOM sinks. The principal accepts this deficiency
only while the PWA remains tailnet-only. Tailscale limits reachability but does not
provide per-application authorization among tailnet peers; every reachable peer is
therefore trusted with transcript reads, microphone ingestion, hosted-model actions,
and record mutations. This acceptance ends if the PWA is exposed beyond the tailnet,
shared with a less-trusted tailnet member, or used for materially more sensitive
records. At that boundary, application authentication plus safe DOM construction is
a prerequisite, not follow-up polish.

- **Phone mic = getUserMedia → ScriptProcessor → Int16 PCM 16k mono → WebSocket `/ws/audio`.**
  PCM was chosen over opus so no server-side decode is needed. The browser downsamples
  via AudioContext({sampleRate:16000}); send `pcm.buffer` (Int16Array) as binary frames.
- **The server runs the SAME whisper + VAD/energy/min-duration gates as listen.py**
  (`transcribe_window` in pwa_server.py) and appends `[mic]` lines to rolling.txt — so a
  phone mic and the desktop BlackHole daemon merge into one transcript.
- **Flush bug to avoid:** the WS loop must transcribe on BOTH accumulated duration AND
  disconnect (`finally:` block) — phone blobs arrive fast enough that a silence-gap-only
  heuristic never fires and the last utterance is lost at hangup.
- **`tailscale serve --bg <port>` re-points the BARE hostname (443), not a new origin.**
  To add the PWA without clobbering the dashboard bookmark, use
  `tailscale serve --bg --https=9876 9877` (a dedicated port); restore 443 with
  `tailscale serve --bg 9119`. Always `tailscale serve status` after.
- **PWA + getUserMedia require https + a secure context** — a Tailscale HTTPS cert
  satisfies
  this; a plain `http://<LAN-IP>` origin will be blocked by the browser. Install:
  open the Tailscale URL in mobile Safari/Chrome → Share → Add to Home Screen.
- **Phone CALL audio is impossible** (no OS/PWA API exposes call audio) — permanently
  out of scope; the phone is a room-mic, not a call-audio tap.
- **`tailscale serve --bg --https=<P> <P>` makes tailscaled ITSELF listen on <P>** (the
  tailnet HTTPS listener) AND proxy to localhost:<P>. Run the server on a DIFFERENT local
  port (9877) and serve `--https=9876 9877`; otherwise the server and tailscaled fight for
  9876 and you get `EADDRINUSE` that `lsof` (non-root) can't see — it's a tailscaled socket.
- **Phone audio merges with desktop sources at the FILE level.** The phone PWA writes the SAME
  `rolling.txt`/`full.txt` the desktop daemon does; each appends independently, tags
  distinguish them (`[phone]`, `[audio]`, `[mic]`). There is no merge step — two writers, one
  file. `phone` as a capture mode means NO local daemon (the phone feeds it), not a device.
- **Answer engine pins `reasoning_effort: "low"`** — GLM's global default is `high`; the copilot
  needs latency, not depth, so the payload hard-sets low so it never inherits a high default.

## Records: hide / restore / clear (per-record)

Records (vault .md files) support three lifetime actions in the pane:
- **hide** = soft — the `rel` path goes into `settings.json` `hidden_records` (kept on disk, dropped from the default list).
- **restore** = remove the `rel` from `hidden_records`.
- **clear** = hard delete (the `/session/delete` route, which also drops the rel from the hidden set).

The `/sessions` route returns `{sessions: visible, hidden: [...]}` so the pane can render a
"Hidden (N)" section. **The phone PWA now has full parity for records** — `/api/sessions`
returns the same `{sessions, hidden}` split, and `pwa_server.py` mirrors every management
route (`/api/session/hide | restore | delete | rename`), so the phone renders checkboxes,
hide/restore, a Hidden section and drives triage from **Save to vault**. `/api/sessions`
does NOT inline record bodies (it made the 5s poll ~80KB) — the phone fetches a body on
demand from `/api/record?rel=` for tap-to-open in a modal.

## Record mode = durable launchd watch agent (the fix for "no cards on a call")

Record mode is NOT spawned from an HTTP handler. The watch loop is the launchd agent
**`com.oz.meeting-watch`** (`~/Library/LaunchAgents/com.oz.meeting-watch.plist`,
`KeepAlive=true`, `ThrottleInterval=10`) running `answer.py --action watch`.

- The loop **never exits** — when `auto_assist` is off it IDLES (1s tick); when on and
the transcript has grown by ≥`chunk_sec`, it emits a card. So arming record mode
survives backend restarts, app reloads, and crashes.
- The backends (`/assist`, `/api/assist`, `/run watch`) only **set the flag** — they
never spawn. A second loop would double every card, so the spawn path and the old
pgrep singleton guard were both removed. Verified: `pgrep -f 'answer.py --action watch' | wc -l` stays `1`.
- **The history**: no-cards-on-a-real-call happened because the loop was spawned
ad-hoc from `/assist`, died with the backend, and nothing restarted it. The launchd
owner is the durable replacement. If cards ever stop again, check this first:
`launchctl list | grep meeting-watch`, `tail ~/.duckwork/meeting-transcript/watch.out`.
- **Growth baseline bug (fixed)**: `last_len` must RESET when the transcript shrinks
(cleared/trimmed), else `grown` stays False forever and no card is ever emitted again.

## Clear actions + model-off state

- **Clear all cards**: `POST /clear/deck` (desktop) / `POST /api/clear/deck` (PWA) —
empties `answers.json` + `answer.txt`. UI: trash icon in the deck header.
- **Clear transcript**: `POST /clear/transcript` / `POST /api/clear/transcript` —
empties `rolling.txt` + `full.txt`. UI: x-circle icon in the transcript header.
- **Model OFF**: `settings.model = 'off'` is a third model state — transcription keeps
flowing but the answer engine no-ops (`answer.py` prints `MODEL_OFF` and exits). Both
model chips are toggles: click the selected one to turn it off. Model-dependent answer
buttons dim; Save-to-vault (transcript-only) stays active. `do_watch` re-resolves the
model, so flipping off mid-record stops cards and re-picking resumes them.

**Clear button size is intentional — leave it small.** `.mini` is deliberately compact
(pad 3px 6px, 13px icon); the user explicitly asked for that size back after a 34px
experiment. Do NOT "fix" it into a big tap target. Clears report via the inline feedback
line (right of `Records (X)`) — a clear that silently works reads as broken.

**⚠️ Testing a clear wipes live data.** The transcript files ARE the meeting. Back them up
first (`cp rolling.txt /tmp/…`) or you destroy a real meeting's only copy. Recovery:
`rolling.txt` is a capped tail of `full.txt`, so a rolling backup restores both.

## Layout defaults

- **Cards on top by default** on both surfaces (`flipped = true`; PWA applies it via
`applyFlip()` at boot).
- **PWA toolbar order**: `[REC] [capture sources] [host/local]` — model on the right,
capture beside REC. REC is the pane's design: dot + "REC", red when live, muted idle.

## Desktop pane: TWO copies of plugin.js (the "my edits did nothing" trap)

The desktop app does NOT load `~/.duckwork/plugins/meeting-overlay/desktop/plugin.js`.
It loads a **synced copy** at `~/.duckwork/desktop-plugins/meeting-overlay/plugin.js`,
stamped by `.duckwork-package.json` (`source` + `sourceMtimeMs`). Editing the source does
nothing until that copy is re-synced and the pane is reloaded (⌘K → Reload desktop plugins).
Always edit the SOURCE, then copy it over and update `sourceMtimeMs`, then reload:

```bash
cp ~/.duckwork/plugins/meeting-overlay/desktop/plugin.js \
   ~/.duckwork/desktop-plugins/meeting-overlay/plugin.js
# then ⌘K → Reload desktop plugins
```

Verify with `diff -q` on the two paths — a mismatch means the pane is running stale JS.
The Python half (`dashboard/plugin_api.py`) needs a gateway restart (include_router runs at
startup); confirm a new route is live by grepping `/openapi.json` on the gateway port.

## Records: the save path works — verify it, don't assume

`Save to vault` → `/run {action:save}` → spawns `answer.py --action save` → writes
`<vault>/Records/YYYY/MM/<week>/<subject>.md` with a `## Transcript` block. Verified by
firing the route directly and confirming a new record appeared. A record with no Sep-11
row means the save never fired on that run — check `ls -t` on the Records tree (mtime is
the proof) rather than trusting that the button was pressed.

## Assist MODES (not one-shot buttons)

What-to-say / Follow-up / Research are **mutually-exclusive, PERSISTED listen modes**
(`settings.assist_mode` = `off|what|followup|research`; `auto_assist` is derived as
`!= off`). Selecting one only changes the setting — it never starts listening; the capture
toggles do that. The watch loop emits a card of the SELECTED mode every `chunk_sec` **only
when the transcript grows**, so selecting a mode while not recording produces nothing.
Clicking the active mode clears it (`off`). The label must NOT change to "Recording" — the
button stays its mode name and shows an accent-tinted selected state.
Backends: `POST /assist {assist_mode}` (desktop) / `/api/assist` (PWA) derive `auto_assist`.

## Save / Recap: feedback + no duplicates

- Both flash a transient note ("Saving…" → "Saved to Records ✓") and refresh the records
  list a few times, since the export runs in a detached subprocess.
- `do_save` is **idempotent by transcript hash** (`settings.last_saved_hash`): pressing Save
twice on an unchanged transcript returns "already saved" instead of creating a duplicate
  record. A changed transcript saves normally.
- Records live under `<vault>/Records/YYYY/MM/<week>/`; `ls -t` is the proof a save fired.

## Card drop: flash ON the drop frame, drop OPEN

`useLayoutEffect` (NOT `useEffect`) drives the drop-flash — it runs before paint, so the
flash class lands on the same frame the card first appears. Also update `prevNewest` on
EVERY pass, or the condition re-fires on later renders. New cards set `surfacedId = null`
so the newest card always drops OPEN.

## Selected-mode indicator + feedback position

The active assist mode MUST be unmistakable, not a faint tint: solid accent fill with
contrasting label (desktop: `background: var(--ui-accent)`, `color: onAccent`; PWA:
`.actions button.on` green fill + `box-shadow: 0 0 0 2px rgba(34,197,94,.28)`).
A subtle 18% `color-mix` tint reads as "no indicator" — the user reported exactly that.

Action feedback (Save/Recap/clear) renders **inline to the right of the `Records (X)`
label** — desktop: a flex row in the records header with the note `marginLeft:auto`;
PWA: `#recNote` (`flex:1; text-align:right`) in `.records .h`. No floating toast.

## Records list = triage queue (check to KEEP, Save commits)

The `Records (X)` list is a triage surface, not a passive list. Each visible row carries a
**checkbox**; the user checks the records they want to KEEP, then presses **Save to vault**.
That action (a) saves the current transcript, and (b) commits every checked row via
`POST /session/hide` — the row drops off the list and stays off (hidden persists in
`settings.hidden_records`, restorable from the Hidden section). Unchecked rows remain.

- Soft-hide, never delete, for the commit path: reversible and safe. `POST /session/delete`
  (the two-click ✕) is the separate hard-delete, and it unlinks the `.md` + `.field.json` so
a deleted record genuinely cannot return.
- The phone PWA has the **same triage** as the pane (checkboxes, hide/restore, Hidden
  section, Save commits the checked rows) — `pwa_server.py` mirrors `/api/session/*`.
- A saved-but-unchanged transcript must not create a second record (see the `do_save` hash
  dedupe) — otherwise the list grows on every Save press and looks like "records coming back".

## Tuning

- Accuracy vs speed: `MEETING_WHISPER_MODEL=small` (more accurate, downloads
  ~460MB once) or `base` (default, already cached). Both transcribe faster
  than realtime on Apple Silicon.
- Context window: `MEETING_ROLLING_CHARS` caps the rolling buffer.
- `MEETING_CHUNK_SEC` (default 5) — the **desktop** (`mic`/`audio`) window.

### Phone chunk length — the 1–2 word bug and the three knobs

The phone's transcript lines arrive 1–2 words at a time when `/ws/audio` closes chunks on
the wrong signal. **Silence must be measured on the AUDIO, never on frame arrival** — the
phone streams continuously, so a "time since last frame" check measures nothing and flushes
every ~1.2s. The loop therefore tracks `last_loud` from per-frame RMS and closes a chunk
only when either the window caps or real quiet holds **after** a minimum:

| Var | Default | Meaning |
|---|---|---|
| `MEETING_PHONE_CHUNK_SEC` | `15` | hard window cap |
| `MEETING_PHONE_MIN_SEC` | `8` | never emit a chunk shorter than this |
| `MEETING_PHONE_SILENCE_SEC` | `1.6` | quiet hold that closes a chunk |

Trade-off: `PHONE_MIN_SEC` **is** the latency of the last words in a chunk — a chunk cannot
be emitted until the window fills or the min is met. Raising it buys coherence, costs
responsiveness. Restart the PWA after changing any of them
(`launchctl kickstart -k "gui/$(id -u)/com.oz.meeting-pwa"`).

**Verify, don't assume:** `scripts/chunk_probe.py` renders slow speech with pauses via `say`,
streams it in real time, and prints old-vs-new chunk sizes on the same frames plus the lines
that landed. Measured: 15.6s of speech → 12×1.28s chunks before, **one 13.06s chunk producing
a 17-word line** after. Re-run it after any tuning change.

`listen.py` has no equivalent bug — it accumulates a clean `CHUNK_SEC` window with no
silence flush.
