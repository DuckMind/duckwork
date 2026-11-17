---
name: adwhispr-clone-winning-ads
description: "Turn a competitor's proven ad into the user's own finished creative and get it live. Use when the user wants to copy, clone, remix, or adapt a winning ad they found (Meta, TikTok, an Instagram reel, or their own video), wants a script based on a competitor's ad, or wants to launch a clone."
---

# Clone proven winners, then launch

## First run: connect AdWhispr

If no adwhispr tools are loaded, or a tool call fails with an authentication error, do NOT apologize and stop. Treat connecting as step one:

1. Connecting is free, takes one sign-in, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll turn that winning ad into your own version, and you see it before anything is charged."
4. A free account is enough to start. After they connect, continue right where the request left off.

The loop: find an ad that has survived months of spend, rebuild it for the user's brand, launch it paused, let the user flip it live.

## 1. Pick a source worth cloning

Longevity is the honest proxy for a winner. Use `get_brand_ads` with `sortBy: longevity` (adwhispr-longest-running-ads) or `research_tiktok_ads` for TikTok. Make sure the user's brand is saved (`get_my_brand`; if empty, ask for their site and call `save_my_brand`).

## 2. Choose the output

| Source | User wants | Tool | Skill |
| --- | --- | --- | --- |
| Image ad | finished image | `clone_ad` | adwhispr-clone-image-ad |
| Video ad, Instagram reel, TikTok link, or the user's own video | finished video | `clone_video_ad` | adwhispr-clone-video-ad |
| Video ad | a script they will shoot themselves | `clone_ad` with `asScript: true` | |
| TikTok ad from `research_tiktok_ads` | a shoot-ready script | `clone_tiktok_ad` | adwhispr-tiktok-ads |
| No source, only their own words or an idea | finished video | `clone_from_script` / `clone_from_concept` | adwhispr-video-from-script |

"Clone it" on a video means MAKE the video. Only give a script when the user explicitly asks for one.

## 3. Launch it (paused)

- Image clone: `launch_cloned_ad` (Meta). Write the primary text and headline fresh for the user's product; the link is the user's own page. The competitor's copy and URL are never used.
- Finished video or the user's own media: `launch_meta_ad` (Meta, by `creativeName`; 2 to 10 cards make a carousel or a creative test) or `launch_tiktok_campaign` (by `creativeName`; 2 to 5 `creativeNames` make a creative test).
- `list_my_creatives` shows everything in the Creative Library.

## Rules

- Source STRUCTURE is preserved; copy, people, footage and logos are always new and the user's own. Never launch competitor media as the user's creative.
- Product questions: when a clone tool asks which product (or for a product photo) instead of generating, ask ONE short question and re-call with `productId`, `productUrl`, `productImage` (image clones) or `brandOnly: true`. Nothing is generated or charged when it asks.
- Launches are two-step with a `confirmToken` and always created PAUSED; `resume_campaign` is what starts spend.
