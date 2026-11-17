#!/usr/bin/env python3
"""meeting-mode listen daemon — capture input(s), transcribe live with
faster-whisper, append to a rolling transcript file.

Runs on Duckwork's own venv interpreter (~/.duckwork/duckwork-agent/venv) — the
faster-whisper/sounddevice/scipy/numpy deps are already installed there.

Usage:
    ~/.duckwork/duckwork-agent/venv/bin/python listen.py

Env overrides:
    MEETING_INPUT          blackhole (default, system audio) | mic (built-in)
                           | both/merge (BlackHole + mic, tagged) | device substring
    MEETING_WHISPER_MODEL  base (default, cached) | small | medium
    MEETING_WHISPER_COMPUTE int8 (default) | float32 | float16
    MEETING_CHUNK_SEC      transcription window seconds (default 5)
    MEETING_ROLLING_CHARS  rolling.txt cap in chars (default 20000)

Output:
    ~/.duckwork/meeting-transcript/rolling.txt   capped tail (context window)
    ~/.duckwork/meeting-transcript/full.txt      append-only full session
"""
import os
import sys
import time
import threading
from collections import deque

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly
from faster_whisper import WhisperModel

# ensure the sibling dedupe.py is importable regardless of the daemon's cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dedupe import should_suppress

SAMPLE_RATE = 48000          # BlackHole native rate
TARGET_RATE = 16000          # faster-whisper expects 16 kHz mono
CHUNK_SEC = float(os.getenv("MEETING_CHUNK_SEC", "5"))
MODEL_SIZE = os.getenv("MEETING_WHISPER_MODEL", "base")
COMPUTE = os.getenv("MEETING_WHISPER_COMPUTE", "int8")
INPUT = os.getenv("MEETING_INPUT", "blackhole").lower()
HOME = os.path.expanduser("~")
DIR = os.path.join(HOME, ".duckwork", "meeting-transcript")
ROLLING = os.path.join(DIR, "rolling.txt")
FULL = os.path.join(DIR, "full.txt")
MAX_ROLLING = int(os.getenv("MEETING_ROLLING_CHARS", "20000"))

# False-positive filtering: keyboard clicks / taps / vape pulls are short,
# broad-spectrum bursts with no sustained voiced energy. These gates drop them
# BEFORE transcription so they never become phantom transcript lines.
ENERGY_FLOOR = float(os.getenv("MEETING_ENERGY_FLOOR", "0.003"))   # RMS floor (post-peak-normalize)
MIN_POST_MS = int(os.getenv("MEETING_MIN_POST_MS", "600"))        # min transcribed ms to keep


def _pick(substr):
    """First device whose name contains substr and has an input channel."""
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if substr in d["name"].lower() and d["max_input_channels"] > 0:
            return i, d["name"]
    return None, None


def _pick_mic():
    """The built-in Mac mic, preferring it over virtual/remote mics."""
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        n = d["name"].lower()
        if "macbook" in n and "microphone" in n and d["max_input_channels"] > 0:
            return i, d["name"]
    for i, d in enumerate(devices):
        n = d["name"].lower()
        if "microphone" in n and d["max_input_channels"] > 0 and "jump desktop" not in n:
            return i, d["name"]
    for i, d in enumerate(devices):
        if "microphone" in d["name"].lower() and d["max_input_channels"] > 0:
            return i, d["name"]
    return None, None


def resolve_sources():
    """Return a list of (idx, name, tag) capture sources.

    Single-source modes carry an empty tag (clean transcript, no marker).
    Merge mode tags each line so both sides read unambiguously in one thread:
    [audio] = computer output (the other party), [mic] = your voice.
    """
    if INPUT in ("both", "merge"):
        out = []
        bi, bn = _pick("blackhole")
        mi, mn = _pick_mic()
        if bi is not None:
            out.append((bi, bn, "audio"))
        if mi is not None:
            out.append((mi, mn, "mic"))
        return out
    if INPUT == "mic":
        idx, name = _pick_mic()
        return [(idx, name, "")] if idx is not None else []
    idx, name = _pick(INPUT)
    return [(idx, name, "")] if idx is not None else []


_ap_lock = threading.Lock()


def trim_rolling():
    try:
        if os.path.getsize(ROLLING) > MAX_ROLLING:
            with open(ROLLING, encoding="utf-8") as f:
                keep = f.read()[-MAX_ROLLING // 2:]
            with open(ROLLING, "w", encoding="utf-8") as f:
                f.write(keep)
    except OSError:
        pass


def append(line):
    os.makedirs(DIR, exist_ok=True)
    with _ap_lock:
        with open(ROLLING, "a", encoding="utf-8") as f:
            f.write(line)
        with open(FULL, "a", encoding="utf-8") as f:
            f.write(line)
        trim_rolling()


def main():
    sources = resolve_sources()
    if not sources:
        sys.exit(f"No capture device matched MEETING_INPUT={INPUT!r} — "
                 f"run scripts/setup.sh, or set MEETING_INPUT to a device name")

    model = WhisperModel(MODEL_SIZE, device="auto", compute_type=COMPUTE)
    desc = ", ".join(f"{name} ({tag})" if tag else name for _, name, tag in sources)
    print(f"meeting-mode listen: {desc} model={MODEL_SIZE}/{COMPUTE} "
          f"chunk={CHUNK_SEC}s", flush=True)

    xc_lock = threading.Lock()   # serialize transcription (single shared model)
    stop = threading.Event()
    workers = []

    def transcribe_and_append(audio, tag):
        # Pre-transcription energy gate: clicks/taps are loud but have low RMS
        # relative to their peak (impulsive, not sustained). Skip cheap if below floor.
        rms = float(np.sqrt(np.mean(np.square(audio))))
        if rms < ENERGY_FLOOR:
            return
        with xc_lock:
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
        # Min-duration gate: an isolated click transcribes as a vanishingly short
        # segment (< MIN_POST_MS). Drop it rather than emit a phantom line.
        if total_ms < MIN_POST_MS and not any(len(w) > 12 for w in words):
            return
        text = " ".join(w for w in words if w).strip()
        if not text:
            return
        # echo gate: if the phone already landed this utterance, drop it
        if tag != "phone" and should_suppress(text, tag, ROLLING):
            print(f"[echo-drop:{tag}] {text[:50]}", flush=True)
            return
        marker = f"[{tag}] " if tag else ""
        line = f"[{time.strftime('%H:%M:%S')}] {marker}{text}\n"
        append(line)
        print(line.strip(), flush=True)

    def worker(idx, name, tag):
        buf = deque()

        def callback(indata, frames, t_info, status):
            if status:
                print(f"[stream:{name}] {status}", flush=True)
            buf.append(indata.copy())

        with sd.InputStream(device=idx, samplerate=SAMPLE_RATE, channels=1,
                            dtype="float32", callback=callback, blocksize=1024):
            acc = []
            while not stop.is_set():
                time.sleep(0.2)
                while True:
                    try:
                        acc.append(buf.popleft())
                    except IndexError:
                        break
                dur = sum(len(b) for b in acc) / SAMPLE_RATE
                if dur < CHUNK_SEC:
                    continue
                raw = np.concatenate(acc)[:, 0]
                acc = []
                audio = resample_poly(raw, TARGET_RATE, SAMPLE_RATE).astype(np.float32)
                peak = float(np.max(np.abs(audio)))
                if peak < 1e-3:
                    continue  # silence; skip transcription
                audio /= max(peak, 1e-6)
                transcribe_and_append(audio, tag)

    for i, (idx, name, tag) in enumerate(sources):
        t = threading.Thread(target=worker, args=(idx, name, tag),
                             daemon=True, name=f"capture-{i}")
        t.start()
        workers.append(t)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()