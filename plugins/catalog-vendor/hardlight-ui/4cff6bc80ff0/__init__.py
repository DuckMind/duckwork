"""Native Duckwork entrypoint. Registration is static; all runtime tools are stateless."""
import json
from collections.abc import Mapping
from pathlib import Path

if __package__:
    from .hardlight import __version__
    from .hardlight.contrast import check_contrast
    from .hardlight.direction import make_direction
    from .hardlight.inspection import inspect_project
    from .hardlight.library import REFERENCE_TOPICS, get_reference
    from .hardlight.brief import CONTEXT_SCHEMA
else:  # Direct source tooling (e.g. pytest's root __init__ collection).
    from hardlight import __version__
    from hardlight.contrast import check_contrast
    from hardlight.direction import make_direction
    from hardlight.inspection import inspect_project
    from hardlight.library import REFERENCE_TOPICS, get_reference
    from hardlight.brief import CONTEXT_SCHEMA


def _navigation(**args):
    from .hardlight.navigation import analyze_navigation
    return analyze_navigation(**args)


def _handler(function):
    def handle(args, **kwargs):
        if not isinstance(args, Mapping):
            return json.dumps({"ok": False, "error": "Tool arguments must be an object"})
        try:
            result = function(**dict(args))
        except (TypeError, ValueError, OSError, ImportError) as exc:
            result = {"ok": False, "error": f"Invalid arguments or unavailable local resource: {exc}"}
        return json.dumps(result, ensure_ascii=False, allow_nan=False)
    return handle


def _schema(name, description, properties, required=()):
    return {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": list(required), "additionalProperties": False}}


_TOOLS = (
    ("hardlight_reference", get_reference, "Read original local design grammars or allowlisted workflow references.", {
        "topic": {"type": "string", "enum": list(REFERENCE_TOPICS), "default": "index"},
        "style": {"type": "string", "description": "Exact atlas ID; required for topic style."}}, ()),
    ("hardlight_direction", make_direction, "Build deterministic reference-derived direction alternatives; preserve incumbent identity in refinement or extension.", {
        "brief": {"type": "string", "minLength": 1},
        "surface": {"type": "string", "enum": ["marketing", "product", "reading", "commerce", "portfolio"], "default": "product"},
        "authority": {"type": "string", "enum": ["refinement", "extension", "redesign", "greenfield"], "default": "greenfield"},
        "styles": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3, "uniqueItems": True},
        "context": CONTEXT_SCHEMA}, ("brief",)),
    ("hardlight_inspect", inspect_project, "Read-only bounded frontend inspection with token provenance and advisory findings. Never execute project code.", {
        "root": {"type": "string", "description": "Existing local directory; no symlink components."},
        "max_files": {"type": "integer", "minimum": 1, "maximum": 500, "default": 120}}, ("root",)),
    ("hardlight_contrast", check_contrast, "Measure opaque sRGB contrast using explicit text, large_text or ui roles; not a conformance audit.", {
        "pairs": {"type": "array", "minItems": 1, "maxItems": 100,
                  "items": {"type": "object", "properties": {
                      "foreground": {"type": "string", "pattern": "^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"},
                      "background": {"type": "string", "pattern": "^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"},
                      "role": {"type": "string", "enum": ["text", "large_text", "ui"]},
                      "label": {"type": "string"}}, "required": ["foreground", "background", "role"], "additionalProperties": False}}}, ("pairs",)),
    ("hardlight_navigation", _navigation, "Analyze explicit destinations and task paths for structural navigation defects; not usability certification.", {
        "pages": {"type": "array", "minItems": 1, "maxItems": 300, "items": {"type": "object", "properties": {
            "id": {"type": "string"}, "label": {"type": "string"},
            "links": {"type": "array", "items": {"type": "object", "properties": {"to": {"type": "string"}, "label": {"type": "string"}}, "required": ["to", "label"], "additionalProperties": False}}}, "required": ["id", "label", "links"], "additionalProperties": False}},
        "tasks": {"type": "array", "maxItems": 100, "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "start": {"type": "string"}, "goal": {"type": "string"}, "max_steps": {"type": "integer", "minimum": 0}}, "required": ["name", "start", "goal"], "additionalProperties": False}},
        "home": {"type": "string"}}, ("pages", "tasks")),
)


def _command(raw_args):
    action = raw_args.strip() or "help"
    if action == "version":
        return "Hardlight UI " + __version__
    if action == "styles":
        return json.dumps(get_reference(), ensure_ascii=False)
    return "Hardlight UI: /hardlight help | styles | version. Use hardlight_reference, hardlight_direction, hardlight_inspect, hardlight_contrast and hardlight_navigation; load hardlight-ui:frontend-design for the workflow."


def register(ctx):
    """Require native surfaces by behavior, not an invented host version number."""
    missing = [name for name in ("register_tool", "register_skill", "register_command") if not callable(getattr(ctx, name, None))]
    if missing:
        raise RuntimeError("Hardlight UI requires callable Duckwork plugin APIs: " + ", ".join(missing) + ". Update Duckwork to a release providing these native APIs; no hooks or core patches are needed.")
    skill = Path(__file__).resolve().parent / "skills" / "frontend-design" / "SKILL.md"
    if not skill.is_file():
        raise RuntimeError("Hardlight UI distribution is incomplete: missing skills/frontend-design/SKILL.md. Reinstall the complete plugin archive.")
    for name, function, description, properties, required in _TOOLS:
        ctx.register_tool(name=name, toolset="hardlight", schema=_schema(name, description, properties, required), handler=_handler(function), description=description, emoji="◈", requires_env=[], is_async=False, override=False)
    ctx.register_skill("frontend-design", skill, description="Design distinctive, navigable frontends with original reference grammars and explicit verification.")
    ctx.register_command("hardlight", _command, description="Hardlight UI help, style IDs and version", args_hint="help|styles|version", argument_mode="text")
    prompt = getattr(ctx, "register_system_prompt_section", None)
    if callable(prompt):
        prompt("hardlight-ui.discovery", "Hardlight UI provides stateless frontend design references, direction packets, bounded project inspection, contrast and navigation checks. For frontend work, load hardlight-ui:frontend-design and use hardlight_reference for on-demand guidance. Automated findings are partial advisory evidence, not artistic or usability certification.", position="after_memory", max_chars=600)
