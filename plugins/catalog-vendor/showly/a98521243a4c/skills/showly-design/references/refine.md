# Review and refinement

Adapted from Impeccable; see [source record](upstream.md).

Start by identifying what already works. Preserve the existing palette, type,
content and interaction model unless the requested change includes replacing them.
A request to polish is not permission for a redesign.

Walk the visitor's primary path and prioritize:

1. Blocked actions, misleading states and inaccessible controls.
2. Missing recovery, empty, loading or permission states that the path can reach.
3. Unclear hierarchy, broken wrapping and inconsistent shared patterns.
4. Spacing, alignment, icon weight and unnecessary motion.

Tie each finding to a specific element and user consequence. For a review, give
an actionable recommendation and distinguish observed behavior from inference.
Do not manufacture scores, flaws or a fixed quota of findings.

For requested edits, fix the cause at the narrowest useful level: reuse a shared
component or token where it already owns the pattern; avoid creating a new system
for one exception. Verify neighboring surfaces if a shared component changes.

Check typography with real content, long titles, mixed scripts and zoom. Preserve
meaningful distinctions instead of shrinking everything until it fits. Check
contrast, focus, control labels, keyboard access and status information that must
not depend on color alone. Motion should explain a transition and remain
interruptible, with a reduced-motion alternative.

For interface text, name what happened and the next available action. Keep product
terms consistent. Do not replace useful error details with vague reassurance or
invent a cause, completion state, timeline or recovery action. Change claims only
within the user's editing scope and preserve their meaning.

Inspect the whole changed path at narrow and wide widths, not only the hero.
Finish by checking the diff for accidental copy, behavior or branding changes.
