---
name: adwhispr-instagram-research
description: "Pull any public Instagram account's organic posts, paid partnerships and UGC creators, ranked by views, likes, comments or recency. Use when the user asks for a brand's or creator's Instagram, IG posts, reels, organic content, creator collabs, or their latest or most-viewed videos."
---

# Instagram content research

## First run: connect AdWhispr

If no adwhispr tools are loaded, or a tool call fails with an authentication error, do NOT apologize and stop. Treat connecting as step one:

1. Connecting is free, takes one sign-in, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll pull their most-viewed reels and the creators posting about them."
4. After they connect, continue right where the request left off.

## Steps

1. Tracked brand: `get_instagram_content` with `brandId` (from `search_brands`). Any public creator or account: pass only `instagramHandle` (no tracking, no brand added).
2. `sort`: `top` (most views, default), `latest`, `most_liked`, `most_commented`.
3. The FIRST call for an account usually STARTS a scan of about a minute. Tell the user it is running and fetch again on their NEXT message. Do not re-call in the same response.
4. If a scan finds nothing (wrong handle or private profile), ask for the exact handle and re-call with `instagramHandle`.

## Using the results

- This is ORGANIC content; paid Meta ads come from `get_brand_ads`. Say which one you are showing.
- A standout reel can be cloned into the user's own finished video: pass its instagram.com/reel/... link to `clone_video_ad` (see adwhispr-clone-video-ad).
- Instagram scanning is a paid-plan feature; relay the upgrade link the tool returns on Free.
