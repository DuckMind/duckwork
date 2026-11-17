---
name: adwhispr-agent
description: "Safety contract and routing for every AdWhispr job: competitor ad research, ad cloning, and campaign execution on Meta, Google, TikTok, X and ChatGPT Ads. Load first for any advertising task, or when unsure which AdWhispr skill or tool fits."
---

# AdWhispr: how to work

AdWhispr does three jobs from chat, in this order of value:

1. **Research**: which brands in a niche are advertising right now, their longest-running (proven) ads on Meta and TikTok, their Instagram content, and Google keyword data.
2. **Cloning**: turn a proven ad into the user's own finished image or video, adapted to their brand and product.
3. **Execution**: launch, review, and optimize campaigns on the user's own Meta, Google, TikTok, X and ChatGPT Ads accounts.

## First run: connect AdWhispr

If no adwhispr tools are loaded, or a tool call fails with an authentication error, do NOT apologize and stop. Treat connecting as step one:

1. Connecting is free, takes one sign-in, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Then continue the request right where it left off. Never make the user repeat it.

## Routing

| The user wants | Skill | Main tools |
| --- | --- | --- |
| A first win / "what can you do" | adwhispr-get-started | get_my_brand, save_my_brand, find_competitors |
| Who advertises in their space | adwhispr-competitor-research, adwhispr-niche-ad-report | find_competitors, search_brands, get_brand_ads |
| Proven winners | adwhispr-longest-running-ads | get_brand_ads (sortBy longevity) |
| Angles, hooks, offers | adwhispr-winning-angle-extractor | get_brand_ads, generate_brief |
| Two brands side by side | adwhispr-brand-vs-brand | compare_brands |
| A rival's new launches | adwhispr-new-ad-watch | get_brand_ads |
| A brand's Instagram | adwhispr-instagram-research | get_instagram_content |
| Keywords | adwhispr-keyword-universe-builder, adwhispr-competitor-keyword-spy | research_keywords, research_competitor_keywords |
| Clone an ad (overview) | adwhispr-clone-winning-ads | clone_ad, clone_video_ad |
| A finished image | adwhispr-clone-image-ad | clone_ad, launch_cloned_ad |
| A finished video from a competitor ad, reel, TikTok or their own video | adwhispr-clone-video-ad | clone_video_ad, revise_video_brief, approve_video_clone, check_video_status |
| A video from their own script, or from nothing | adwhispr-video-from-script | clone_from_script, clone_from_concept |
| Launch / manage per platform | adwhispr-meta-ads, adwhispr-google-ads, adwhispr-tiktok-ads, adwhispr-x-ads, adwhispr-chatgpt-ads | launch_* tools |
| How their campaigns are doing | adwhispr-campaign-review | get_account_performance, inspect_ad_account |
| Wasted spend | adwhispr-wasted-spend-audit | get_account_performance |
| Move budget | adwhispr-budget-reallocation | update_budget |
| Tired creatives | adwhispr-creative-fatigue-refresh | get_account_performance, clone tools |

## The safety contract (always applies)

- **Every campaign is created PAUSED.** A successful launch does not mean it is delivering; use `inspect_ad_account` (Meta) to answer "is my ad running?".
- **Spend-affecting tools are two-step.** `launch_*`, `update_budget`, `update_campaign_locations`, `update_keywords`, `add_negative_keywords` and `resume_campaign` first return a preview and a `confirmToken`. Show the preview, get the user's explicit OK, then call again with the same arguments plus that token. Never invent or reuse a token.
- **`resume_campaign` starts real spend.** Surface its warning and confirm before passing the token.
- **Rendering a video is the only paid creative step.** `approve_video_clone` charges video credits and cannot be cancelled. Call it only when the user's LATEST message explicitly approves THIS script, and pass their words verbatim in `userApproval`.
- **Never ask for keys, tokens or passwords in chat.** `connect_ad_account` returns a browser link; ChatGPT Ads opens an AdWhispr page where the user pastes their Ads API key.
- **Never launch competitor media.** Only the user's own creatives or AdWhispr clones made for their brand.
- **Never guess an objective or invent targeting ids.** Ask for the goal; resolve ids with `search_ad_targeting`.
- **Quote prices from the tools.** Plans, quotas and credit prices change; relay the numbers a tool returns, never numbers from memory. When a tool returns an upgrade or buy link, relay it as-is.

## Always drive to one next step

End every answer with exactly ONE concrete next step tied to what just happened: no brand saved, then ask for their site; brand saved, then show verified competitors; competitors shown, then their longest-running ads; a winner found, then offer to clone it; a creative ready, then offer to launch it (paused). One step, never a menu.
