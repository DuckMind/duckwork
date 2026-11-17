# EmpirioLabs AI media backends for Duckwork Agent

[EmpirioLabs AI](https://empiriolabs.ai) is a specialized AI inference and integration provider. It hosts open-source models on GPU infrastructure it manages, runs optimized endpoints for proprietary models, helps teams ship their own models, and offers on-demand GPU Cloud instances and hosted AI agents. Its model catalog spans text, image, audio, video, transcription, embedding, reranking, research, and 3D models.

This plugin adds three EmpirioLabs AI backends to Duckwork Agent, each named `empiriolabs`:

| Duckwork tool | Backend setting | What it does |
|---|---|---|
| `image_generate` | `image_gen.provider: empiriolabs` | Image generation and image editing |
| `video_generate` | `video_gen.provider: empiriolabs` | Text-to-video and image-to-video |
| `text_to_speech` | `tts.provider: empiriolabs` | Text-to-speech |

It registers no tools, hooks or commands of its own. For chat models, install the companion plugin [`empiriolabs`](../provider/README.md).

## Requirements

- Duckwork Agent 0.21.6 or later
- An EmpirioLabs AI API key from https://platform.empiriolabs.ai/dashboard/api-keys

## Install

From the Duckwork plugin catalog:

```bash
duckwork plugins install empiriolabs-media
```

From GitHub (add `--ref <full commit SHA>` to pin a reviewed commit):

```bash
duckwork plugins install EmpirioLabs-AI/duckwork-empiriolabs/media
```

Enable it when the installer asks, or later with `duckwork plugins enable empiriolabs-media`. The installer also asks for `EMPIRIOLABS_API_KEY` and saves it to your Duckwork `.env` file.

## Choose models

Run `duckwork tools`, open Image Generation or Video Generation, select **EmpirioLabs AI** and pick a model; the lists come from the live catalog at `GET https://api.empiriolabs.ai/v1/models`. For Text-to-Speech, select **EmpirioLabs AI** in the same menu and set a model and voice in `config.yaml` when you want something other than the defaults.

You can also set everything in `config.yaml`:

```yaml
image_gen:
  provider: empiriolabs
  model: flux-2-klein-4b
video_gen:
  provider: empiriolabs
  model: hunyuan-video-1-5
  empiriolabs:
    timeout_seconds: 900   # how long one video_generate call waits
tts:
  provider: empiriolabs
  model: tts-2-flash
  voice: Sarah
```

Without a model setting, each backend uses the model named above when it is in the catalog, and otherwise the first featured model of that kind. A model id that is not in the EmpirioLabs AI catalog (for example one left over from another backend) is ignored. `image_gen.empiriolabs.model`, `video_gen.empiriolabs.model`, `tts.empiriolabs.model` and `tts.empiriolabs.voice` set a model or voice for this backend only.

## How each backend works

- **Images.** One request to `POST /v1/images/generations`. When a generation runs long, the plugin polls `GET /v1/jobs/{job_id}` for up to 10 minutes. To edit an image, the agent passes `image_url`: an https URL, a `data:image` URI, or a local PNG, JPEG, WebP or GIF file of up to 20 MB, which is sent inline. Editing is offered when the selected model accepts input images.
- **Videos.** One request to `POST /v1/videos/generations`, then `GET /v1/jobs/{job_id}` every 5 seconds for up to 15 minutes (`video_gen.empiriolabs.timeout_seconds`). If the wait ends first, the job keeps running and the tool result gives its job id and the URL to fetch it from. Duration, resolution and aspect ratio are matched to the values the model offers. Pass `image_url` to animate an image.
- **Speech.** One request to `POST /v1/audio/speech` per piece of text. Voices and output formats come from the selected model. When the text is longer than the model accepts in one request, it is split at sentence boundaries and the MP3 pieces are joined.
- Generated images and videos are downloaded into Duckwork' cache (`$DUCKWORK_HOME/cache/generated/`); if that download fails, the tool result gives the signed URL instead. Speech is written to the file Duckwork asks for.

## Data handling

- Prompts, source images and the text to speak go to `api.empiriolabs.ai` (or `EMPIRIOLABS_BASE_URL`) with your `EMPIRIOLABS_API_KEY`. Each image, video and speech request is billed to the EmpirioLabs AI account that owns the key, and Duckwork does not ask for approval before a backend call.
- Generated files are downloaded from the URLs the API returns. The key is never sent to those URLs, and every download address is checked with Duckwork' URL safety check.
- To edit a local image, the plugin reads that one file. It reads no other files, writes only the generated media into Duckwork' cache, starts no background processes, runs no shell commands and sends no telemetry. It reads your key through Duckwork and never stores it.
- EmpirioLabs AI privacy policy: https://empiriolabs.ai/privacy-policy

## Links

- Website: https://empiriolabs.ai
- Documentation: https://docs.empiriolabs.ai
- Support: support@empiriolabs.ai
- Source: https://github.com/DuckMind/duckwork

## License

MIT
