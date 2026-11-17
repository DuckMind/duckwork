---
name: showly-design
description: Create or refine website layouts, typography, spacing and interactions. Use for building a new web interface, visual design review, or requests to make an existing page more polished or less generic. Not for hosting-only requests, prose-only editing, or backend changes.
license: Apache-2.0
---

# Design websites with Showly

Use the user's brief and the site's own visual identity to guide the design.
This is portable design guidance; it requires no Impeccable installation, engine,
hooks or downloads. Use the editing and browser tools available in the host.

## Choose the scope

Read the target files and available brand assets, design tokens, shared components
and reference screenshots before editing. For an existing hosted site, use the
available Showly tools to read its context and selected files first. Missing
DESIGN.md does not mean the site has no established design.

- For a new page or an explicitly requested redesign, read
  [new-page.md](references/new-page.md).
- For polishing, reviewing or fixing an existing interface, read
  [refine.md](references/refine.md). A review request returns findings; it does
  not implicitly authorize a rewrite.

For new pages and redesigns, make the chosen brand character visible in layout,
typography and imagery; “polished” does not always mean quiet or minimal.

Infer the audience, primary action and visual direction from the brief and
existing work. Ask only about a missing choice that would materially change the
result. A small spacing fix does not need a branding interview or a design document.

## Preserve the user's intent

Keep the project's framework and shared primitives. Preserve existing identity,
content and behavior during refinement; change them only within the requested
scope. A customer's website uses its own brand, not Showly's product palette.
Render third-party logos in their original colors without tint, opacity or filters.

Avoid generic composition when it obscures the content: repeated equal cards,
empty slogans, decorative gradients and motion without a purpose. These are
contextual warning signs, not bans on a color, font, layout or aesthetic the user
chose. Do not invent customer quotes, statistics, product capabilities or claims
of success to make the page look finished.

## Verify the result

Inspect the rendered page when a browser is available. Check desktop and mobile,
including 390×844 and about 320px wide, for clipping, hierarchy, readable text and
reachable primary actions. Use content-driven wrapping; do not hide essential
actions to make a screenshot fit. Use dynamic viewport units for full-height web
surfaces, safe-area insets where needed, 44px touch targets and at least 16px form
input text on mobile. Keep keyboard focus visible and honor reduced motion.

Build, inspect, fix the concrete defects in one batch, then confirm the fixes.
Stop when the requested result works; further passes need a new finding. If the
page cannot run or browser tools are unavailable, inspect the source and state
which visual or interaction checks remain unverified. Never call source inspection
a visual test or claim accessibility compliance from a screenshot.

Deliver the requested files or review, with a short account of meaningful changes
and checks. Design work alone does not authorize upload or publication. If the
user requested a Showly share link, continue through the available hosting workflow;
keep its access and publish-confirmation boundaries intact. Do not block local
design work when hosting tools are unavailable.

For source versions, adaptations and licensing, see
[upstream.md](references/upstream.md) and
[THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt).
