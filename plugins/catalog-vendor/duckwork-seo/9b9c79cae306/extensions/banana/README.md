# Banana image generation extension

This extension preserves SEO-oriented image prompts and helper scripts from the source project. It does not install a skill, agent, or MCP server and does not configure Claude Code. The optional generation workflow needs a compatible image-generation MCP provider and `GOOGLE_AI_API_KEY` stored in the active Duckwork profile. The parent native tool injects that secret for the selected script; the helpers never accept it as a command argument. Image generation can incur cost; review current provider pricing before use.

Use Duckwork `skills_list` and `skill_view` to discover the registered image workflow. Local, credential-free planning helpers can run through the CLI. Credentialed helpers must run through the native `duckwork_seo_run` tool so the active profile secret is scoped to that process, for example:

```bash
duckwork seo run --extension banana batch.py --csv requests.csv
```

```json
{"script":"validate_setup.py","extension":"banana","args":["--model","<verified-model-id>"]}
```

The helper scripts can support planning and validation; they do not establish provider connectivity. Image generation should happen only after the user approves the specific generation/cost.

See [setup notes](docs/BANANA-SETUP.md) and the retained references for prompt structure, presets, and post-processing. Historical source references to Claude Banana identify the original project, not a runtime dependency of this Duckwork fork.
