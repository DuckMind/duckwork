# EmpirioLabs AI model provider for Duckwork Agent

[EmpirioLabs AI](https://empiriolabs.ai) is a specialized AI inference and integration provider. It hosts open-source models on GPU infrastructure it manages, runs optimized endpoints for proprietary models, helps teams ship their own models, and offers on-demand GPU Cloud instances and hosted AI agents. Its model catalog spans text, image, audio, video, transcription, embedding, reranking, research, and 3D models.

This plugin adds EmpirioLabs AI to Duckwork Agent as a model provider named `empiriolabs`. For image generation, video generation and text-to-speech, install the companion plugin [`empiriolabs-media`](../media/README.md).

## Requirements

- Duckwork Agent 0.21.6 or later
- An EmpirioLabs AI API key from https://platform.empiriolabs.ai/dashboard/api-keys

## Install

From the Duckwork plugin catalog:

```bash
duckwork plugins install empiriolabs
```

From GitHub (add `--ref <full commit SHA>` to pin a reviewed commit):

```bash
duckwork plugins install EmpirioLabs-AI/duckwork-empiriolabs/provider
```

The installer asks for `EMPIRIOLABS_API_KEY` and saves it to your Duckwork `.env` file. You can also add it there yourself.

## Use

Run `duckwork model`, choose **EmpirioLabs AI** and pick a model from the live catalog. In a session, `/model` switches models the same way.

Run a one-shot prompt:

```bash
duckwork -z "Summarize the README in this folder" --provider empiriolabs -m glm-5-3
```

Or set it in `config.yaml`:

```yaml
model:
  provider: empiriolabs
  default: glm-5-3
```

## What the plugin provides

- **Model list.** Chat models that support tool calling, read from `GET https://api.empiriolabs.ai/v1/models`. Duckwork sends tools with every request, so models without tool calling are left out. When the catalog cannot be reached, Duckwork offers two fallback ids (`glm-5-3`, `qwen3-7-flash`).
- **Model details.** Context window, image input and reasoning support for each model, from the same catalog.
- **Auxiliary model.** Duckwork uses a low-cost model for side tasks such as context compression and titles: `qwen3-7-flash`, the lowest-priced featured chat model with tool calling and at least a 200K context when this version was released. Where Duckwork asks the provider for a current pick, the plugin applies the same rule to the live catalog.
- **Reasoning effort.** When you choose a level with `/reasoning`, the plugin sends `reasoning_effort` to models that accept it, using the closest level the model offers without going higher. Nothing is sent when no level is set.
- **Endpoint override.** Set `EMPIRIOLABS_BASE_URL` to use a different API base URL (default `https://api.empiriolabs.ai/v1`).

## Data handling

- Duckwork sends your prompts, messages, tool definitions and tool results to `api.empiriolabs.ai` (or `EMPIRIOLABS_BASE_URL`) with your `EMPIRIOLABS_API_KEY`. Usage is billed to the EmpirioLabs AI account that owns the key.
- The plugin itself only reads the model catalog (`GET /v1/models`) and keeps it in memory for an hour. It writes no files, starts no background processes, runs no shell commands and sends no telemetry. It never reads or stores your key; Duckwork does.
- EmpirioLabs AI privacy policy: https://empiriolabs.ai/privacy-policy

## Links

- Website: https://empiriolabs.ai
- Documentation: https://docs.empiriolabs.ai
- Support: support@empiriolabs.ai
- Source: https://github.com/DuckMind/duckwork

## License

MIT
