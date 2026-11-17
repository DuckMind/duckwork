"""Backend routes for the meeting-overlay desktop pane.

Mounted under /api/plugins/meeting-overlay/ by the gateway. Reads/writes the
transcript + answer files the meeting-mode daemon owns, controls the listen
daemon (launchd), and fires the answer engine. Runs inside the gateway process.

Single source of truth for settings is settings.json next to the transcript
files — the pane reads it, every toggle writes it, and answer.py + the Lua
menu bar mirror read the same file, so no value drifts between surfaces.
"""
from datetime import datetime
from pathlib import Path
from time import time
import json
import os
import subprocess

from fastapi import APIRouter

router = APIRouter()

DIR = Path.home() / ".duckwork" / "meeting-transcript"
ROLLING = DIR / "rolling.txt"
FULL = DIR / "full.txt"
ANSWER = DIR / "answer.txt"
DECK = DIR / "answers.json"
REQUEST = DIR / "request.txt"
SETTINGS = DIR / "settings.json"

ANSWER_PY = None  # set after _scripts_dir() is defined
PY = Path.home() / ".duckwork" / "duckwork-agent" / "venv" / "bin" / "python"


def _scripts_dir() -> Path:
    """Return the scripts reviewed and pinned with this plugin.

    A catalog SHA only constrains code that is loaded from this tree.  Resolving
    a same-named skill from ``~/.duckwork/skills`` would silently replace reviewed
    daemon code with mutable, unrelated bytes, so it is deliberately forbidden.
    """
    return Path(__file__).resolve().parent.parent / "scripts"


ANSWER_PY = _scripts_dir() / "answer.py"
LISTEN_PY = _scripts_dir() / "listen.py"

LISTEN_LABEL = "com.oz.meeting-listener"
LISTEN_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LISTEN_LABEL}.plist"

_DEFAULTS = {
    "listen": False,
    "mode": "both",          # both | mic | blackhole
    "model": "host",         # host (Duckwork system default) | local (ollama-qwen)
    "recap_model": "host",   # recap export model; hosted default
    "auto_recap": False,
    "auto_local": False,     # set by answer.py when host fell back to local
    "hidden_records": [],    # vault-relative rel paths the user soft-hid (restorable)
    "auto_assist": False,    # record mode on/off (derived: assist_mode != "off")
    "assist_mode": "off",    # WHICH question auto-chunks: off|what|followup|research
    "chunk_sec": 30,         # auto-assist chunk interval (15–60s), scrobbler-set
}

_VALID_ACTIONS = {"what", "followup", "recap", "research", "save", "watch"}
# model = 'off' means NO model engaged: transcription flows but the answer
# engine is disengaged (no cards). host = Duckwork default, local = ollama qwen.
_VALID_MODELS = {"host", "local", "glm", "qwen", "off"}
# four capture sources. "phone" = the phone streams its own mic (via the PWA's
# /ws/audio path), the other three = the desktop daemon captures. One source at
# a time, so there is no phone+desktop merge/echo.
_VALID_MODES = {"phone", "blackhole", "mic", "both"}


def _read_settings() -> dict:
    s = dict(_DEFAULTS)
    try:
        if SETTINGS.exists():
            loaded = json.loads(SETTINGS.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for k in _DEFAULTS:
                    if k in loaded:
                        s[k] = loaded[k]
    except (OSError, ValueError):
        pass
    return s


def _write_settings(s: dict) -> dict:
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(s, indent=2), encoding="utf-8")
    os.replace(tmp, SETTINGS)
    return s


def _tail(path: Path, n: int = 40) -> list:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.strip().splitlines()[-n:] if text.strip() else []


def _age(path: Path):
    if not path.exists():
        return None
    return round(time() - path.stat().st_mtime, 1)


def _daemon_alive() -> bool:
    try:
        out = subprocess.run(
            ["pgrep", "-f", str(LISTEN_PY)],
            capture_output=True, text=True, timeout=2,
        )
        return out.returncode == 0
    except Exception:
        return False


def _uid() -> str:
    try:
        return subprocess.run(
            ["id", "-u"], capture_output=True, text=True, timeout=2
        ).stdout.strip()
    except Exception:
        return ""


def _write_listen_plist(mode: str) -> None:
    """Rewrite MEETING_INPUT in the launchd plist (preserving everything else the
    Lua menu wrote is not possible — we own the plist shape here)."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>\n'
        f"  <key>Label</key><string>{LISTEN_LABEL}</string>\n"
        "  <key>ProgramArguments</key><array>\n"
        f"    <string>{PY}</string>\n"
        f"    <string>{LISTEN_PY}</string>\n"
        "  </array>\n"
        "  <key>EnvironmentVariables</key><dict>\n"
        f"    <key>MEETING_INPUT</key><string>{mode}</string>\n"
        "  </dict>\n"
        "  <key>RunAtLoad</key><true/>\n"
        "  <key>KeepAlive</key><false/>\n"
        f"  <key>StandardOutPath</key><string>{DIR / 'listen.out'}</string>\n"
        f"  <key>StandardErrorPath</key><string>{DIR / 'listen.err'}</string>\n"
        "</dict></plist>\n"
    )
    LISTEN_PLIST.parent.mkdir(parents=True, exist_ok=True)
    tmp = LISTEN_PLIST.with_suffix(".plist.tmp")
    tmp.write_text(xml, encoding="utf-8")
    os.replace(tmp, LISTEN_PLIST)


def _apply_listen(listen: bool, mode: str) -> bool:
    """Bootout/bootstrap the launchd agent for the logged-in GUI user.

    bootout → bootstrap must NOT be back-to-back: launchd needs a moment to
    tear the label down, else bootstrap fails with `Input/output error`.
    Add a settle delay and a bounded retry (the exact race the live test hit)."""
    import time as _time
    uid = _uid()
    if not uid:
        return False
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}/{LISTEN_LABEL}"],
        capture_output=True, timeout=5,
    )
    if not listen:
        return True
    if mode == "phone":
        # phone audio streams via the PWA server → rolling.txt, not the local
        # daemon. No launchd listen.py to bootstrap; recording state is real
        # (the phone writes the same files), so just don't start a local listener.
        return True
    _write_listen_plist(mode)
    last_err = ""
    for attempt in range(4):
        _time.sleep(0.6)
        result = subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(LISTEN_PLIST)],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            return True
        last_err = result.stderr.decode().strip()
    # If bootstrap still fails, fall back to a direct child process so the
    # user isn't left with listening off and no transcript at all.
    subprocess.Popen(
        [str(PY), str(LISTEN_PY)],
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return False


_RUNNING = {}  # pid → popped process handle for the auto-recap loop


@router.get("/transcript")
async def transcript():
    return {"lines": _tail(ROLLING, 40), "fresh_sec": _age(ROLLING)}


@router.get("/answer")
async def answer():
    text = ANSWER.read_text(encoding="utf-8", errors="replace").strip() if ANSWER.exists() else ""
    return {"text": text, "fresh_sec": _age(ANSWER)}


@router.get("/answers")
async def answers():
    """Structured answer deck (answers.json) for the swipeable card carousel.
    Newest last; the pane shows the last N as cards and older ones in a drawer."""
    deck = []
    if DECK.exists():
        try:
            loaded = json.loads(DECK.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                deck = loaded
        except (OSError, ValueError):
            deck = []
    return {"answers": deck, "fresh_sec": _age(DECK), "live_sec": _age(ANSWER)}


@router.post("/clear/deck")
async def clear_deck():
    """Clear ALL answer cards: empty answers.json (the deck) and answer.txt
    (the live hero). Reversible only in the sense that new cards repopulate —
    the old cards are gone. The transcript is untouched."""
    try:
        DECK.write_text("[]", encoding="utf-8")
    except OSError:
        pass
    try:
        ANSWER.write_text("", encoding="utf-8")
    except OSError:
        pass
    return {"cleared": "deck", "answers": []}


@router.post("/clear/transcript")
async def clear_transcript():
    """Clear the transcript: empty rolling.txt (context window) and full.txt
    (append-only session). The answer deck is untouched."""
    for p in (ROLLING, FULL):
        try:
            p.write_text("", encoding="utf-8")
        except OSError:
            pass
    return {"cleared": "transcript", "lines": []}


@router.get("/full")
async def full():
    """Full transcript (capped) for seeding a Duckwork session — the jump-to-session
    context. full.txt grows linearly, so cap it and tell the caller it was capped."""
    text = FULL.read_text(encoding="utf-8", errors="replace").strip() if FULL.exists() else ""
    CAP = 24000
    if len(text) > CAP:
        return {"text": text[-CAP:], "capped": True, "total": len(text)}
    return {"text": text, "capped": False, "total": len(text)}


@router.get("/status")
async def status():
    return {"listening": _daemon_alive(), "transcript_age_sec": _age(ROLLING)}


@router.get("/settings")
async def settings():
    s = _read_settings()
    # recording = listen intent AND (for local sources) the daemon actually up.
    # Gate on listen first so turning OFF reports false immediately, and phone
    # mode (no daemon) reflects pure intent.
    s["listening"] = bool(s.get("listen")) and (s.get("mode") == "phone" or _daemon_alive())
    s["auto_recap_running"] = any(p.poll() is None for p in list(_RUNNING.values()))
    return s


@router.post("/mode")
async def set_mode(body: dict):
    """Set listen on/off + capture mode; applies to launchd + persists."""
    s = _read_settings()
    if "mode" in body and body["mode"] in _VALID_MODES:
        s["mode"] = body["mode"]
    if "listen" in body:
        s["listen"] = bool(body["listen"])
    ok = _apply_listen(s["listen"], s["mode"])
    _write_settings(s)
    # recording = listen intent AND (for local sources) the daemon actually up.
    # Gate on listen first so turning OFF reports false immediately (no bootout
    # teardown lag), and phone mode (no daemon) reflects pure intent.
    s["listening"] = bool(s["listen"]) and (s["mode"] == "phone" or _daemon_alive())
    s["applied"] = ok
    return s


@router.post("/model")
async def set_model(body: dict):
    s = _read_settings()
    if "model" in body and body["model"] in _VALID_MODELS:
        s["model"] = body["model"]
    if "recap_model" in body and body["recap_model"] in _VALID_MODELS:
        s["recap_model"] = body["recap_model"]
    _write_settings(s)
    return s


@router.post("/recap")
async def set_recap(body: dict):
    """Deprecated continuous auto-recap → no-op persistence. Recap is now an
    on-demand EXPORT (see /run action=recap), never a background loop, so this
    route just reflects settings and never spawns a process."""
    s = _read_settings()
    s["auto_recap"] = bool(body.get("on", False))
    _write_settings(s)
    s["auto_recap_running"] = False
    return s


@router.post("/run")
async def run(body: dict):
    """Fire the answer engine for a given action/model.

    - what | followup | research → on-screen answer (streams into answer.txt,
      appends the deck).
    - watch → record mode: continuous 'what' chunks while auto_assist is set.
    - recap → LLM summary AND save (export type; recap_model is hosted).
    - save → transcript-only save to Records (no summary; subject from model).
    """
    action = body.get("action", "recap")
    model = body.get("model")
    if model not in _VALID_MODELS:
        model = _read_settings().get("model", "glm")
    if action == "recap":
        model = _read_settings().get("recap_model", "glm")
    if action not in _VALID_ACTIONS:
        return {"error": f"unknown action {action}"}
    # record mode is owned by the durable launchd agent — /run watch just arms
    # the flag the loop reads; it never spawns a competing loop.
    if action == "watch":
        s = _read_settings()
        s["auto_assist"] = True
        _write_settings(s)
        return {"started": "watch", "model": model, "armed": True}
    argv = [str(PY), str(ANSWER_PY), "--action", action, "--model", model]
    # stderr → a real file (not DEVNULL) so a dying answer.py is diagnosable
    # instead of silently producing "no answers flow in".
    errfile = open(DIR / "answer.err", "a")
    try:
        proc = subprocess.Popen(
            argv,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=errfile,
        )
        if action == "watch":
            _RUNNING["watch"] = proc
        return {"started": action, "model": model}
    except Exception as exc:
        return {"error": str(exc)}


@router.post("/assist")
async def set_assist(body: dict):
    """Toggle record mode (auto_assist) and set the chunk interval (chunk_sec).

    on=true sets the flag AND spawns the watch loop (answer.py --action watch);
    on=false flips the flag (the loop exits on its next tick) and clears the
    tracked process. chunk_sec is clamped 15–60."""
    s = _read_settings()
    if "chunk_sec" in body:
        try:
            s["chunk_sec"] = max(15, min(60, int(body["chunk_sec"])))
        except (TypeError, ValueError):
            pass
    # assist_mode = WHICH question auto-chunks (a mutually-exclusive, PERSISTED
    # selection). Selecting one does NOT start listening — the capture toggles do
    # that; the watch loop only emits a card when the transcript actually grows.
    if "assist_mode" in body:
        am = body["assist_mode"]
        s["assist_mode"] = am if am in ("off", "what", "followup", "research") else "off"
        s["auto_assist"] = s["assist_mode"] != "off"
    if "on" in body:
        # legacy boolean toggle: on → ensure a mode is selected, off → clear it
        s["auto_assist"] = bool(body["on"])
        if not s["auto_assist"]:
            s["assist_mode"] = "off"
        elif s.get("assist_mode", "off") == "off":
            s["assist_mode"] = "what"
    _write_settings(s)
    # The durable launchd agent com.oz.meeting-watch (KeepAlive) owns the watch
    # loop and reads auto_assist each tick — so setting the flag is ALL that's
    # needed here. No spawn: a second loop would double every card.
    return s


@router.post("/request")
async def request(body: dict):
    action = body.get("action", "assist")
    kind = body.get("kind", action)  # web-research | thi-research | plain action
    context = (body.get("context") or "").strip()
    with open(REQUEST, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {kind}\n")
        if context:
            f.write("CONTEXT: " + context[:2000] + "\n")
    return {"queued": kind, "scoped": bool(context)}


@router.get("/sessions")
async def sessions():
    """List saved meeting Records (the CRUD Read surface) — walk Records/YYYY/MM/week/*.md.
    Split into visible vs. hidden so the pane can show both and let the user restore."""
    vault = _read_settings_vault()
    records_dir = vault / "Records"
    rows = []
    if records_dir.is_dir():
        for f in sorted(records_dir.rglob("*.md"), reverse=True):
            # skip the cross-month pointer notes (week-YYY-MM-DD.md)
            if f.name.startswith("week-") and f.parent.parent.name.startswith("20"):
                continue
            try:
                stat = f.stat()
            except OSError:
                continue
            rel = str(f.relative_to(records_dir))
            rows.append({
                "name": f.name,
                "rel": rel,
                "path": str(f),
                "modified": stat.st_mtime,
            })
    hidden = set(_read_settings().get("hidden_records", []))
    visible = [r for r in rows if r["rel"] not in hidden]
    hidden_rows = [r for r in rows if r["rel"] in hidden]
    return {"sessions": visible, "hidden": hidden_rows, "records_dir": str(records_dir)}


@router.post("/session/hide")
async def session_hide(body: dict):
    """Soft-hide a Record (kept on disk, removed from the default list)."""
    rel = body.get("rel", "")
    if not rel or ".." in rel or rel.startswith("/"):
        return {"error": "invalid rel"}
    s = _read_settings()
    h = set(s.get("hidden_records", []))
    h.add(rel)
    s["hidden_records"] = sorted(h)
    _write_settings(s)
    return {"hidden": rel}


@router.post("/session/restore")
async def session_restore(body: dict):
    """Un-hide a previously soft-hidden Record."""
    rel = body.get("rel", "")
    if not rel or ".." in rel or rel.startswith("/"):
        return {"error": "invalid rel"}
    s = _read_settings()
    h = set(s.get("hidden_records", []))
    h.discard(rel)
    s["hidden_records"] = sorted(h)
    _write_settings(s)
    return {"restored": rel}


@router.post("/session/delete")
async def session_delete(body: dict):
    """Delete a saved Record by its vault-relative path (Records/.../slug.md)."""
    rel = body.get("rel", "")
    if not rel or ".." in rel or rel.startswith("/"):
        return {"error": "invalid rel"}
    vault = _read_settings_vault()
    target = (vault / "Records" / rel).resolve()
    records_root = (vault / "Records").resolve()
    # resolve() guards against traversal; require the target to stay under Records/
    if not str(target).startswith(str(records_root) + os.sep):
        return {"error": "outside Records"}
    if target.is_file() and target.suffix == ".md":
        target.unlink()
        # remove the sibling .field.json if present
        field = target.with_suffix(".field.json")
        if field.exists():
            field.unlink()
        # drop from hidden set too (deleting a hidden record clears it fully)
        s = _read_settings()
        h = set(s.get("hidden_records", []))
        h.discard(rel)
        s["hidden_records"] = sorted(h)
        _write_settings(s)
        return {"deleted": rel}
    return {"error": "not found"}


@router.post("/session/rename")
async def session_rename(body: dict):
    old = body.get("rel", "")
    new_name = body.get("new_name", "")
    if not old or not new_name or ".." in old or old.startswith("/") or "/" in new_name:
        return {"error": "invalid name"}
    if not new_name.lower().endswith(".md"):
        new_name += ".md"
    vault = _read_settings_vault()
    src = (vault / "Records" / old).resolve()
    records_root = (vault / "Records").resolve()
    if not str(src).startswith(str(records_root) + os.sep):
        return {"error": "outside Records"}
    dst = src.with_name(new_name)
    if src.is_file() and src.suffix == ".md" and not dst.exists():
        src.rename(dst)
        field_src = src.with_suffix(".field.json")
        if field_src.exists():
            field_src.rename(dst.with_suffix(".field.json"))
        return {"renamed": old, "to": new_name}
    return {"error": "not found or target exists"}


def _read_settings_vault() -> Path:
    """Resolve the Obsidian vault root the same way answer.py does."""
    env = os.getenv("OBSIDIAN_VAULT_PATH", "")
    if env:
        return Path(env)
    dotenv = Path.home() / ".duckwork" / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(errors="replace").splitlines():
            if line.startswith("OBSIDIAN_VAULT_PATH="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return Path(val)
    return Path.home() / "Documents" / "Markdown"