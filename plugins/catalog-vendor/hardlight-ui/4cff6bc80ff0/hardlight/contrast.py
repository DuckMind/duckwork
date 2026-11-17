"""Opaque sRGB contrast, using unrounded WCAG thresholds."""
import re

_THRESHOLDS = {"text": 4.5, "large_text": 3.0, "ui": 3.0}
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\Z")


def _luminance(color):
    value = color[1:]
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722)))


def check_contrast(pairs):
    """Return JSON-ready results, or an atomic error for unsupported input."""
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 100:
        return {"ok": False, "error": "pairs must be an array of 1..100 color pairs"}
    results = []
    for index, pair in enumerate(pairs):
        if not isinstance(pair, dict):
            return {"ok": False, "error": f"pairs[{index}] must be an object"}
        for key in ("foreground", "background"):
            if not isinstance(pair.get(key), str) or not _HEX.fullmatch(pair[key]):
                return {"ok": False, "error": f"pairs[{index}].{key} must be opaque #RGB or #RRGGBB"}
        role = pair.get("role")
        if not isinstance(role, str) or role not in _THRESHOLDS:
            return {"ok": False, "error": f"pairs[{index}].role must be text, large_text or ui"}
        if "label" in pair and not isinstance(pair["label"], str):
            return {"ok": False, "error": f"pairs[{index}].label must be a string"}
        light, dark = sorted((_luminance(pair["foreground"]), _luminance(pair["background"])), reverse=True)
        ratio = (light + 0.05) / (dark + 0.05)
        item = {"foreground": pair["foreground"], "background": pair["background"], "role": role,
                "ratio": ratio, "threshold": _THRESHOLDS[role],
                "status": "pass" if ratio >= _THRESHOLDS[role] else "fail"}
        if "label" in pair:
            item["label"] = pair["label"]
        results.append(item)
    return {"ok": True, "pairs": results, "coverage": "Opaque sRGB pairs only; role supplied by caller. Not a WCAG conformance audit."}
