#!/usr/bin/env python3
"""Cross-source echo suppression for the meeting-mode transcript.

The same room audio can reach two capture sources at once — the phone PWA
(which lands first; it's faster) and the Mac's mic/BlackHole. Each daemon
transcribes independently and appends to the SAME rolling.txt, so without a
gate you get two near-identical lines for every utterance.

Rule (preference = phone, per the principal):
    - a `phone` line is never suppressed;
    - a non-phone line (mic/audio/untagged) that near-duplicates a line already
      in the recent tail is suppressed (it's an echo of what already landed).

`similar()` uses difflib ratio on normalized text: same audio transcribed
twice yields slightly different wordings, and a ratio threshold absorbs that
variance while leaving genuinely new speech alone. Lines shorter than
`MIN_CHARS` are never compared (short words like "ok" repeat legitimately and
would over-suppress).
"""
import difflib
import re
import os

MIN_CHARS = 8          # ignore very short utterances for dedupe
RATIO = 0.55           # difflib similarity above which two lines are "the same"
TAIL_LINES = 10        # how many recent lines to compare against

_TAG_RE = re.compile(r"\[\d\d:\d\d:\d\d\]\s*(?:\[(\w+)\]\s*)?(.*)")


def _normalize(text):
    return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split()


def _line_text(line):
    m = _TAG_RE.match(line)
    return m.group(2) if m else line


def _line_tag(line):
    m = _TAG_RE.match(line)
    return (m.group(1) or "") if m else ""


def similar(a, b):
    ta = _normalize(a)
    tb = _normalize(b)
    if len(ta) < 3 or len(tb) < 3:
        return False
    return difflib.SequenceMatcher(None, ta, tb).ratio() >= RATIO


def should_suppress(text, tag, rolling_path):
    """True if `text` (with source `tag`) is an echo and must NOT be appended.

    `rolling_path` = path to the shared rolling transcript; its recent tail is
    the comparison set (both daemons read it, so state is shared via disk).
    """
    if tag == "phone":
        return False  # preferred source wins unconditionally
    if len((text or "").strip()) < MIN_CHARS:
        return False
    try:
        with open(rolling_path, encoding="utf-8", errors="replace") as f:
            tail = f.read().splitlines()[-TAIL_LINES:]
    except OSError:
        return False
    for line in tail:
        if similar(_line_text(line), text):
            return True
    return False


def rolling_tail(rolling_path, n=TAIL_LINES):
    try:
        with open(rolling_path, encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()[-n:]
    except OSError:
        return []
