---
name: adwhispr-clone-video-ad
description: "Clone a winning video ad into a finished, ready-to-launch video for the user's brand, from a Meta ad, an Instagram reel, a TikTok link, or the user's own video, with a free script approval before any credit is charged. Use when the user wants a video ad, says clone this video, or shares a reel or TikTok to copy."
---

# Clone a winning video ad (finished video)

## First run: connect AdWhispr

If no adwhispr tools are loaded, or a tool call fails with an authentication error, do NOT apologize and stop. Treat connecting as step one:

1. Connecting is free, takes one sign-in, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll write the script for your version of that ad, free, and you approve it before anything is charged."
4. After they connect, continue right where the request left off.

## What it makes

A finished vertical video for the user's brand: length matched to the source (10 to 30 seconds), native AI voice in the footage (presenters, narrators, two-person dialogue), and the source's visual style (live action stays live action, cartoons clone as cartoons). The footage, people and logos are always new; the competitor's are never reused.

## Sources `clone_video_ad` accepts as `adId`

- A video ad from `get_brand_ads` (UUID), a Meta Ad Library ID, or a facebook.com/ads/library URL.
- An Instagram reel (instagram.com/reel/...) or a TikTok (tiktok.com/@user/video/..., vm.tiktok.com/...). The FIRST call only pulls it and shows a playable card: ask "is this the one?", then call again with the returned `adId`. These get a new instrumental bed matched to the original sound; the original audio is never reused.
- The user's own video: its id or exact name from `list_my_creatives`, or a direct .mp4/.mov/.webm link.

## The approval gate (free until approval)

1. `clone_video_ad` analyzes the source and writes a scene-by-scene script. It does NOT render or charge. About 30 to 60 seconds.
2. `check_video_status` (with the jobId) shows the script, the exact length, the on-screen text, and the credit quote. Show it to the user.
3. Changes: `revise_video_brief` with only the fields to change (`scenes`, `captions`, `language`, `newName`, `noProductImage`, ...). Free, as many times as needed.
4. `approve_video_clone` is the ONLY paid step and cannot be cancelled. Call it only when the user's LATEST message explicitly approves rendering this script ("yes, render it"), and pass their words verbatim as `userApproval`. Questions, discussion, or "how much?" are not approval. If credits are short it returns a buy link; relay it (the script is saved).
5. The render takes about 5 to 8 minutes. `check_video_status` plays it inline when done; it lands in the Creative Library.

## Product questions

If the tool asks instead of writing (several saved products, no product photo for a physical-goods brand, or a site photo to confirm), ask ONE short question and re-call with `productId`, `productUrl`, or `brandOnly: true`. Nothing is written or charged when it asks. Never pass a model; there is none to choose.

## After delivery

- Caption cards (the top 'hook' and bottom 'caption' text boxes) can be edited free on a finished video with `revise_video_brief` `captions`; it is redrawn as a new library version in about a minute. Spoken words, footage or music need a new render.
- Launch with `launch_meta_ad` or `launch_tiktok_campaign` (by `creativeName`), created PAUSED, two-step confirm.
