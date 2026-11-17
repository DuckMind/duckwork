"""Deterministic reference-derived direction packets, not generated artwork."""
from .library import get_reference
from .brief import CONTEXT_FIELDS, design_contract, validate_context, verification_matrix

_SURFACES = ("marketing", "product", "reading", "commerce", "portfolio")
_AUTHORITIES = ("refinement", "extension", "redesign", "greenfield")
_DEFAULTS = {
    "marketing": ("kinetic-poster", "organic-humanist", "swiss-editorial"),
    "product": ("systemic-product", "data-atelier", "wayfinding"),
    "reading": ("swiss-editorial", "editorial-luxe", "quiet-craft"),
    "commerce": ("editorial-luxe", "organic-humanist", "expressive-material"),
    "portfolio": ("cinematic-gallery", "bauhaus-play", "spatial-technical"),
}


def make_direction(brief, surface="product", authority="greenfield", styles=None, context=None):
    """Preserve input intent and return three alternatives unless IDs were explicit."""
    if not isinstance(brief, str) or not brief.strip():
        return {"ok": False, "error": "brief must be a nonempty string"}
    if not isinstance(surface, str) or surface not in _SURFACES:
        return {"ok": False, "error": "surface must be one of: " + ", ".join(_SURFACES)}
    if not isinstance(authority, str) or authority not in _AUTHORITIES:
        return {"ok": False, "error": "authority must be one of: " + ", ".join(_AUTHORITIES)}
    if styles is not None and (not isinstance(styles, list) or not 1 <= len(styles) <= 3 or any(not isinstance(s, str) for s in styles) or len(set(styles)) != len(styles)):
        return {"ok": False, "error": "styles must be an array of 1..3 distinct exact atlas IDs"}
    try:
        supplied = validate_context(context)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    candidates = []
    for style in (styles if styles is not None else _DEFAULTS[surface]):
        reference = get_reference("style", style)
        if not reference["ok"]:
            return reference
        candidates.append({**reference["style"], "sources": reference["sources"],
                           "adaptation": "Reference grammar only: develop a thesis and real asset plan for the exact brief; do not copy a source site."})
    preserve = authority in ("refinement", "extension")
    gaps = [f"{key}: {prompt}" for key, prompt in CONTEXT_FIELDS.items() if key not in supplied]
    if context is None:
        # Preserve the original guidance for callers that have not adopted context.
        gaps = (["Existing navigation, tokens, brand assets and user-tested behavior were not supplied; do not infer them."]
                if preserve else ["Audience, primary jobs, content inventory and available asset rights require confirmation."])
    return {
        "ok": True, "brief": brief, "surface": surface, "authority": authority,
        "preserve_incumbent": preserve,
        "authority_guidance": "Preserve incumbent tokens, identity, navigation and working behavior; propose compatible changes only." if preserve else "Confirm retained constraints before adopting a new direction.",
        "missing_context": gaps,
        "context": supplied,
        "design_contract": design_contract(preserve),
        "craft_references": ["layout", "platform", "typography", "color", "motion", "performance"],
        "verification_matrix": verification_matrix(),
        "candidates": candidates,
        "ia_questions": ["Who is using this surface and what job must they finish?", "Which destinations and direct links support each primary task?", "What labels, current-location cues and Back/Forward behavior are needed?", "How does mobile navigation preserve the same destinations?", "How do search, filters, permissions and recovery persist or reset?"],
        "state_matrix": [{"state": s, "requirement": r} for s, r in (
            ("default", "Show meaningful content and primary task."),
            ("loading", "Explain progress without hiding current location."),
            ("empty", "Explain why and offer a real next action."),
            ("error", "Preserve input and provide actionable recovery."),
            ("success", "Confirm the action and its next destination."),
            ("permission", "Explain unavailable actions and allowed alternatives."),
            ("keyboard", "Visible focus, logical order and no traps."))],
        "asset_plan": "Inventory real owned/licensed imagery, diagrams and content; use labeled placeholders until assets exist. Never invent testimonials, metrics or evidence.",
        "signature_plan": "Choose one coherent structural signature from a candidate and connect it to the primary user job, not decoration alone.",
        "verification_plan": ["Map destinations and primary task paths before styling.", "Inspect incumbent tokens before changes.", "Test direct links, Back/Forward, keyboard and mobile routes.", "Verify loading, empty, error, permission and success states.", "Measure explicit contrast roles and reduced-motion behavior.", "Inspect wide and narrow screenshots; automated checks do not certify beauty, usability or WCAG conformance."],
        "limitations": ["Deterministic reference selection, not scientific taste ranking or generated original artwork.", "Explicit style choices are preserved, including those outside usual surface recommendations."],
    }
