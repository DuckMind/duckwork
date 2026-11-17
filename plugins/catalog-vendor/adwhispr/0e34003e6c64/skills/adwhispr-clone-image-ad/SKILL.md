---
name: adwhispr-clone-image-ad
description: "Clone a competitor's winning image ad into a finished image for the user's brand, tweak it, and launch it as a paused Meta ad. Use when the user wants an image ad, a static ad, or says clone this image, make me a similar ad, or change the headline on my clone."
---

# Clone a winning image ad

## First run: connect AdWhispr

If no adwhispr tools are loaded, or a tool call fails with an authentication error, do NOT apologize and stop. Treat connecting as step one:

1. Connecting is free, takes one sign-in, and there are no API keys to manage.
2. Duckwork: the first AdWhispr tool call opens a browser for the AdWhispr sign-in (OAuth, nothing to paste). Ask them to finish it, then run /reload-mcp or start a new session so the tools load. If the browser did not open, run /reload-mcp to retry the sign-in.
3. Tell them the payoff: "the second you're connected, I'll rebuild that ad as a finished image with your product, logo and copy."
4. A free account is enough for a first clone. After they connect, continue right where the request left off.

## Steps

1. Get the source `adId` from `get_brand_ads` (prefer the longest-running image ads). A Meta Ad Library ID or a facebook.com/ads/library URL also works.
2. Call `clone_ad` with `adId`. If the brand is not saved, pass `productUrl` (the user's product page) and it is extracted and saved. Generation takes about 30 to 60 seconds and returns the image inline.
3. If the tool ASKS instead of generating (several products, no product photo, or a site photo to confirm), relay ONE short question and re-call with `productId`, `productImage` (a direct https image link the user owns), `productUrl`, or `brandOnly: true`.
4. Tell the user which product photo the clone used. If it says no product photo was on file, say the product in the picture is a stand-in and offer to redo it with their photo.

## Tweaks (never re-clone for a change)

"Change the headline", "make the logo bigger", "use my real product": call `clone_ad` with `editClonedAdId` (the clonedAdId, or the clone's name from `list_my_creatives`) plus `edit` in the user's own words, and/or `productImage`/`productId` to swap the product. Only the named change is made. Tweaks are limited per clone by plan; relay any upgrade link the tool returns.

## Language

Clones are written in the user's brand language automatically. Set `language` only when the user explicitly asks for a different language.

## Launch

`launch_cloned_ad` turns the clone into a PAUSED Meta campaign, ad set and ad. You MUST write the primary text (and optionally a headline) fresh for the user's product; the link is the user's own page. Two-step: show the preview (destination link and copy), get an explicit OK, then call again with the `confirmToken`. `resume_campaign` starts spend.

## Quota

Image clones count against the plan's clone allowance. When a clone comes back LOCKED (blurred, with an unlock link), relay the link. Do not recreate it.
