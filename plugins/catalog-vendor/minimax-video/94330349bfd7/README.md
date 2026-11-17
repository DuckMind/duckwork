# duckwork-plugin-minimax-video

Video generation plugin for [Duckwork Agent](https://github.com/DuckMind/duckwork) using [MiniMax](https://platform.minimax.io) Hailuo models.

Brings MiniMax's Hailuo video models to Duckwork's `video_generate` tool. Supports text-to-video, image-to-video, and subject-reference-to-video generation.

## Models

| Model | Modes | Strengths |
|-------|-------|-----------|
| `MiniMax-Hailuo-2.3` | T2V, I2V | Latest model. 768P/1080P, 6 or 10s. Camera control via `[command]` syntax. |
| `MiniMax-Hailuo-2.3-Fast` | I2V | Faster I2V variant. 768P/1080P, 6 or 10s. |
| `MiniMax-Hailuo-02` | T2V, I2V | Previous gen. 512P/768P/1080P, 6 or 10s. Camera control. |
| `S2V-01` | S2V | Subject-reference-to-video: animate a character from reference images. |

Older models (`T2V-01`, `T2V-01-Director`, `I2V-01`, `I2V-01-Director`, `I2V-01-live`) are also supported -- pass them as the `model` parameter.

## Install

```bash
duckwork plugins install rriggs/duckwork-plugin-minimax-video
duckwork plugins enable minimax-video
```

## Configure

All configuration lives under `video_gen.minimax` in `config.yaml`:

```yaml
video_gen:
  provider: minimax
  minimax:
    api: https://api.minimax.io
    key_env: MINIMAX_PAYG_KEY
    model: MiniMax-Hailuo-2.3    # default for t2v/i2v
    model_s2v: S2V-01            # auto-used for subject reference
    # resolution: 768P           # optional
    # prompt_optimizer: true     # optional, defaults to true
```

| Key | Default | Description |
|-----|---------|-------------|
| `api` | `https://api.minimax.io` | MiniMax API base URL |
| `key_env` | `MINIMAX_API_KEY` | Name of the env var holding your API key |
| `model` | `MiniMax-Hailuo-2.3` | Default model for T2V and I2V |
| `model_s2v` | `S2V-01` | Model for subject-reference-to-video |
| `resolution` | `768P` (Hailuo-2.3/02), `720P` (others) | Video resolution |
| `prompt_optimizer` | `true` | Auto-optimize prompts |

Set the API key in your `.env` file:

```bash
MINIMAX_PAYG_KEY=***
```

No env var names are hard-coded -- `key_env` tells the plugin which env var to read.

## Usage

Once configured, Duckwork's `video_generate` tool routes through MiniMax automatically:

- **Text-to-video**: just provide a prompt
- **Image-to-video**: provide `image_url` (used as the first frame)
  - Accepts URLs (`https://...`), data URIs (`data:image/png;base64,...`), or local file paths (`/path/to/image.png`) -- local files are automatically base64-encoded inline
- **Subject-reference-to-video**: provide `reference_image_urls` (the character to animate)

### Camera Control

Hailuo-2.3, Hailuo-02, and Director models support camera movement commands embedded in the prompt using `[command]` syntax:

```
A man picks up a book [Pedestal up], then reads [Static shot].
```

Supported commands: `[Truck left]`, `[Truck right]`, `[Pan left]`, `[Pan right]`, `[Push in]`, `[Pull out]`, `[Pedestal up]`, `[Pedestal down]`, `[Tilt up]`, `[Tilt down]`, `[Zoom in]`, `[Zoom out]`, `[Shake]`, `[Tracking shot]`, `[Static shot]`.

Multiple commands inside one `[]` take effect simultaneously (e.g. `[Pan left,Pedestal up]`). Sequential movements use `then` (e.g. `...[Push in], then...[Push out]`).

### Duration and Resolution

- Duration: 6 or 10 seconds (MiniMax only supports these values)
- Resolution depends on model:
  - Hailuo-2.3 / Hailuo-2.3-Fast: 768P (default), 1080P
  - Hailuo-02: 512P, 768P (default), 1080P
  - Other models: 720P (default)

Generated videos are cached locally under `$DUCKWORK_HOME/cache/videos/`.

## API Details

This plugin uses the MiniMax video generation API:

```
POST {api}/v1/video_generation          # Submit task
GET  {api}/v1/query/video_generation    # Poll status (?task_id=X)
GET  {api}/v1/files/retrieve            # Get download URL (?file_id=X)
```

All video generation is asynchronous. The plugin handles the full flow: submit, poll (5s interval, 10min timeout), retrieve file URL, download and cache locally.

## Requirements

- Duckwork Agent v0.18+
- API key set in the env var named by `key_env`
- `requests` Python package (bundled with Duckwork)

## License

MIT