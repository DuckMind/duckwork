#!/usr/bin/env python3
"""Generate the meeting-copilot PWA icon: a dark tile with the abbreviation
"REC" centered and well letter-spaced, in the app's accent green."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BG = (11, 11, 15, 255)        # #0b0b0f — dark, matches the app chrome
ACCENT = (124, 231, 135, 255) # tailwind-ish accent green (matches RECORD)


def _font(size):
    for fname in ("/System/Library/Fonts/Helvetica.ttc",
                  "/System/Library/Fonts/SFNS.ttf",
                  "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(fname, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_icon(size):
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)
    text = "REC"
    font = _font(int(size * 0.20))
    # letter-spacing: ~35% tighter than the prior pass, still readable
    tracking = int(size * 0.091)
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = (size - total) / 2
    ascent, descent = font.getmetrics()
    y = (size - (ascent + descent)) / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=font, fill=ACCENT)
        x += w + tracking
    return img


for px in (192, 512):
    img = draw_icon(px)
    out = Path(__file__).resolve().parent / "static" / f"icon-{px}.png"
    img.save(out)
    print(f"wrote icon-{px}.png")
