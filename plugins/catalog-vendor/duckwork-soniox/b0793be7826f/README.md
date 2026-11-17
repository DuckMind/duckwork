# duckwork-soniox

Native **BYOK** [Soniox](https://soniox.com) text-to-speech and speech-to-text for
[Duckwork Agent](https://github.com/DuckMind/duckwork). Provider id: `soniox` (both TTS and STT).
It calls Soniox directly with your own `SONIOX_API_KEY` — no proxy, no gateway, no third-party middleman.
STT auto-detects language by default; TTS defaults to English with `Adrian` and can be configured for every
language and voice exposed by the selected Soniox model. The plugin uses only Duckwork-bundled `httpx` plus the
standard library.

## Install

```bash
duckwork plugins install XimilalaXiang/duckwork-soniox
duckwork plugins enable duckwork-soniox
```

Add your key to `~/.duckwork/.env` (never to `config.yaml`):

```bash
SONIOX_API_KEY=your-soniox-key
```

## Data path (what leaves your machine)

| Feature | Destination | Data sent |
|---|---|---|
| TTS | `POST https://tts-rt.soniox.com/tts` | reply text, model, voice, language, format, speed |
| STT | `https://api.soniox.com/v1` (`/files`, `/transcriptions`) | the audio file, optional language hints and prompt text |

The key is sent only as an `Authorization: Bearer` header to those two Soniox hosts. It is resolved through
Duckwork' active-profile secret scope on each call, never written to `config.yaml`, returned, logged, or included
in error messages. This keeps credentials isolated when one gateway serves multiple Duckwork profiles.
After each transcription the plugin deletes the remote transcription and the uploaded file (best effort).
Soniox's own retention and billing terms apply to anything you send.

## Configuration

```yaml
tts:
  provider: soniox
  model: tts-rt-v2      # optional; non-"tts-*" values are ignored
  voice: Adrian         # optional; any voice id from GET /v1/tts-models
  soniox:
    language: en        # optional, default en
stt:
  enabled: true
  provider: soniox
  soniox:
    model: stt-async-v5 # optional
    # language: en      # optional hint; omit for automatic language detection
```

Defaults: TTS model `tts-rt-v2`, language `en`, voice `Adrian`; STT model `stt-async-v5` with automatic
language detection. Nothing restricts the plugin to English: set any model-supported language and voice.

### Chinese preset

```yaml
tts:
  provider: soniox
  model: tts-rt-v2
  voice: Meilin
  soniox:
    language: zh
stt:
  enabled: true
  provider: soniox
  soniox:
    model: stt-async-v5
    language: zh
```

How Duckwork passes settings (verified against Duckwork v0.22.4): TTS receives `tts.voice`, `tts.model`,
`tts.speed` and `tts.output_format` from the dispatcher; `tts.soniox.language` is read by the plugin itself.
STT receives `stt.soniox.model`; its optional language hint resolves in this order:
`stt.soniox.language` → `stt.language` → legacy `DUCKWORK_LOCAL_STT_LANGUAGE` → no hint. With no resolved hint,
Soniox detects the language. `stt.prompt` is sent as `context.text`.

- **Languages**: BCP-47 values are reduced to the ISO code (`zh-CN` → `zh`). STT accepts a comma-separated
  list (`zh,en`) which is sent as `language_hints`; hints bias recognition, they do not restrict it.
- **Voices**: Soniox built-in voice names or a cloned voice id. The plugin's catalog is a short static list;
  the authenticated `GET https://api.soniox.com/v1/tts-models` catalog confirms that `tts-rt-v2` supports
  `Meilin` and Chinese (`zh`). Any voice can speak any language supported by the model. `tts.voice`/`tts.model`
  are shared Duckwork keys; a stale value from another provider (a non-`tts-*` model is ignored, a voice is not)
  will be sent as-is.
- **Speed**: Duckwork allows 0.25–4.0; Soniox accepts 0.7–1.3, so values are clamped into that range.
- **Formats**: `mp3`, `wav`, `flac` natively; `ogg`/`opus` request Soniox `opus` (saved as `.ogg` if the
  response is an Ogg container, otherwise `.opus`). Unknown formats fall back to `mp3`.
  The provider opts into voice bubbles; Duckwork converts to Opus with ffmpeg when needed.
- **Limits**: TTS text ≤ 5000 characters (the Soniox limit; Duckwork may apply its own cap first). STT polls with backoff
  (1s → 5s) for up to 300 s until `completed`/`error`, then fails with a timeout error.
- Realtime WebSocket TTS/STT is not implemented in 0.2.0.

## Testing

```bash
uv venv --python 3.14 .venv-test && uv pip install --python .venv-test/bin/python pytest ruff httpx
.venv-test/bin/python -m pytest -q
.venv-test/bin/python -m ruff check .
```

Tests use mocked HTTP only and need no credentials. They import Duckwork' provider ABCs from
`~/.duckwork/duckwork-agent` (override with `DUCKWORK_AGENT_PATH`).

For catalog admission, validate a clean tracked-files export rather than the development directory: the
recursive security scanner intentionally sees dependencies inside `.venv-test` as plugin content.

## Troubleshooting

- *"SONIOX_API_KEY is not set"* — add it to `~/.duckwork/.env` and restart Duckwork.
- *HTTP 401* — wrong key. *HTTP 402* — Soniox balance/budget exhausted. *HTTP 429* — rate/concurrency limit.
- *HTTP 400 invalid_request* on TTS — voice or language not valid for the model; check `/v1/tts-models`.
- *"transcription timed out"* — very long audio; retry or split the file.
- Provider not picked up — `duckwork plugins list`, ensure it is enabled, and that `tts.provider`/`stt.provider` is exactly `soniox`.

## Uninstall / rollback

```bash
duckwork plugins disable duckwork-soniox
duckwork plugins uninstall duckwork-soniox
```

Then set `tts.provider` / `stt.provider` back to your previous provider and remove `SONIOX_API_KEY`
from `~/.duckwork/.env` if you no longer need it.

## License

MIT
