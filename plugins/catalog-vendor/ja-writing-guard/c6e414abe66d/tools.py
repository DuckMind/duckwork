"""Tool handler and slash command. Handlers return JSON strings and never raise."""

from __future__ import annotations

import json

from .detector import check
from .surfaces import SURFACE_LABELS, SURFACES


def ja_writing_check(args: dict, **kwargs) -> str:
    text = (args or {}).get("text") or ""
    if not text.strip():
        return json.dumps({"error": "text is empty"}, ensure_ascii=False)
    try:
        cap = int(args.get("max_findings") or 30)
        report = check(text, args.get("surface") or None)
        return json.dumps(report.to_dict(max_findings=max(1, min(cap, 200))), ensure_ascii=False)
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    except Exception as exc:  # pragma: no cover - defensive
        return json.dumps({"error": f"check failed: {type(exc).__name__}"}, ensure_ascii=False)


def format_report(data: dict, limit: int = 10) -> str:
    lines = [data.get("summary", "")]
    for f in data.get("findings", [])[:limit]:
        mark = "" if f.get("counted", True) else "（点数外）"
        lines.append(f"- {f['line']}行{f['col']}字目 {f['label']}{mark}: {f['excerpt']}")
        lines.append(f"  直し方: {f['hint']}")
    more = data.get("findings_total", 0) - min(limit, len(data.get("findings", [])))
    if more > 0:
        lines.append(f"（ほか {more} 件）")
    return "\n".join(lines)


USAGE = (
    "Usage: /ja-check [surface] <text>  Surfaces: "
    + " / ".join(f"{k} ({v})" for k, v in SURFACE_LABELS.items())
    + ". Omit the text to show the last answer's report.\n"
    "使い方: /ja-check [場面] <文>  場面は "
    + " / ".join(f"{k}（{v}）" for k, v in SURFACE_LABELS.items())
    + "。文を省くと、直前の返答の検査結果を表示します。"
)


def make_command(guard):
    def handler(raw_args: str = "") -> str:
        raw = (raw_args or "").strip()
        if raw in ("help", "-h", "--help"):
            return USAGE
        if not raw:
            last = guard.recall()
            if not last:
                return (
                    "No checked answer on this screen yet (on Telegram and other gateways, "
                    "the last report is not kept so other people's answers stay private).\n"
                    "この画面ではまだ検査した返答がありません（Telegram などのゲートウェイでは、"
                    "他の人の返答が見えないよう直前の結果を残しません）。\n" + USAGE
                )
            out = [f"直前の返答（モード: {last.get('mode')}）", format_report(last["report"])]
            rw = last.get("rewrite")
            if rw:
                out.append(f"書き直し: {rw['reason']}（{rw['score_before']} → {rw['score_after']}）")
                if rw.get("diff"):
                    out.append("変わった行:")
                    out.extend(line for line in rw["diff"] if line[:1] in "+-" and line[:3] not in ("+++", "---"))
            return "\n".join(out)
        surface = None
        head, _, rest = raw.partition(" ")
        if head in SURFACES and rest.strip():
            surface, raw = head, rest.strip()
        try:
            return format_report(check(raw, surface).to_dict())
        except ValueError as exc:
            return str(exc)

    return handler
