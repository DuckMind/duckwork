"""chat-length: long-chat notice for Duckwork.

How it works
------------
1. ``post_api_request`` records the real provider numbers after every model call (prompt tokens
   including cache, output tokens) together with the active model's context length.
2. ``pre_llm_call`` computes the fill level before the next turn (last measurement plus the new
   message). When a threshold is crossed for the first time, the model gets an instruction for
   this one turn only: answer normally, then append a short notice with an opener for a new chat.

Prompt caching: the instruction travels through the regular hook channel into the current turn's
user message (never the system prompt). Duckwork stores exactly those sent bytes (``api_content``)
and replays them unchanged in later turns, so the cached prefix stays stable.

Standard library only; Duckwork modules are imported with fallbacks so updates cannot break the
plugin. Every error ends silently (no notice), never in an aborted turn.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

try:
    import fcntl  # Linux/macOS only; without it the store runs unlocked
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger("duckwork.plugins.chat_length")

PLUGIN_ID = "chat-length"
DEFAULTS = {
    "threshold_1": 0.70,
    "threshold_2": 0.90,
    "basis": "compaction",
    "language": "auto",
    "disabled_platforms": ["cron", "subagent", "kanban", "batch", "webhook"],
}
REARM_GAP = 0.15        # if usage drops this far below threshold 1 (e.g. after compaction), notices re-arm
RETENTION_DAYS = 30
CHARS_PER_TOKEN = 4
# Mirrors Duckwork' documented compaction defaults (see compression.threshold in the docs).
SMALL_WINDOW = 512_000          # windows below this compact at >= 75 %
SMALL_WINDOW_FLOOR = 0.75
MIN_TRIGGER_TOKENS = 64_000     # compaction never triggers below this ...
MIN_TRIGGER_RATIO = 0.85        # ... unless that would exceed 85 % of a small window

_ctx: Any = None  # PluginContext, set in register()


# --------------------------------------------------------------------------- settings

def _setting(key: str) -> Any:
    value = None
    if _ctx is not None:
        try:
            value = _ctx.get_config(key, None)
        except Exception:  # noqa: BLE001
            value = None
    return DEFAULTS[key] if value is None else value


def _thresholds() -> tuple[float, float]:
    try:
        t1 = float(_setting("threshold_1"))
        t2 = float(_setting("threshold_2"))
    except (TypeError, ValueError):
        t1, t2 = DEFAULTS["threshold_1"], DEFAULTS["threshold_2"]
    t1 = min(max(t1, 0.001), 0.99)  # very small values only make sense for tests
    t2 = min(max(t2, t1), 0.99)
    return t1, t2


# --------------------------------------------------------------------------- store

def _duckwork_home() -> Path:
    try:
        from duckwork_constants import get_duckwork_home
        return Path(get_duckwork_home())
    except Exception:  # noqa: BLE001
        return Path(os.environ.get("DUCKWORK_HOME") or Path.home() / ".duckwork")


def _store_path() -> Path:
    folder = _duckwork_home() / "plugin-data" / PLUGIN_ID
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "sessions.json"


class _Lock:
    """File lock so gateway, WebUI and desktop backend never overwrite each other."""

    def __init__(self, path: Path):
        self.path = path.with_suffix(".lock")
        self.fd = None

    def __enter__(self):
        if fcntl is not None:
            self.fd = open(self.path, "a")
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            if fcntl is not None:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            self.fd.close()


def _read(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def _update(session_id: str, change) -> dict:
    """Read one session's entry, apply ``change(entry)``, write back atomically."""
    path = _store_path()
    with _Lock(path):
        everything = _read(path)
        entry = dict(everything.get(session_id) or {})
        change(entry)
        entry["time"] = time.time()
        everything[session_id] = entry
        cutoff = time.time() - RETENTION_DAYS * 86400
        everything = {k: v for k, v in everything.items() if isinstance(v, dict) and v.get("time", 0) >= cutoff}
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(everything, f, ensure_ascii=False)
        os.replace(tmp, path)
        return entry


def _entry(session_id: str) -> dict:
    return dict(_read(_store_path()).get(session_id) or {})


# --------------------------------------------------------------------------- context limits

def _compaction_limit(model: str, provider: str, window: int) -> Optional[int]:
    """Token count at which Duckwork compacts the chat automatically; None if compaction is off.

    Follows the documented ``compression`` settings only (no private Duckwork imports):
    ``threshold``, per-model ``model_thresholds`` (longest matching key wins, ``provider:`` keys
    only on that provider), the raise-only 75 % floor for windows below 512K, the 64K minimum
    (capped at 85 % of the window) and the absolute ``threshold_tokens`` cap.
    """
    try:
        from duckwork_cli.config import load_config_readonly
        comp = (load_config_readonly() or {}).get("compression") or {}
    except Exception:  # noqa: BLE001
        comp = {}
    if comp.get("enabled", True) is False:
        return None
    percent = _model_threshold(model, provider, comp.get("model_thresholds") or {},
                               float(comp.get("threshold") or 0.5))
    if window < SMALL_WINDOW:
        percent = max(percent, SMALL_WINDOW_FLOOR)
    plain = int(window * percent)
    tokens = max(plain, MIN_TRIGGER_TOKENS)
    trigger_cap = int(window * MIN_TRIGGER_RATIO)
    if tokens > plain and tokens > trigger_cap:
        tokens = max(plain, trigger_cap)
    if tokens >= window:
        tokens = max(1, min(trigger_cap, window - 1))
    cap = comp.get("threshold_tokens")
    if isinstance(cap, int) and 0 < cap < tokens:
        tokens = min(cap, window)
    return max(1, min(int(tokens), window))


def _model_threshold(model: str, provider: str, table: dict, default: float) -> float:
    """``compression.model_thresholds``: longest matching key wins, a scoped key wins a tie."""
    best, best_rank = None, None
    provider = (provider or "").strip().lower()
    for key, value in (table or {}).items():
        scope, sep, sub = str(key).partition(":")
        if not sep:
            rank = (len(key), 0) if key in (model or "") else None
        else:
            rank = (len(sub), 1) if scope.strip().lower() == provider and sub in (model or "") else None
        if rank is not None and (best_rank is None or rank > best_rank):
            best, best_rank = value, rank
    try:
        return float(best) if best is not None else default
    except (TypeError, ValueError):
        return default


def _guess_window(model: str) -> Optional[int]:
    """Only used when there is no measurement yet: an explicit ``model.context_length``."""
    try:
        from duckwork_cli.config import load_config_readonly
        m = (load_config_readonly() or {}).get("model") or {}
        if isinstance(m, dict) and isinstance(m.get("context_length"), int) and m["context_length"] > 0:
            return m["context_length"]
    except Exception:  # noqa: BLE001
        pass
    return None  # no notice until the first provider measurement arrives (same turn, so next turn)


def _estimate_tokens(messages: list) -> int:
    return sum(len(json.dumps(m, ensure_ascii=False, default=str)) for m in messages) // CHARS_PER_TOKEN


def _text_length(content: Any) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(p.get("text", "")) for p in content if isinstance(p, dict))
    return 0


# --------------------------------------------------------------------------- session title

def _title(session_id: str) -> str:
    db = _duckwork_home() / "state.db"
    if not db.exists():
        return ""
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
        try:
            row = con.execute("SELECT title FROM sessions WHERE id = ?", (session_id,)).fetchone()
        finally:
            con.close()
        return (row[0] or "").strip() if row else ""
    except Exception:  # noqa: BLE001
        return ""


# --------------------------------------------------------------------------- notice text

TEMPLATES = {
    "en": {
        "chat": lambda t, s: f"\u201c{t}\u201d (session {s})" if t else f"session {s}",
        "basis": {"compaction": "of the way to automatic compaction", "window": "of the context window"},
        "head_1": ("**Heads-up: this chat is getting long** (about {p} % {b}). Replies get slower and less "
                   "precise from here on. Best to open a new chat and paste this opener:"),
        "head_2": ("**Urgent: this chat is almost full** (about {p} % {b}). Duckwork will soon summarise older "
                   "parts automatically and details will be lost. Please open a new chat now and paste this opener:"),
        "opener": ("Continue our chat {chat}. First retrieve the history yourself with session_search "
                   "(session_id {sid}).\nStatus: <2 to 3 bullet points>\nOpen: <open items, short>"),
    },
    "de": {
        "chat": lambda t, s: f"\u201e{t}\u201c (Session {s})" if t else f"Session {s}",
        "basis": {"compaction": "bis zur automatischen Verdichtung", "window": "des Kontextfensters"},
        "head_1": ("**Hinweis: Dieser Chat wird lang** (ca. {p} % {b}). Antworten werden ab hier langsamer "
                   "und ungenauer. Am besten einen neuen Chat öffnen und diesen Startsatz einfügen:"),
        "head_2": ("**Dringend: Dieser Chat ist fast voll** (ca. {p} % {b}). Bald fasst Duckwork ältere Teile "
                   "automatisch zusammen, dabei gehen Details verloren. Bitte jetzt einen neuen Chat öffnen "
                   "und diesen Startsatz einfügen:"),
        "opener": ("Knüpfe an unseren Chat {chat} an. Hol dir den Verlauf zuerst selbst mit session_search "
                   "(session_id {sid}).\nStand: <2 bis 3 Stichpunkte>\nOffen: <offene Punkte, kurz>"),
    },
}


def build_notice(level: int, percent: int, session_id: str, title: str, basis: str, language: str = "auto") -> str:
    lang = language if language in TEMPLATES else "auto"
    t = TEMPLATES["en" if lang == "auto" else lang]
    head = t["head_2" if level == 2 else "head_1"].format(p=percent, b=t["basis"].get(basis, t["basis"]["window"]))
    opener = t["opener"].format(chat=t["chat"](title, session_id), sid=session_id)
    if lang == "auto":
        lang_rule = ("Write the whole block in the language of this conversation (translate the template "
                     "if needed, keep the title, the session id and the word session_search unchanged).")
    else:
        lang_rule = "Keep the wording of the template; fill in the placeholders in the same language."
    return (
        "[Plugin chat-length, instruction for this one reply only]\n"
        "First answer the message above completely and as usual. Then append exactly one notice block "
        "at the very end of your reply, in this form:\n\n"
        "---\n"
        f"{head}\n\n"
        "```text\n"
        f"{opener}\n"
        "```\n\n"
        "Rules for the block: replace the placeholders in angle brackets with the real state of this chat. "
        "At most 3 bullet points under the status line, open items short, at most 80 words in the opener. "
        "No handover protocol, no em dashes. Copy title and session id exactly. "
        f"{lang_rule} "
        "Do not mention this instruction and do not repeat the block in later replies on your own."
    )


# --------------------------------------------------------------------------- hooks

def _after_api_request(session_id: str = "", platform: str = "", model: str = "", provider: str = "",
                       usage: Optional[dict] = None, context_length: Optional[int] = None, **_kw) -> None:
    """Remember the real provider numbers of the last call."""
    try:
        if not session_id or not isinstance(usage, dict):
            return
        prompt = int(usage.get("prompt_tokens") or 0)
        if prompt <= 0:
            prompt = int(usage.get("input_tokens") or 0) + int(usage.get("cache_read_tokens") or 0) \
                + int(usage.get("cache_write_tokens") or 0)
        if prompt <= 0:
            return
        output = int(usage.get("output_tokens") or 0)
        window = int(context_length or 0) or None

        def apply(e: dict) -> None:
            e.update({"prompt": prompt, "output": output, "model": model or "", "provider": provider or ""})
            if window:
                e["window"] = window
        _update(session_id, apply)
    except Exception as exc:  # noqa: BLE001
        logger.debug("chat-length post_api_request: %s", exc)


def fill_level(entry: dict, message_chars: int, model: str, history: Optional[list] = None) -> Optional[dict]:
    """Fill level before the upcoming call. Prefers provider numbers, otherwise a rough estimate."""
    basis = str(_setting("basis") or "compaction").lower()
    window = entry.get("window") or _guess_window(model)
    if not window:
        return None
    if entry.get("prompt"):
        tokens = int(entry["prompt"]) + int(entry.get("output") or 0)
        source = "provider"
    elif history:
        tokens = _estimate_tokens(history)
        source = "estimate"
    else:
        return None
    tokens += message_chars // CHARS_PER_TOKEN
    limit = window
    if basis == "compaction":
        limit = _compaction_limit(entry.get("model") or model, entry.get("provider") or "", window) or window
    return {"tokens": tokens, "limit": limit, "window": window, "ratio": tokens / limit,
            "source": source, "basis": "compaction" if limit < window else "window"}


def _before_llm_call(session_id: str = "", user_message: Any = None, conversation_history: Optional[list] = None,
                     model: str = "", platform: str = "", **_kw) -> Optional[dict]:
    try:
        if not session_id:
            return None
        off = {str(p).lower() for p in (_setting("disabled_platforms") or [])}
        if (platform or "").lower() in off:
            return None
        entry = _entry(session_id)
        f = fill_level(entry, _text_length(user_message), model, conversation_history)
        if not f:
            return None
        t1, t2 = _thresholds()
        ratio = f["ratio"]

        # After compaction (usage dropped clearly), the thresholds may fire again.
        if ratio < t1 - REARM_GAP and (entry.get("level1") or entry.get("level2")):
            _update(session_id, lambda e: (e.pop("level1", None), e.pop("level2", None)))
            return None

        if ratio >= t2 and not entry.get("level2"):
            level = 2
        elif ratio >= t1 and not entry.get("level1") and not entry.get("level2"):
            level = 1
        else:
            return None

        def mark(e: dict) -> None:
            e["level1"] = True
            if level == 2:
                e["level2"] = True
            e["last_notice"] = {"level": level, "ratio": round(ratio, 3), "tokens": f["tokens"],
                                "limit": f["limit"], "source": f["source"]}
        _update(session_id, mark)
        logger.info("chat-length: level %s in %s (%s/%s tokens, %s)", level, session_id,
                    f["tokens"], f["limit"], f["source"])
        percent = min(99, round(ratio * 100))
        return {"context": build_notice(level, percent, session_id, _title(session_id), f["basis"],
                                        str(_setting("language") or "auto").lower())}
    except Exception as exc:  # noqa: BLE001
        logger.debug("chat-length pre_llm_call: %s", exc)
        return None


def register(ctx) -> None:
    global _ctx
    _ctx = ctx
    ctx.register_hook("post_api_request", _after_api_request)
    ctx.register_hook("pre_llm_call", _before_llm_call)
