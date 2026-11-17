"""Bounded caller-supplied context and worksheets the host must still author."""

CONTEXT_FIELDS = {
    "audience": "Name the people and situation the interface serves.",
    "tasks": "List concrete jobs and observable successful results.",
    "content": "Identify actual content, objects and missing product facts.",
    "assets": "Inventory available assets, rights and fallbacks.",
    "identity": "Record incumbent tokens, navigation and behaviors to retain.",
    "browsers": "State the browser/device target and fallback expectations.",
    "constraints": "Record performance, accessibility, delivery and operational constraints.",
}
_TEXT_FIELDS = {"audience", "identity", "browsers"}
MAX_CONTEXT_TEXT = 16000
CONTEXT_SCHEMA = {
    "type": "object",
    "description": "Optional supplied facts, not inferred design. At most 16000 characters across all values; omit unknown fields.",
    "additionalProperties": False,
    "properties": {
        key: ({"type": "string", "minLength": 1, "maxLength": 2000, "description": description}
              if key in _TEXT_FIELDS else
              {"type": "array", "minItems": 1, "maxItems": 12, "description": description,
               "items": {"type": "string", "minLength": 1, "maxLength": 1000}})
        for key, description in CONTEXT_FIELDS.items()
    },
}


def validate_context(context):
    """Return an owned copy or raise ValueError; do not coerce or infer facts."""
    if context is None:
        return {}
    if not isinstance(context, dict):
        raise ValueError("context must be an object with allowlisted fields")
    if any(key not in CONTEXT_FIELDS for key in context):
        raise ValueError("context contains unknown fields; choose: " + ", ".join(CONTEXT_FIELDS))
    result, total = {}, 0
    for key, value in context.items():
        if key in _TEXT_FIELDS:
            values, limit = [value], 2000
        else:
            if not isinstance(value, list) or not 1 <= len(value) <= 12:
                raise ValueError(f"context.{key} must be an array of 1..12 nonblank strings")
            values, limit = value, 1000
        if any(not isinstance(item, str) or not item.strip() or len(item) > limit for item in values):
            raise ValueError(f"context.{key} values must be nonblank strings of at most {limit} characters")
        total += sum(len(item) for item in values)
        if total > MAX_CONTEXT_TEXT:
            raise ValueError("context text must not exceed 16000 characters in total")
        result[key] = value if key in _TEXT_FIELDS else list(value)
    return result


def design_contract(preserve):
    """An unanswered worksheet, explicitly separated from generated decisions."""
    return {
        "status": "awaiting_host_authorship",
        "instruction": "Complete these decisions using the supplied facts and actual project. Reference candidates are not original concepts or a completed design.",
        "decisions": [{"id": key, "status": "not_authored", "prompt": prompt} for key, prompt in (
            ("thesis", "Name the subject-specific idea, the primary user job and the real object, content or proof artifact that makes the idea visible."),
            ("structure", "Preserve the incumbent composition and navigation; explain the smallest compatible change and its tradeoff."
             if preserve else "Compare three concepts that differ in at least two of composition, sequence, density, assets or interaction. State each task tradeoff and select one."),
            ("invariants", "Define alignment, hierarchy, type roles, semantic color and spacing rules that remain coherent beyond the opening screen."),
            ("signature", "Choose one recognizable interaction or material gesture serving a real job; specify its immediate, keyboard and reduced-motion equivalents."),
            ("mobile", "Describe the narrow-screen transformation: content priority, grouping, navigation and artwork. Include long copy, text resizing and relevant writing directions."),
            ("budget", "Choose browser support, asset/font/effect budgets and baseline fallbacks. Separate proposed targets from measured evidence."),
            ("critique", "Try an unrelated subject name: identify which decisions would have to change. Revise generic decisions; record a real risk and the observation that would challenge it."),
        )],
    }


def verification_matrix():
    return [{"check": check, "status": "not_run", "evidence_needed": evidence} for check, evidence in (
        ("tasks", "Primary/recovery paths, direct URLs, Back/Forward and applicable state transitions."),
        ("responsive", "Initial and engaged wide, narrow and intermediate views; 320 CSS pixel reflow, long copy and text resizing."),
        ("input", "Keyboard order, visible/unobscured focus, touch alternatives and relevant target-size exceptions."),
        ("preferences", "Reduced motion, forced colors, supported themes and fallback fonts; preserve information and controls."),
        ("platform", "Chosen capabilities detected in the target browsers and exercised with enhancements unavailable."),
        ("paint", "Actual supported color pairs and roles; unsupported syntax or composite paint stays unknown."),
        ("performance", "Asset bytes and reproducible lab observations with device/build context; field metrics require real visits."),
        ("composition", "Human review against the authored premise and real content; no numerical beauty score."),
    )]
