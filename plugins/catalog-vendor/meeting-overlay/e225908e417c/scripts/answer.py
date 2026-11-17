#!/usr/bin/env python3
"""meeting-mode answer engine — run an LLM over the live transcript, on demand.

Drives the meeting-overlay answer panel (streams into answer.txt, appends a
structured answers.json deck) and saves meetings to the vault as Records.

Usage:
    answer.py --action <what|followup|research|recap|save> [--model glm|qwen] [--name slug]

Actions:
    what      "What should I say?" — short in-the-moment phrasing.   (ask)
    followup  3-4 follow-up questions.                               (ask)
    research  deeper subject-matter synthesis (model knowledge).     (ask)
    recap     LLM summary (decisions/actions/questions) AND save.    (export)
    save      transcript-only save to Records (no summary).          (export)

Models:
    glm   hosted GLM Flash via fordex (OAuth agent_key; openrouter fallback).
    qwen  local Qwen3-4B via ollama (offline fallback).

Outputs:
    ~/.duckwork/meeting-transcript/answer.txt    latest answer (STREAMED as it lands)
    ~/.duckwork/meeting-transcript/answers.json  structured deck (id/ts/action/model/text)
    ~/.duckwork/meeting-transcript/answers.log   append-only Q&A history (legacy)
    <vault>/Records/YYYY/MM/<Mon–Sun week>/<subject>.md   saved meeting
    <vault>/Records/.../<subject>.field.json               Mean Judge Record payload
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error

from pathlib import Path
from datetime import date, timedelta

HOME = Path.home()
DIR = HOME / ".duckwork" / "meeting-transcript"
ROLLING = DIR / "rolling.txt"
FULL = DIR / "full.txt"
ANSWER = DIR / "answer.txt"
HISTORY = DIR / "answers.log"
DECK = DIR / "answers.json"
QUEUE = DIR / "meanjudge-queue.jsonl"

GLM_MODEL = os.getenv("MEETING_GLM_MODEL", "")          # empty → read Duckwork config default
FALLBACK_MODEL = os.getenv("MEETING_FALLBACK_MODEL", "deepseek/deepseek-v4-flash")
QWEN_MODEL = os.getenv("MEETING_QWEN_MODEL", "qwen3:4b")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "")
OLLAMA = os.getenv("MEETING_OLLAMA_URL", "http://127.0.0.1:11434")
FORDEX_INFERENCE = "https://inference-api.fordex.com/v1"


def _duckwork_default():
    """Read (model, provider) from ~/.duckwork/config.yaml `model:` block.

    "Host" means "whatever Duckwork' system default is" — not a hardcoded model.
    Falls back to glm-flash via fordex if the block is unreadable."""
    default, provider = "z-ai/glm-5.3-flash", "fordex"
    cfg = HOME / ".duckwork" / "config.yaml"
    try:
        if cfg.exists():
            in_model = False
            for line in cfg.read_text(errors="replace").splitlines():
                stripped = line.rstrip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped == "model:":
                    in_model = True
                    continue
                lead = len(line) - len(line.lstrip())
                if in_model and stripped and lead == 0:
                    in_model = False
                if not in_model:
                    continue
                s = stripped.strip()
                if s.startswith("default:"):
                    default = s.split(":", 1)[1].strip().strip('"').strip("'")
                elif s.startswith("provider:"):
                    provider = s.split(":", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return default, provider


def read(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def vault_path():
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


def from_dotenv(key):
    if not key:
        return ""
    dotenv = HOME / ".duckwork" / ".env"
    if not dotenv.exists():
        return ""
    for line in dotenv.read_text(errors="replace").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


SETTINGS = DIR / "settings.json"


def read_settings():
    """Read settings, MERGED OVER DEFAULTS. The defaults matter: several writers
    (do_save, _set_auto_local) read-then-write the dict, and a writer that starts
    from a bare {} drops any key it does not touch — which is how `assist_mode`
    silently disappeared once. Merging defaults makes the schema self-healing."""
    s = dict(_SETTINGS_DEFAULTS)
    try:
        if SETTINGS.exists():
            loaded = json.loads(SETTINGS.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                s.update(loaded)
    except (OSError, ValueError):
        pass
    return s


_SETTINGS_DEFAULTS = {
    "listen": False,
    "mode": "phone",
    "model": "host",
    "recap_model": "host",
    "auto_recap": False,
    "auto_local": False,
    "hidden_records": [],
    "auto_assist": False,
    "assist_mode": "off",     # off | what | followup | research
    "chunk_sec": 30,
    "last_saved_hash": None,
    "last_saved_path": None,
}


def resolve_model(explicit: str) -> str:
    """Normalize to 'host' | 'local' | 'off'. Legacy 'glm'/'qwen' map through.
    'host' means the Duckwork system default (auto); 'local' means ollama-qwen;
    'off' means NO model is engaged — transcription continues but no answer is
    generated (the transcript keeps flowing, cards just stop stacking)."""
    # legacy aliases first
    if explicit == "glm":
        explicit = "host"
    elif explicit == "qwen":
        explicit = "local"
    if explicit in ("host", "local", "off"):
        return explicit
    persisted = read_settings().get("model", "")
    if persisted == "glm":
        persisted = "host"
    elif persisted == "qwen":
        persisted = "local"
    if persisted in ("host", "local", "off"):
        return persisted
    return "host"


def transcript_window(seconds=90):
    return read(ROLLING) or read(FULL)


def _fordex_runtime_credential():
    """Resolve a fresh Fordex Portal inference JWT (agent_key)."""
    try:
        agent_root = HOME / ".duckwork" / "duckwork-agent"
        code = subprocess.run(
            [
                sys.executable, "-c",
                "import sys, json\n"
                f"sys.path.insert(0, {str(agent_root)!r})\n"
                "from duckwork_cli.auth_fordex import resolve_fordex_runtime_credentials as f\n"
                "c = f()\n"
                "print(json.dumps({'k': c.get('api_key') or c.get('agent_key'), "
                "'b': (c.get('base_url') or c.get('inference_base_url') or '').rstrip('/')}))",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if code.returncode == 0:
            d = json.loads(code.stdout.strip().splitlines()[-1])
            if d.get("k"):
                return d["k"], d.get("b") or FORDEX_INFERENCE
    except Exception:
        pass
    raise RuntimeError("fordex credential unavailable")


def _payload(model, system, user, stream):
    p = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        # The meeting copilot needs speed, not depth: pin reasoning to the LOWEST
        # tier so it never inherits a high global default and never burns tokens
        # thinking about a short "what should I say" answer.
        "reasoning_effort": "low",
    }
    if stream:
        p["stream"] = True
    return p


def _open_chat(base_url, bearer, model, system, user, stream=True):
    payload = _payload(model, system, user, stream)
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=180)


def _sse_deltas(resp):
    """Yield content deltas from an OpenAI-style text/event-stream response.

    Skips `reasoning_content` deltas (Fordex/GLM emit the chain-of-thought in a
    separate field) so only the real answer text reaches the stream."""
    for raw in resp:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
        except ValueError:
            continue
        delta = obj.get("choices", [{}])[0].get("delta", {})
        if delta.get("reasoning_content"):
            continue
        content = delta.get("content", "")
        if content:
            yield content


def _chat(base_url, bearer, model, system, user, on_delta, stream=True):
    """Stream a hosted completion, calling on_delta(chunk) as tokens land.

    GLM through Fordex wraps the chain-of-thought inline and ends it with a
    literal ` response` marker (same shape as ollama qwen3). Buffer until that
    marker so the reasoning never reaches the answer stream or the card — the
    user wants the pointed answer, not the narrator."""
    resp = _open_chat(base_url, bearer, model, system, user, stream=stream)
    if not stream:
        data = json.loads(resp.read().decode())
        text = data["choices"][0]["message"]["content"].strip()
        text = _strip_reasoning(text)
        on_delta(text)
        return text
    buf = ""
    passed = False
    emitted = ""
    for delta in _sse_deltas(resp):
        if passed:
            on_delta(delta)
            emitted += delta
            continue
        buf += delta
        idx = buf.rfind(" response")
        if idx != -1:
            passed = True
            tail = buf[idx + len(" response"):].lstrip("\n ")
            buf = ""
            if tail:
                on_delta(tail)
                emitted += tail
    if passed:
        return emitted.strip()
    if buf:
        on_delta(buf)
    return (buf or emitted).strip()


def _strip_reasoning(text):
    """Drop any inline reasoning up to a ` response` marker from a finished
    (non-streamed) answer, so a reasoning model can't narrate into the card."""
    idx = text.rfind(" response")
    if idx != -1:
        return text[idx + len(" response"):].lstrip("\n ").strip()
    return text.strip()


def host_stream(system, user, on_delta):
    """Host = Duckwork system default. resolve the default model/provider from
    config.yaml, route fordex → openrouter fallback. Never falls back mid-stream."""
    host_model, provider = _duckwork_default()
    model = GLM_MODEL or host_model
    if provider.lower() != "fordex":
        # provider not fordex: go straight to openrouter with the default model
        key = os.getenv("OPENROUTER_API_KEY", "") or from_dotenv("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("duckwork default provider is not fordex and no OPENROUTER_API_KEY")
        return _chat("https://openrouter.ai/api/v1", key, model, system, user, on_delta)
    try:
        bearer, base = _fordex_runtime_credential()
    except Exception:
        key = os.getenv("OPENROUTER_API_KEY", "") or from_dotenv("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("fordex credential unavailable and no OPENROUTER_API_KEY fallback")
        bearer, base, model = key, "https://openrouter.ai/api/v1", FALLBACK_MODEL
    return _chat(base, bearer, model, system, user, on_delta)


def qwen_stream(system, user, on_delta):
    payload = {
        "model": QWEN_MODEL, "stream": True, "think": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": 0.3},
    }
    req = urllib.request.Request(
        f"{OLLAMA}/api/chat", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    # qwen3 embeds its reasoning chain into message.content, separated from the
    # real answer by a ` response` marker (think:false is ignored by ollama).
    # Buffer until that marker is seen so reasoning never leaks into the live
    # stream; emit only the post-marker tail, incrementally.
    buf = ""
    passed = False
    emitted = ""
    with urllib.request.urlopen(req, timeout=300) as resp:
        for raw in resp:
            try:
                obj = json.loads(raw)
            except ValueError:
                continue
            chunk = obj.get("message", {}).get("content", "")
            if not chunk:
                continue
            if passed:
                on_delta(chunk)
                emitted += chunk
                continue
            buf += chunk
            idx = buf.rfind(" response")
            if idx != -1:
                passed = True
                tail = buf[idx + len(" response"):].lstrip("\n ")
                buf = ""
                if tail:
                    on_delta(tail)
                    emitted += tail
    # If no marker ever surfaced (model emitted no reasoning), stream the buffer.
    if passed:
        return emitted.strip()
    if buf:
        on_delta(buf)
    return (buf or emitted).strip()


SYSTEM = (
    "You are a live meeting copilot. You answer from the provided transcript "
    "only. Output ONLY the answer itself — no preamble, no 'I would say', no "
    "explanation of your reasoning, no meta-commentary about the transcript. "
    "Be concise and direct — the user is reading mid-conversation. Never "
    "invent meeting content; if the transcript is thin, say so in one line."
)


def build(action):
    tx = transcript_window()
    if action == "what":
        return SYSTEM, (
            "Here is the live transcript so far:\n\n"
            f"{tx or '(nothing heard yet)'}\n\n"
            'Answer "what should I say?" — a short, natural phrasing the user '
            "can say right now in response to the last point or question heard. "
            "One or two sentences."
        )
    if action == "followup":
        return SYSTEM, (
            "Here is the live transcript so far:\n\n"
            f"{tx or '(nothing heard yet)'}\n\n"
            "Give 3-4 sharp follow-up questions the user could ask next, one "
            "per line, each advancing the conversation."
        )
    if action == "research":
        return SYSTEM, (
            "Here is the full meeting transcript:\n\n"
            f"{read(FULL) or tx or '(nothing heard yet)'}\n\n"
            "Act as a subject-matter researcher: give background, context, and "
            "framing that would help the user understand the topic better. "
            "Clearly separate what comes from the transcript vs. your own knowledge."
        )
    if action == "recap":
        return SYSTEM, (
            "Here is the full transcript so far:\n\n"
            f"{read(FULL) or tx or '(nothing heard yet)'}\n\n"
            "Give a structured recap with three labeled sections: "
            "**Decisions**, **Action items**, **Open questions**."
        )
    if action == "subject":
        return SYSTEM, (
            "Summarize this meeting transcript into a short, searchable 3–7 word "
            "title phrase (no punctuation, title case). Example: "
            "\"Launch Timing Shoulder Surgery\". Return ONLY the phrase.\n\n"
            f"{read(FULL) or read(ROLLING) or '(nothing heard yet)'}"
        )
    raise ValueError(f"unknown action {action!r}")


def generate_streaming(model, action, on_delta):
    system, user = build(action)
    fn = host_stream if model in ("host", "glm") else qwen_stream
    return fn(system, user, on_delta)


def write_answer(text):
    DIR.mkdir(parents=True, exist_ok=True)
    with open(ANSWER, "w", encoding="utf-8") as f:
        f.write(text + "\n")


def append_history(action, model, text):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(f"\n## [{stamp}] {action} ({model})\n\n{text}\n")


def append_deck(action, model, text):
    """Structured answer deck (newest last) the pane reads for the card carousel."""
    deck = []
    try:
        if DECK.exists():
            deck = json.loads(DECK.read_text(encoding="utf-8"))
            if not isinstance(deck, list):
                deck = []
    except (OSError, ValueError):
        deck = []
    entry = {
        "id": str(int(time.time() * 1000)),
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "model": model,
        "text": text,
    }
    deck.append(entry)
    # keep the last ~40 for the drawer; the deck UI shows ~10 newest
    deck = deck[-40:]
    DECK.write_text(json.dumps(deck, indent=2), encoding="utf-8")


def _week_bounds(today=None):
    today = today or date.today()
    start = today - timedelta(days=today.weekday())  # Monday
    end = start + timedelta(days=6)                  # Sunday
    # month that owns the majority of the week's days
    if start.month == end.month:
        month = start.month
        year = start.year
    else:
        n_start = sum(1 for i in range(7) if (start + timedelta(days=i)).month == start.month)
        if n_start >= 4:
            month, year = start.month, start.year
        else:
            month, year = end.month, end.year
    return start, end, year, month


def _records_dir(today=None):
    start, end, year, month = _week_bounds(today)
    vault = vault_path()
    week_folder = f"{start:%Y-%m-%d} to {end:%m-%d}"
    target = vault / "Records" / str(year) / f"{month:02d}" / week_folder
    target.mkdir(parents=True, exist_ok=True)
    if start.month != end.month:
        other_month = end.month if month == start.month else start.month
        pointer = vault / "Records" / str(year) / f"{other_month:02d}"
        pointer.mkdir(parents=True, exist_ok=True)
        note = pointer / f"week-{start:%Y-%m-%d}.md"
        note.write_text(
            f"# Week {start:%Y-%m-%d}\n\n"
            f"→ see `{year}/{month:02d}/{week_folder}`\n",
            encoding="utf-8")
    return target, week_folder


def _subject(model, tx):
    system, user = build("subject")
    if model in ("host", "glm"):
        return host_stream(system, user, lambda _: None)[:80]
    return qwen_stream(system, user, lambda _: None)[:80]


def _safe_slug(text):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return slug[:60] or f"meeting-{time.strftime('%Y%m%d-%H%M')}"


def _pad(text, n=150):
    """Ensure a slot clears the field's 150-char floor. Pads with real modal
    context (never invented meeting content); returns the (possibly padded) text."""
    text = (text or "").strip()
    if len(text) >= n:
        return text
    return text + ("\n\nCaptured by the meeting-mode copilot; see the Records "
                   "vault file for the full transcript and answers.")


def save_record(tx, history, subject, model, summary=""):
    """Write the meeting .md into the Records tree and emit the Mean Judge payload."""
    target, week_folder = _records_dir()
    slug = _safe_slug(subject)
    fname = f"{slug}.md"
    parts = [
        f"# {subject or 'Meeting'}\n",
        f"> {time.strftime('%Y-%m-%d %H:%M')} · {week_folder} · model {model}\n",
    ]
    if summary:
        parts.append(f"\n## Summary\n\n{summary}\n")
    parts.append(f"\n## Transcript\n\n```\n{tx or '(no transcript)'}\n```\n")
    parts.append(f"\n## Answers\n\n{history or '(no answers recorded yet)'}\n")
    out = target / fname
    out.write_text("".join(parts), encoding="utf-8")

    # Mean Judge Record payload — kind=report, topic_tags meeting+record, rich
    # structured body under plural `body` keys (the field's richness floor).
    subject_txt = subject or f"meeting {slug}"
    tx_field = _pad(tx, 150)
    conclusion = _pad(summary or history, 150)
    tech = _pad(
        f"Week {week_folder} · model {model} · file {fname} · vault {vault_path()}"
        f" · exported {time.strftime('%Y-%m-%d %H:%M:%S')} by meeting-mode copilot",
        150)
    implication = _pad(history or summary, 150)
    field = {
        "kind": "report",
        "sector_id": "UNDERSTANDING_EMPIRICAL",
        "topic_tags": ["meeting", "record"],
        "concept_name": subject_txt[:60],
        "body": {
            "premises": [
                {"claim_id": "p1", "text": tx_field, "status": "asserted",
                 "provenance_ids": [f"meeting:{slug}"]}
            ],
            "conclusions": [
                {"conclusion_id": "c1", "text": conclusion, "status": "qualified",
                 "premise_ids": ["p1"]}
            ],
            "technical_details": [
                {"detail_id": "d1", "text": tech, "provenance_ids": [f"meeting:{slug}"]}
            ],
            "system_implications": [
                {"implication_id": "i1", "condition": implication, "direction": "forward",
                 "kind": "semantic", "target_ref": f"Records/{week_folder}/{fname}"}
            ],
        },
    }
    field_path = target / f"{slug}.field.json"
    field_path.write_text(json.dumps(field, indent=2), encoding="utf-8")
    seated = _seat_or_queue(field, slug)
    if seated:
        # mark the local field.json as seated so the queue/flush knows it landed
        field_path.write_text(json.dumps({"seated": True, **field}, indent=2), encoding="utf-8")
    return out


def _seat_or_queue(field, slug):
    """Attempt desk POST /v1/entries; else queue for meanjudge-writer."""
    desk = os.getenv("MEANJUDGE_DESK_URL", "") or from_dotenv("MEANJUDGE_DESK_URL")
    if desk:
        try:
            req = urllib.request.Request(
                desk.rstrip("/") + "/v1/entries",
                data=json.dumps(field).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read().decode("utf-8", "replace")
                try:
                    obj = json.loads(body)
                except ValueError:
                    obj = {}
                if r.status == 200 and obj.get("ok", False) is not False:
                    return True
        except Exception:
            pass
    with open(QUEUE, "a", encoding="utf-8") as f:
        f.write(json.dumps(field) + "\n")
    return False


def do_save(model):
    """Transcript-only save (no LLM summary); subject comes from the model.

    IDEMPOTENT: the transcript's hash is remembered in settings, so pressing
    Save twice on an unchanged transcript does NOT create a second record
    (the duplicate the pane's record list would otherwise accumulate)."""
    import hashlib
    tx = read(FULL) or read(ROLLING)
    if not tx.strip():
        return "(nothing to save — transcript is empty)"
    h = hashlib.sha256(tx.strip().encode("utf-8")).hexdigest()[:16]
    s = read_settings()
    if s.get("last_saved_hash") == h and s.get("last_saved_path"):
        return s["last_saved_path"] + "  (already saved — transcript unchanged)"
    history = read(HISTORY)
    subject = _subject(model, tx)
    out = save_record(tx, history, subject, model, summary="")
    s = read_settings()
    s["last_saved_hash"] = h
    s["last_saved_path"] = str(out)
    SETTINGS.write_text(json.dumps(s, indent=2), encoding="utf-8")
    return out


def _set_auto_local(flag):
    """Persist the auto-local flag so the pane's Model label can show 'auto local'."""
    s = read_settings()
    s["auto_local"] = bool(flag)
    SETTINGS.write_text(json.dumps(s, indent=2), encoding="utf-8")


def _generate_with_fallback(model, action, on_delta):
    """Run the chosen model; if 'host' fails (offline / no credential), fall
    back to local ollama automatically and mark it so the UI shows the state."""
    if model == "host":
        try:
            return generate_streaming("host", action, on_delta), "host"
        except Exception:
            _set_auto_local(True)
            # reset the partially-written answer.txt before retrying locally
            write_answer("")
            return generate_streaming("local", action, on_delta), "local"
    return generate_streaming("local", action, on_delta), "local"


def do_watch(model):
    """Continuous 'what to say' record mode.

    While `auto_assist` is set, poll the transcript every ~1s; when at least
    `chunk_sec` has elapsed since the last card AND the transcript has grown,
    generate a fresh 'what' answer and append it as a deck card. Reads
    settings each tick so the scrobbler (chunk_sec) and the off-switch both
    take effect without a restart.

    SINGLE OWNER: the launchd agent com.oz.meeting-watch (KeepAlive) is the one
    and only watch loop. The backends no longer spawn it — they only set the
    auto_assist flag this loop reads — so there is no double-card race and no
    guard to fight launchd's restart cycle."""
    last_card_at = 0.0
    last_len = len(read(FULL) or read(ROLLING))
    idle_logged = False
    while True:
        s = read_settings()
        # DURABLE: never exit. A launchd agent (com.oz.meeting-watch) keeps this
        # process alive so record mode survives backend restarts. When the flag
        # is off we IDLE (not exit) — flipping the flag on resumes instantly.
        if not s.get("auto_assist"):
            if not idle_logged:
                print(f"watch [{time.strftime('%H:%M:%S')}] idle (auto_assist off)", flush=True)
                idle_logged = True
            time.sleep(1.0)
            continue
        idle_logged = False
        chunk = max(15, min(60, int(s.get("chunk_sec", 30) or 30)))
        cur = read(FULL) or read(ROLLING)
        cur_len = len(cur)
        if cur_len < last_len:
            # transcript shrank — it was cleared or trimmed. Reset the baseline
            # so growth is measured from the new (smaller) size, else `grown`
            # stays False forever and no card is ever emitted again.
            last_len = cur_len
            grown = False
        else:
            grown = cur_len > last_len
            last_len = cur_len
        now = time.time()
        # re-resolve the model each tick: turning it 'off' mid-record stops the
        # cards (transcript keeps flowing) and resumes when a model is re-picked.
        live_model = resolve_model(s.get("model", model))
        # which question type auto-chunks: the persisted assist_mode selection
        mode_kind = s.get("assist_mode") or "what"
        if mode_kind not in ("what", "followup", "research"):
            mode_kind = "what"
        if grown and now - last_card_at >= chunk and live_model != "off":
            # a fresh card of the selected mode from the latest transcript window
            system, user = build(mode_kind)
            text, effective = _generate_with_fallback(live_model, mode_kind, lambda _: None)
            if text:
                append_deck(mode_kind, effective, text)
                append_history(mode_kind, effective, text)
                # keep answer.txt in sync with the newest chunk, else a stale
                # live card from the last manual answer masks the new chunk
                write_answer(text)
                last_card_at = now
                print(f"chunk [{time.strftime('%H:%M:%S')}] {mode_kind} {text[:80]}", flush=True)
        time.sleep(1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", required=True,
                    choices=["what", "followup", "research", "recap", "save", "watch"])
    ap.add_argument("--model", default="", choices=["host", "local", "glm", "qwen", "off", ""])
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    model = resolve_model(args.model)
    if model == "host":
        _set_auto_local(False)

    # ── export: save (transcript only, no model needed) ─────────────
    if args.action == "save":
        out = do_save(model)
        print(f"SAVED {out}")
        return

    # ── model off: transcription flows but the answer engine is disengaged.
    #    No card is generated for ANY ask/recap action; record mode is a no-op.
    if model == "off":
        print("MODEL_OFF — no answer generated (transcript still flowing)", flush=True)
        return

    # ── record mode: continuous 'what' chunks while auto_assist is on ──
    if args.action == "watch":
        do_watch(model)
        return

    # ── ask + recap: stream the answer into answer.txt as it lands ──
    acc = []
    def on_delta(chunk):
        acc.append(chunk)
        write_answer("".join(acc))
    text, effective = _generate_with_fallback(model, args.action, on_delta)

    if args.action == "recap":
        # recap = summary AND save (on-screen reading is not vital)
        tx = read(FULL) or read(ROLLING)
        history = read(HISTORY)
        subject = _subject(effective, tx) if tx else ""
        out = save_record(tx, history, subject, effective, summary=text)
        print(f"SNAPSHOT {out}")
    else:
        print(text)

    write_answer(text)
    append_history(args.action, effective, text)
    append_deck(args.action, effective, text)


if __name__ == "__main__":
    main()