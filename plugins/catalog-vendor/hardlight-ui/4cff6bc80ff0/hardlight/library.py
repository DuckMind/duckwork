"""Allowlisted, local-only reference lookup. No caller-selected paths."""
import json
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent
_RESOURCE_ROOT = _PACKAGE_ROOT if (_PACKAGE_ROOT / "data" / "atlas.json").is_file() else _PACKAGE_ROOT.parent
REFERENCE_TOPICS = ("index", "atlas", "style", "workflow", "navigation", "states", "typography", "color", "motion", "review", "systems", "browser", "layout", "platform", "performance")


def get_reference(topic="index", style=None):
    """Read shipped guidance and original style grammars; errors are JSON objects."""
    if not isinstance(topic, str) or topic not in REFERENCE_TOPICS:
        return {"ok": False, "error": "Unknown topic; choose an available topic", "topics": list(REFERENCE_TOPICS)}
    try:
        atlas = json.loads((_RESOURCE_ROOT / "data" / "atlas.json").read_text(encoding="utf-8"))
        styles = atlas["styles"]
        ids = [s["id"] for s in styles]
        if style is not None and (not isinstance(style, str) or style not in ids):
            return {"ok": False, "error": "Unknown exact style ID", "available_styles": ids}
        if topic == "index":
            return {"ok": True, "topic": topic, "topics": list(REFERENCE_TOPICS),
                    "styles": [{k: s[k] for k in ("id", "name", "family", "surfaces")} for s in styles]}
        if topic == "atlas":
            return {"ok": True, "topic": topic, **atlas}
        if topic == "style":
            if style is None:
                return {"ok": False, "error": "topic style requires an exact style ID", "available_styles": ids}
            selected = next(s for s in styles if s["id"] == style)
            return {"ok": True, "topic": topic, "style": selected,
                    "sources": [s for s in atlas["sources"] if s["id"] in selected["source_ids"]]}
        content = (_RESOURCE_ROOT / "references" / f"{topic}.md").read_text(encoding="utf-8")
        if topic == "platform":
            ledger = json.loads((_RESOURCE_ROOT / "data" / "platform-features.json").read_text(encoding="utf-8"))
            return {"ok": True, "topic": topic, "content": content,
                    "schema_version": ledger["schema_version"], "features": ledger["features"]}
        return {"ok": True, "topic": topic, "content": content}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"ok": False, "error": f"Shipped reference data unavailable or invalid; reinstall the complete Hardlight UI distribution ({type(exc).__name__})"}
