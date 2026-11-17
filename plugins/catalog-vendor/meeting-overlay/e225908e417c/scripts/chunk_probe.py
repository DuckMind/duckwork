#!/usr/bin/env python3
"""Verify the phone chunking fix end-to-end.

Streams slow speech (with the pauses + fillers the user described) into
/ws/audio in real time, then reports the transcript lines that land. Also
replays the SAME frame timeline through the OLD flush predicate so the
before/after is measured on identical input, not asserted.
"""
import asyncio, io, json, os, subprocess, sys, time, wave
from pathlib import Path

import numpy as np

TRANSCRIPT = Path(os.path.expanduser("~/.duckwork/meeting-transcript/rolling.txt"))
WS = "ws://127.0.0.1:9877/ws/audio"
RATE = 16000
FRAME_S = 0.128                      # the frame size the PWA sends
FRAME_BYTES = int(RATE * FRAME_S) * 2

# Slow speech, real filler, real pauses — the condition reported.
SEGMENTS = [
    ("Um, so I think", 1.5),
    ("we should probably", 1.9),
    ("move the launch to next week", 1.1),
    ("because, uh, the, the vendor", 1.7),
    ("is not ready yet", 1.3),
]


def say_pcm(text: str, rate: int = 132) -> bytes:
    """Render text to 16 kHz mono int16 PCM using the macOS voice."""
    aiff = "/tmp/_chunk_probe.aiff"
    subprocess.run(["say", "-r", str(rate), "-o", aiff, text], check=True)
    wav = "/tmp/_chunk_probe.wav"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", aiff, "-ar", str(RATE), "-ac", "1",
                        "-f", "wav", wav], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        subprocess.run(["afconvert", "-f", "WAVE", "-d", f"LEI16@{RATE}", "-c", "1",
                        aiff, wav], check=True)
    with wave.open(wav, "rb") as w:
        return w.readframes(w.getnframes())


def build_timeline():
    """-> (frames[list[bytes]], silence_flags[list[bool]]) in real-time order."""
    pcm = bytearray()
    speech = []                                  # (start_byte, end_byte) of speech
    for text, gap in SEGMENTS:
        seg = say_pcm(text)
        start = len(pcm)
        pcm.extend(seg)
        speech.append((start, len(pcm)))
        pcm.extend(b"\x00" * int(RATE * 2 * gap))
    frames, flags = [], []
    for i in range(0, len(pcm), FRAME_BYTES):
        f = bytes(pcm[i:i + FRAME_BYTES])
        a = np.frombuffer(f[:len(f) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768.0
        frames.append(f)
        flags.append(bool(len(a)) and float(np.sqrt(np.mean(a ** 2))) >= 0.003)
    return frames, flags


def old_predicate(frames, flags):
    """The shipped bug: silence measured by frame ARRIVAL on a live socket."""
    out, buf, last_flush = [], 0, 0.0
    starts, t = [], 0.0
    for i, f in enumerate(frames):
        buf += len(f)
        t = i * FRAME_S                      # audio time == wall time (real-time stream)
        dur = buf / 2 / RATE
        if dur >= 5.0 or (buf > 1600 and t - last_flush > 1.2):
            out.append((round(t - sum(d for d, _ in []), 2), round(dur, 2)))
            starts.append(round(t - dur, 2))
            buf = 0
            last_flush = t
    return list(zip(starts, [d for _, d in out]))


def new_predicate(frames, flags):
    """The fix: RMS hold on the audio + a minimum worth transcribing."""
    out, buf, last_loud, saw = [], 0, 0.0, False
    start = 0.0
    for i, f in enumerate(frames):
        buf += len(f)
        t = i * FRAME_S
        if flags[i]:
            last_loud = t
            saw = True
        dur = buf / 2 / RATE
        quiet = t - last_loud
        if dur >= 15.0 or (quiet >= 1.6 and dur >= 8.0):
            if saw:
                out.append((round(start, 2), round(dur, 2)))
            buf, saw, last_loud, start = 0, False, t, t
    return out


async def stream(frames):
    import websockets
    before = TRANSCRIPT.read_text(encoding="utf-8", errors="replace") if TRANSCRIPT.exists() else ""
    n_before = len(before.splitlines())
    t0 = time.time()
    async with websockets.connect(WS, max_size=None) as ws:
        for f in frames:
            await ws.send(f)
            await asyncio.sleep(FRAME_S)              # real-time pacing
        await asyncio.sleep(2.0)                       # let the final chunk land
    time.sleep(2.0)
    after = TRANSCRIPT.read_text(encoding="utf-8", errors="replace")
    new_lines = after.splitlines()[n_before:]
    return new_lines, time.time() - t0


def main():
    frames, flags = build_timeline()
    audio_s = sum(len(f) for f in frames) / 2 / RATE
    print(f"input: {audio_s:.1f}s of slow speech, {len(frames)} frames @ {FRAME_S*1000:.0f}ms "
          f"({sum(flags)} speech frames, {len(flags)-sum(flags)} quiet)\n")

    old = old_predicate(frames, flags)
    new = new_predicate(frames, flags)
    print(f"OLD predicate -> {len(old)} chunks: " + ", ".join(f"{d}s" for _, d in old))
    print(f"NEW predicate -> {len(new)} chunks: " + ", ".join(f"{d}s" for _, d in new))
    print()

    lines, elapsed = asyncio.run(stream(frames))
    print(f"LIVE transcript lines ({len(lines)} in {elapsed:.1f}s):")
    for ln in lines:
        text = ln.split("] ", 2)[-1] if "] " in ln else ln
        print(f"  [{len(text.split()):2d} words] {text}")
    if not lines:
        print("  ⚠️  none — check ~/.duckwork/meeting-transcript/pwa.err")
    return 0


if __name__ == "__main__":
    sys.exit(main())
