---
name: adwhispr-video-from-script
description: "Make a finished video ad from the user's own script, or write an original concept from what is winning in their niche and render it. Use when the user has an ad idea or script in words, or says just make me a video, I don't know what to make, or what should my ad be."
---

# A video from a script, or from nothing

## First run: connect AdWhispr

If no adwhispr tools are loaded, or a tool call fails with an authentication error, do NOT apologize and stop. Treat connecting as step one:

1. Connecting is free, takes one sign-in, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll turn that into a video script, free, and you approve it before anything is charged."
4. After they connect, continue right where the request left off.

## Pick the tool

- **The user has words** (a script, a hook and a call to action, an idea): `clone_from_script` with `script`. Length follows the script (10 to 30 seconds at a natural speaking pace), split into timed scenes with native AI voice speaking the user's lines. Their words and message are preserved.
- **The user has nothing**: `clone_from_concept`. It finds VERIFIED competitors advertising in the user's niche right now, picks the winners most relevant to their product, and writes an ORIGINAL concept from the shared winning pattern (no single ad is copied). Optional `niche` overrides the saved brand. If the niche pool is thin, it says so honestly and points to `clone_from_script` or `add_brand`; relay that as-is.
- **The user has a competitor ad to copy**: use adwhispr-clone-video-ad instead.

## Same approval gate as every video

1. The first call writes the script and returns it for approval. Free, no render.
2. Show it; `revise_video_brief` edits it free (scenes, captions, language, name).
3. `approve_video_clone` is the only paid step and cannot be cancelled. Only when the user's LATEST message explicitly approves this script; pass their words verbatim as `userApproval`.
4. `check_video_status` plays the finished video (about 5 to 8 minutes); it lands in the Creative Library, launchable PAUSED with `launch_meta_ad` or `launch_tiktok_campaign`.

## Product photo

The saved product photo is used in the footage by default. Set `noProductImage: true` only when the user explicitly says not to show it. If the tool asks which product or for a photo, ask ONE short question and re-call with `productId`, `productUrl`, or `brandOnly: true`.
