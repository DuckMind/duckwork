#!/usr/bin/env python3
"""meeting-overlay PWA server — phone mirror of the meeting copilot panel.

Serves the installable PWA (manifest + service worker + icons) over Tailscale,
mirrors the same transcript/answer JSON the desktop pane reads, exposes the same
actions (ask / save / recap / listen toggle / model / mode), and accepts PCM 16k
mono microphone audio over WebSocket — transcribing it with the SAME
faster-whisper model + VAD/energy/min-duration gates the desktop daemon uses.

Run:  python pwa_server.py  (defaults to loopback :9877)

The server is loopback-only by default. `tailscale serve` can publish that
listener on the tailnet without exposing an unauthenticated transcript control
plane to the LAN. Direct LAN use is an explicit authenticated opt-in:
`--lan --token-file /path/to/token`.
"""
import argparse
import asyncio
import hmac
import json
import os
import stat
import sys
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# ensure the sibling dedupe.py is importable regardless of the daemon's cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dedupe import should_suppress

HOME = Path.home()
DIR = HOME / ".duckwork" / "meeting-transcript"
ROLLING = DIR / "rolling.txt"
FULL = DIR / "full.txt"
ANSWER = DIR / "answer.txt"
DECK = DIR / "answers.json"
SETTINGS = DIR / "settings.json"
REQUEST = DIR / "request.txt"

def _scripts_dir() -> Path:
    """Return only the scripts bundled in the reviewed plugin tree."""
    return Path(__file__).resolve().parent


ANSWER_PY = _scripts_dir() / "answer.py"
PY = HOME / ".duckwork" / "duckwork-agent" / "venv" / "bin" / "python"
STATIC = Path(__file__).resolve().parent / "static"

MODEL_SIZE = os.getenv("MEETING_WHISPER_MODEL", "base")
COMPUTE = os.getenv("MEETING_WHISPER_COMPUTE", "int8")
ENERGY_FLOOR = float(os.getenv("MEETING_ENERGY_FLOOR", "0.003"))
MIN_POST_MS = int(os.getenv("MEETING_MIN_POST_MS", "600"))

# ── Phone chunking (pwa_server only) ──────────────────────────────────────────
# The phone streams CONTINUOUSLY, so "silence" must be measured on the AUDIO
# (an RMS hold), never on frame arrival. Measuring frame arrival made this flush
# every ~1.2s and emit 1-2 word fragments, which transcribes badly (whisper runs
# with condition_on_previous_text=False, so a tiny window has no context).
# A chunk now closes on the earlier of: the audio reaching PHONE_CHUNK_SEC, or
# PHONE_SILENCE_SEC of real quiet AFTER at least PHONE_MIN_SEC of audio.
PHONE_CHUNK_SEC = float(os.getenv("MEETING_PHONE_CHUNK_SEC", "15"))     # hard window cap
PHONE_MIN_SEC = float(os.getenv("MEETING_PHONE_MIN_SEC", "8"))          # never emit shorter
PHONE_SILENCE_SEC = float(os.getenv("MEETING_PHONE_SILENCE_SEC", "1.6"))  # quiet hold that closes a chunk


def _frame_rms(pcm16: bytes) -> float:
    """RMS of one socket frame, so the loop can tell speech from quiet."""
    n = len(pcm16) // 2 * 2
    if n < 2:
        return 0.0
    a = np.frombuffer(pcm16[:n], dtype=np.int16).astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(np.square(a))))


def vault_path():
    """Resolve the Obsidian vault root (same as answer.py / plugin_api.py)."""
    env = os.getenv("OBSIDIAN_VAULT_PATH", "")
    if env:
        return Path(env)
    dotenv = HOME / ".duckwork" / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(errors="replace").splitlines():
            if line.startswith("OBSIDIAN_VAULT_PATH="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return Path(val)
    return HOME / "Documents" / "Markdown"

VALID_MODELS = {"host", "local", "glm", "qwen", "off"}
# four capture sources. "phone" = this phone streams its own mic (via /ws/audio
# below); the other three = the desktop daemon captures. One source at a time,
# so there is no phone+desktop merge/echo.
VALID_MODES = {"phone", "blackhole", "mic", "both"}

app = FastAPI(title="meeting-overlay-pwa")

# `None` means loopback-only mode. Direct LAN mode gets a process-local token;
# do not place it in settings.json, transcript files, logs, or generated links.
_access_token: str | None = None
_SESSION_COOKIE = "meeting_pwa_session"


def _token_matches(candidate: str | None) -> bool:
    return bool(_access_token and candidate and hmac.compare_digest(candidate, _access_token))


@app.middleware("http")
async def require_lan_token(request: Request, call_next):
    """Authenticate every HTTP route only when direct LAN mode is selected.

    A one-time `?token=` bootstrap becomes an HttpOnly cookie and redirects to a
    clean URL, so fetches and PWA assets inherit authentication without retaining
    the bearer token in browser history or links.
    """
    if _access_token is None:
        return await call_next(request)
    supplied = request.query_params.get("token")
    if _token_matches(supplied):
        clean = request.url.replace_query_params(**{
            key: value for key, value in request.query_params.items() if key != "token"
        })
        response = RedirectResponse(str(clean), status_code=303)
        response.set_cookie(
            _SESSION_COOKIE, _access_token, httponly=True, samesite="strict",
            secure=request.headers.get("x-forwarded-proto", "").lower() == "https",
        )
        return response
    if _token_matches(request.cookies.get(_SESSION_COOKIE)):
        return await call_next(request)
    return JSONResponse({"detail": "authentication required"}, status_code=401)

# ── lazy whisper model (loaded on first mic connection) ─────────────
_model = None
_model_lock = threading.Lock()


def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from faster_whisper import WhisperModel
                _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type=COMPUTE)
    return _model


# ── shared file helpers (byte-identical semantics to the desktop pane) ─
def _read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _tail(path, n=60):
    txt = _read(path)
    return txt.splitlines()[-n:] if txt else []


def _settings():
    s = {
        "listen": False, "mode": "both", "model": "host", "recap_model": "host",
        "auto_recap": False, "auto_local": False,
        "auto_assist": False, "assist_mode": "off", "chunk_sec": 30,
    }
    try:
        if SETTINGS.exists():
            s.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return s


def _write_settings(s):
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(s, indent=2), encoding="utf-8")
    os.replace(tmp, SETTINGS)


# ── desktop daemon control (the phone drives the Mac's listener via launchd,
#    exactly as the desktop /mode endpoint does — same label, same plist) ────
LISTEN_LABEL = "com.oz.meeting-listener"
LISTEN_PLIST = HOME / "Library" / "LaunchAgents" / f"{LISTEN_LABEL}.plist"
LISTEN_PY = _scripts_dir() / "listen.py"


def _uid():
    try:
        return subprocess.run(["id", "-u"], capture_output=True, text=True, timeout=2).stdout.strip()
    except Exception:
        return ""


def _daemon_alive():
    try:
        out = subprocess.run(
            ["pgrep", "-f", str(LISTEN_PY)],
            capture_output=True, text=True, timeout=2,
        )
        return out.returncode == 0
    except Exception:
        return False


def _write_listen_plist(mode: str) -> None:
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
    """Bootout/bootstrap the launchd agent (same settle-delay + retry as the
    desktop backend, avoiding the bootout→bootstrap Input/output error race)."""
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
        # phone audio streams via /ws/audio → rolling.txt, not the local daemon.
        # No launchd listener to bootstrap; the phone writes the same files.
        return True
    _write_listen_plist(mode)
    last_err = ""
    for _ in range(4):
        time.sleep(0.6)
        result = subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", str(LISTEN_PLIST)],
            capture_output=True, timeout=5,
        )
        if result.returncode == 0:
            return True
        last_err = result.stderr.decode().strip()
    subprocess.Popen(
        [str(PY), str(LISTEN_PY)], start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return False


def _deck():
    if DECK.exists():
        try:
            d = json.loads(DECK.read_text(encoding="utf-8"))
            if isinstance(d, list):
                return d
        except (OSError, ValueError):
            pass
    return []


# ── transcription (same gates as listen.py) ────────────────────────
_tx_lock = threading.Lock()


def transcribe_window(pcm16: bytes, tag="phone"):
    """pcm16 = int16, 16k mono. Returns the emitted text line or None."""
    if len(pcm16) < 1600:  # <0.1s
        return None
    audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
    rms = float(np.sqrt(np.mean(np.square(audio))))
    if rms < ENERGY_FLOOR:
        return None
    model = get_model()
    with _tx_lock:
        segs, _ = model.transcribe(
            audio, language="en", vad_filter=True,
            condition_on_previous_text=False, word_timestamps=True,
        )
        segs = list(segs)
    total_ms = 0
    words = []
    for s in segs:
        total_ms += (s.end - s.start) * 1000
        words.append(s.text.strip())
    if total_ms < MIN_POST_MS and not any(len(w) > 12 for w in words):
        return None
    text = " ".join(w for w in words if w).strip()
    if not text:
        return None
    # echo gate: phone is preferred, so it writes unconditionally; only a
    # slower non-phone echo of the same words would be dropped (see listen.py).
    line = f"[{time.strftime('%H:%M:%S')}] [{tag}] {text}\n"
    DIR.mkdir(parents=True, exist_ok=True)
    with open(ROLLING, "a", encoding="utf-8") as f:
        f.write(line)
    with open(FULL, "a", encoding="utf-8") as f:
        f.write(line)
    return line.strip()


# ── API mirror routes ──────────────────────────────────────────────
@app.get("/api/transcript")
async def transcript():
    return {"lines": _tail(ROLLING), "fresh_sec": _age(ROLLING)}


@app.get("/api/answers")
async def answers():
    deck = _deck()
    return {"answers": deck, "live": _read(ANSWER)}


@app.post("/api/clear/deck")
async def clear_deck():
    """Clear ALL answer cards (answers.json + answer.txt). Transcript untouched."""
    try:
        DECK.write_text("[]", encoding="utf-8")
    except OSError:
        pass
    try:
        ANSWER.write_text("", encoding="utf-8")
    except OSError:
        pass
    return {"cleared": "deck", "answers": []}


@app.post("/api/clear/transcript")
async def clear_transcript():
    """Clear the transcript (rolling.txt + full.txt). Deck untouched."""
    for p in (ROLLING, FULL):
        try:
            p.write_text("", encoding="utf-8")
        except OSError:
            pass
    return {"cleared": "transcript", "lines": []}


@app.get("/api/settings")
async def settings():
    s = _settings()
    # recording = listen intent AND (for local sources) the daemon actually up.
    s["listening"] = bool(s.get("listen")) and (s.get("mode") == "phone" or _daemon_alive())
    return s


def _age(path):
    try:
        return round(time.time() - path.stat().st_mtime, 1)
    except OSError:
        return None


@app.get("/api/sessions")
async def sessions():
    """Records list, split visible/hidden. Hidden rows are soft-hidden from the
    pane and are restorable. `text` is NOT inlined here (it made this poll ~80 KB);
    the phone fetches a body on demand from /api/record."""
    vault = vault_path()
    records_dir = vault / "Records"
    rows = []
    if records_dir.is_dir():
        for f in sorted(records_dir.rglob("*.md"), reverse=True):
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
    hidden = set(_settings().get("hidden_records", []))
    return {
        "sessions": [r for r in rows if r["rel"] not in hidden],
        "hidden": [r for r in rows if r["rel"] in hidden],
    }


@app.get("/api/record")
async def record(rel: str = ""):
    """Return a single record's full markdown body for phone viewing."""
    if not rel or ".." in rel or rel.startswith("/"):
        return JSONResponse({"error": "invalid rel"}, status_code=400)
    vault = vault_path()
    target = (vault / "Records" / rel).resolve()
    root = (vault / "Records").resolve()
    if not str(target).startswith(str(root) + os.sep) or not target.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return {"name": target.name, "text": _read(target)}


def _valid_rel(rel: str) -> bool:
    return bool(rel) and ".." not in rel and not rel.startswith("/")


def _records_target(rel: str):
    """Resolve a vault-relative record path, confined to Records/. None if invalid."""
    vault = vault_path()
    root = (vault / "Records").resolve()
    target = (root / rel).resolve()
    if not str(target).startswith(str(root) + os.sep):
        return None
    return target


def _set_hidden(rel: str, hide: bool) -> None:
    s = _settings()
    h = set(s.get("hidden_records", []))
    h.add(rel) if hide else h.discard(rel)
    s["hidden_records"] = sorted(h)
    _write_settings(s)


# Records management — parity with the desktop pane. The phone is no longer
# read-only: it can hide/restore, rename and delete records, and drive triage.
@app.post("/api/session/hide")
async def session_hide(body: dict):
    """Soft-hide a record (kept on disk, dropped from the default list)."""
    rel = (body or {}).get("rel", "")
    if not _valid_rel(rel):
        return JSONResponse({"error": "invalid rel"}, status_code=400)
    _set_hidden(rel, True)
    return {"hidden": rel}


@app.post("/api/session/restore")
async def session_restore(body: dict):
    """Un-hide a previously soft-hidden record."""
    rel = (body or {}).get("rel", "")
    if not _valid_rel(rel):
        return JSONResponse({"error": "invalid rel"}, status_code=400)
    _set_hidden(rel, False)
    return {"restored": rel}


@app.post("/api/session/delete")
async def session_delete(body: dict):
    """HARD delete: unlink the record + its .field.json so it cannot come back."""
    rel = (body or {}).get("rel", "")
    if not _valid_rel(rel):
        return JSONResponse({"error": "invalid rel"}, status_code=400)
    target = _records_target(rel)
    if target is None or not target.is_file() or target.suffix != ".md":
        return JSONResponse({"error": "not found"}, status_code=404)
    target.unlink()
    field = target.with_suffix(".field.json")
    if field.exists():
        field.unlink()
    _set_hidden(rel, False)
    return {"deleted": rel}


@app.post("/api/session/rename")
async def session_rename(body: dict):
    """Rename a record in place (same directory), keeping the .md extension and
    carrying the sibling .field.json along."""
    rel = (body or {}).get("rel", "")
    new_name = (body or {}).get("new_name", "")
    if not _valid_rel(rel) or not new_name:
        return JSONResponse({"error": "invalid rel or name"}, status_code=400)
    target = _records_target(rel)
    if target is None or not target.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    safe = "".join(c if (c.isalnum() or c in "._- ") else "-" for c in new_name).strip() or "record"
    if not safe.endswith(".md"):
        safe += ".md"
    dest = target.with_name(safe)
    if dest.exists():
        return JSONResponse({"error": "name exists"}, status_code=409)
    target.rename(dest)
    src_field = target.with_suffix(".field.json")
    if src_field.exists():
        src_field.rename(dest.with_suffix(".field.json"))
    return {"renamed": safe}


@app.post("/api/run")
async def run(body: dict):
    action = body.get("action", "recap")
    model = body.get("model") or _settings().get("model", "host")
    if action == "recap":
        model = _settings().get("recap_model", "host")
    if action not in {"what", "followup", "research", "recap", "save", "watch"}:
        return JSONResponse({"error": f"unknown action {action}"}, status_code=400)
    if model not in VALID_MODELS:
        model = "host"
    subprocess.Popen(
        [str(PY), str(ANSWER_PY), "--action", action, "--model", model],
        start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return {"started": action, "model": model}


@app.post("/api/assist")
async def assist(body: dict):
    """Toggle record mode (auto_assist) + chunk interval. The durable launchd
    agent com.oz.meeting-watch owns the watch loop and reads auto_assist each
    tick — so this only sets the flag; it never spawns a competing loop."""
    s = _settings()
    if "chunk_sec" in body:
        try:
            s["chunk_sec"] = max(15, min(60, int(body["chunk_sec"])))
        except (TypeError, ValueError):
            pass
    # assist_mode = WHICH question auto-chunks (mutually-exclusive, PERSISTED).
    # Selecting one does NOT start listening — the capture toggles do that.
    if "assist_mode" in body:
        am = body["assist_mode"]
        s["assist_mode"] = am if am in ("off", "what", "followup", "research") else "off"
        s["auto_assist"] = s["assist_mode"] != "off"
    if "on" in body:
        s["auto_assist"] = bool(body["on"])
        if not s["auto_assist"]:
            s["assist_mode"] = "off"
        elif s.get("assist_mode", "off") == "off":
            s["assist_mode"] = "what"
    _write_settings(s)
    return s


@app.post("/api/settings")
async def set_settings(body: dict):
    s = _settings()
    if "model" in body and body["model"] in VALID_MODELS:
        s["model"] = body["model"]
    if "recap_model" in body and body["recap_model"] in VALID_MODELS:
        s["recap_model"] = body["recap_model"]
    if "mode" in body and body["mode"] in VALID_MODES:
        s["mode"] = body["mode"]
    if "listen" in body:
        s["listen"] = bool(body["listen"])
    # phone source: the phone streams its own mic (no local daemon) — recording
    # = the listen intent. Other sources boot the Mac's launchd listener.
    _apply_listen(s["listen"], s["mode"])
    _write_settings(s)
    s["listening"] = bool(s["listen"]) and (s["mode"] == "phone" or _daemon_alive())
    return s


@app.post("/api/request")
async def request(body: dict):
    kind = body.get("kind", "web-research")
    context = (body.get("context") or "").strip()
    with open(REQUEST, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {kind}\n")
        if context:
            f.write("CONTEXT: " + context[:2000] + "\n")
    return {"queued": kind}


# ── mic ingest ─────────────────────────────────────────────────────
@app.websocket("/ws/audio")
async def ws_audio(ws: WebSocket):
    # HTTP middleware does not protect WebSockets. The browser automatically
    # sends the bootstrap cookie; accepting the query token also permits the
    # first authenticated socket while an older browser is still following the
    # redirect that set it.
    if _access_token is not None and not (
        _token_matches(ws.cookies.get(_SESSION_COOKIE))
        or _token_matches(ws.query_params.get("token"))
    ):
        await ws.close(code=1008, reason="authentication required")
        return
    await ws.accept()
    buf = bytearray()
    loop = asyncio.get_running_loop()
    last_loud = time.time()   # last frame whose RMS cleared the energy floor
    saw_speech = False        # did this buffer contain any actual speech?
    try:
        while True:
            data = await ws.receive_bytes()
            buf.extend(data)
            now = time.time()
            if _frame_rms(data) >= ENERGY_FLOOR:
                last_loud = now
                saw_speech = True
            dur = len(buf) / 2 / 16000          # audio seconds, NOT wall-clock
            quiet = now - last_loud
            # Close on the window cap, or on a real quiet hold once the buffer
            # is long enough to be worth transcribing. Silent buffers are
            # dropped without a whisper call.
            flush = dur >= PHONE_CHUNK_SEC or (quiet >= PHONE_SILENCE_SEC and dur >= PHONE_MIN_SEC)
            if flush:
                if saw_speech:
                    await loop.run_in_executor(None, transcribe_window, bytes(buf), "phone")
                buf = bytearray()
                saw_speech = False
                last_loud = now
    except WebSocketDisconnect:
        pass
    finally:
        # transcribe whatever remains on disconnect (short utterance at hangup)
        if saw_speech and len(buf) > 1600:
            try:
                await loop.run_in_executor(None, transcribe_window, bytes(buf), "phone")
            except Exception:
                pass


# ── static PWA (mounted last so /api wins) ─────────────────────────
if STATIC.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="pwa")


def main():
    global _access_token
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9877)
    ap.add_argument("--lan", action="store_true", help="bind all interfaces; requires --token-file")
    ap.add_argument("--token-file", type=Path, help="file containing the direct-LAN access token")
    args = ap.parse_args()
    if args.lan:
        if args.token_file is None:
            ap.error("--lan requires --token-file")
        try:
            if stat.S_IMODE(args.token_file.stat().st_mode) & 0o077:
                ap.error("--token-file must be owner-readable only (chmod 600)")
            _access_token = args.token_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            ap.error(f"cannot read --token-file: {exc}")
        if not _access_token or len(_access_token) < 24:
            ap.error("--token-file must contain a non-empty high-entropy token (at least 24 characters)")
        host = "0.0.0.0"
    else:
        if args.token_file is not None:
            ap.error("--token-file is only valid together with --lan")
        host = "127.0.0.1"
    import uvicorn
    uvicorn.run(app, host=host, port=args.port)


if __name__ == "__main__":
    main()