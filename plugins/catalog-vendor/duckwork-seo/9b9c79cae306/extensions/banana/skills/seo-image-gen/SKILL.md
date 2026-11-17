---
name: seo-image-gen
description: "AI image generation for SEO assets: OG/social preview images, blog hero images, schema images, product photography, infographics. Powered by Gemini via nanobanana-mcp. Requires banana extension installed. Use when user says \"generate image\", \"OG image\", \"social preview\", \"hero image\", \"blog image\", \"product photo\", \"infographic\", \"seo image\", \"create visual\", \"image-gen\", \"favicon\", \"schema image\", \"pinterest pin\", \"generate visual\", \"banner\", or \"thumbnail\"."
argument-hint: "[og|hero|product|infographic|custom|batch] <description>"
user-invocable: true
license: MIT
compatibility: "Requires nanobanana MCP server"
metadata:
  author: AgriciDaniel
  version: "2.4.2"
  category: seo
---

# SEO Image Gen: AI Image Generation for SEO Assets (Extension)

Generate production-ready images for SEO use cases using Gemini's image generation
via the banana Creative Director pipeline. Maps SEO needs to optimized domain modes,
aspect ratios, and resolution defaults.

## Architecture Note

This extension is built on [Claude Banana](https://github.com/AgriciDaniel/banana-claude),
a standalone AI image generation skill; this file is an optional Duckwork provider reference.

This optional companion reference is not itself a registered Duckwork skill. The registered core `duckwork-seo:seo-image-gen` workflow and role `duckwork-seo:role-seo-image-gen` provide the invocable entry points:
- This file: optional Gemini provider guidance for the registered core image-generation workflow.
- `duckwork-seo:role-seo-image-gen`: audit-only analyst used with `duckwork-seo:seo-audit` to assess existing OG/social images and produce a generation plan (never auto-generates).

## Prerequisites

This reference is bundled with Duckwork SEO. Configure a compatible Gemini image MCP server in Duckwork to enable generation. Store `GOOGLE_AI_API_KEY` as a secret in the active Duckwork profile; the parent native tool injects it only for Banana provider scripts. Never place the key in command arguments.

**Check availability:** Before using any image generation tool, verify the MCP server
is connected by checking if `gemini_generate_image` or `set_aspect_ratio` tools are
available. If tools are not available, inform the user the provider MCP is not configured in Duckwork
and explain Duckwork provider setup.

## Quick Reference

| Command | What it does |
|---------|-------------|
| Use the registered `duckwork-seo:seo-image-gen` workflow to generate og <description>` | Generate OG/social preview image (1200x630 feel) |
| Use the registered `duckwork-seo:seo-image-gen` workflow to generate hero <description>` | Blog hero image (widescreen, dramatic) |
| Use the registered `duckwork-seo:seo-image-gen` workflow to generate product <description>` | Product photography (clean, white BG) |
| Use the registered `duckwork-seo:seo-image-gen` workflow to generate infographic <description>` | Infographic visual (vertical, data-heavy) |
| Use the registered `duckwork-seo:seo-image-gen` workflow to generate custom <description>` | Custom image with full Creative Director pipeline |
| Use the registered `duckwork-seo:seo-image-gen` workflow to generate batch <description> [N]` | Generate N variations (default: 3) |

## SEO Image Use Cases

Each use case maps to pre-configured banana parameters:

| Use Case | Aspect Ratio | Resolution | Domain Mode | Notes |
|----------|-------------|------------|-------------|-------|
| **OG/Social Preview** | `16:9` | `1K` | Product or UI/Web | Clean, professional, text-friendly |
| **Blog Hero** | `16:9` | `2K` | Cinema or Editorial | Dramatic, atmospheric, editorial quality |
| **Schema Image** | `4:3` | `1K` | Product | Clean, descriptive, schema ImageObject |
| **Social Square** | `1:1` | `1K` | UI/Web | Platform-optimized square |
| **Product Photo** | `4:3` | `2K` | Product | White background, studio lighting |
| **Infographic** | `2:3` | `4K` | Infographic | Data-heavy, vertical layout |
| **Favicon/Icon** | `1:1` | `512` | Logo | Minimal, scalable, recognizable |
| **Pinterest Pin** | `2:3` | `2K` | Editorial | Tall vertical card |

## Generation Pipeline

For every generation request:

1. **Identify use case** from command or context (og, hero, product, etc.)
2. **Apply SEO defaults** from the use cases table above
3. **Set aspect ratio** via `set_aspect_ratio` MCP tool
4. **Construct Reasoning Brief** using the banana Creative Director pipeline:
   - Load `references/prompt-engineering.md` with `duckwork seo show extensions/banana/references/prompt-engineering.md` for the 6-component system
   - Apply domain mode emphasis (Subject 30%, Style 25%, Context 15%, etc.)
   - Be SPECIFIC and VISCERAL: describe what the camera sees
5. **Generate** via `gemini_generate_image` MCP tool
6. **Post-generation SEO checklist** (see below)

### Check for Presets

If the user mentions a brand or has SEO presets configured:
```bash
duckwork seo run --extension banana presets.py list
```
Load matching preset and apply as defaults. For SEO-specific preset templates, read
`extensions/banana/references/seo-image-presets.md` with `duckwork seo show extensions/banana/references/seo-image-presets.md`.

## Post-Generation SEO Checklist

After every successful generation, guide the user on:

1. **Alt text**:Write descriptive, keyword-rich alt text for the generated image
2. **File naming**:Rename to SEO-friendly format: `keyword-description-widthxheight.webp`
3. **WebP conversion**:Convert to WebP for optimal page speed:
   ```bash
   magick output.png -quality 85 output.webp
   ```
4. **File size**:Target under 200KB for hero images, under 100KB for thumbnails
5. **Schema markup**:Suggest `ImageObject` schema for the generated image:
   ```json
   {
     "@type": "ImageObject",
     "url": "https://example.com/images/keyword-description.webp",
     "width": 1200,
     "height": 630,
     "caption": "Descriptive caption with target keyword"
   }
   ```
6. **OG meta tags**:For social preview images, remind about:
   ```html
   <meta property="og:image" content="https://example.com/images/og-image.webp" />
   <meta property="og:image:width" content="1200" />
   <meta property="og:image:height" content="630" />
   <meta property="og:image:alt" content="Descriptive alt text" />
   ```

## Cost Awareness

Image generation costs money. Be transparent:
- Show estimated cost before generating (especially for batch)
- Log every generation: `duckwork seo run --extension banana cost_tracker.py log --model MODEL --resolution RES --prompt "brief"`
- Run `duckwork seo run --extension banana cost_tracker.py summary` if user asks about usage

Pricing is not hard-coded. Check current Google pricing at
https://ai.google.dev/gemini-api/docs/pricing, store dated values in
`~/.banana/pricing.json`, and treat estimates as approximate.

## Model Routing

| Scenario | Model | Why |
|----------|-------|-----|
| OG images, social previews | Verified `NANOBANANA_MODEL` @ 1K | Fast, cost-aware |
| Hero images, product photos | Verified `NANOBANANA_MODEL` @ 2K if supported | Quality + detail |
| Infographics with text | Verified `NANOBANANA_MODEL` @ 2K if supported, thinking: high | Better text rendering |
| Quick drafts | Verified `NANOBANANA_MODEL` @ 512 if supported | Rapid iteration |

## Error Handling

| Error | Resolution |
|-------|-----------|
| MCP not configured | Configure the Gemini image provider in Duckwork and grant its MCP tool access; do not write credentials into repository files. |
| API key invalid | New key at https://aistudio.google.com/apikey |
| Rate limited (429) | Wait 60s, retry. Check current free-tier limits before batch operations |
| `IMAGE_SAFETY` | Rephrase prompt - see `references/prompt-adaptation-safety.md` |
| MCP unavailable | Call the native `duckwork_seo_run` tool for Banana `generate.py` with prompt, aspect-ratio, and model arguments after the provider is configured. |
| CSV batch input | Plan first: `duckwork seo run --extension banana batch.py --csv requests.csv --model "$NANOBANANA_MODEL"` |
| Extension not installed | Use the bundled extension files from the Duckwork SEO plugin; provider setup remains separate. |

## Cross-Skill Integration

- **seo-images** (analysis) feeds into **seo-image-gen** (generation): audit results from `duckwork-seo:seo-images` identify missing or low-quality images; use those findings to drive `duckwork-seo:seo-image-gen` commands
- **seo-audit** spawns the seo-image-gen **agent** (not this skill) to analyze OG/social images across the site and produce a prioritized generation plan
- **seo-schema** can consume generated images: after generation, suggest `ImageObject` schema markup pointing to the new assets

## Reference Documentation

These companion files are optional reference material, not separately registered Duckwork skills. Load on demand:
These reference files live under `extensions/banana/references/`; load them with
`duckwork seo show extensions/banana/references/<filename>.md` when needed:
`prompt-engineering.md`, `prompt-templates.md`, `prompt-adaptation-safety.md`,
`gemini-models.md`, `mcp-tools.md`, `post-processing.md`, `cost-tracking.md`,
`presets.md`, and `seo-image-presets.md`.

## Response Format

After generating, always provide:
1. **Image path**:where it was saved
2. **Crafted prompt**:show what was sent to the API (educational)
3. **Settings**:model, aspect ratio, resolution
4. **SEO checklist**:alt text suggestion, file naming, WebP conversion
5. **Schema snippet**:ImageObject or og:image markup if applicable
