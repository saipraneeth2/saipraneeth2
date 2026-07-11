#!/usr/bin/env python3
"""Generate an animated terminal-style ASCII portrait SVG from a photo.

Usage:
    python scripts/ascii_portrait.py [photo] [output] [--width N] [--invert]

Defaults:
    photo  = photo.jpg
    output = portrait.svg
    width  = 60 characters

Only third-party dependency: Pillow  (pip install Pillow)

How it works:
  1. The photo is converted to grayscale, auto-contrasted, and downsampled
     to ~60 columns (rows are scaled by the monospace glyph aspect ratio).
  2. Each pixel's luminance is mapped onto a dark-background character ramp
     (dim pixel -> blank space, bright pixel -> dense glyph).
  3. The lines are wrapped in an SVG that "types" itself top-to-bottom using
     CSS keyframes (a left-to-right clip-path reveal per line, staggered),
     with a blinking block cursor on a final prompt line.

Graceful degradation: every <text> element is visible by default. The
animation only *temporarily hides* lines via clip-path keyframes, so any
renderer that ignores CSS (static rasterizers, RSS readers, reduced-motion
users) simply shows the finished portrait.
"""

from __future__ import annotations

import argparse
import sys

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required. Install it with:  pip install Pillow")

# ---------------------------------------------------------------- theme ----
BG = "#0a1220"      # near-black navy (portfolio theme)
FG = "#7cc4ff"      # ice blue
BORDER = "#1c2f4d"  # subtle frame stroke

# Luminance ramp for DARK backgrounds: darkest -> ' ', brightest -> '@'.
# (No XML-special characters, so lines embed safely in SVG.)
CHARSET = " .':;i+=*x%#@"

# ------------------------------------------------- monospace glyph metrics --
FONT_SIZE = 10
CHAR_W = 6.0        # 0.6em advance — true for effectively all monospace fonts
LINE_H = 11
PAD = 16

MONO_STACK = ("'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, "
              "'Courier New', monospace")


def image_to_ascii(path: str, width: int, invert: bool) -> list[str]:
    """Convert an image file to a list of equal-width ASCII lines."""
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)   # honor phone-camera rotation
    img = img.convert("L")               # grayscale luminance
    if invert:
        img = ImageOps.invert(img)       # for photos on light backgrounds
    img = ImageOps.autocontrast(img, cutoff=1)

    w, h = img.size
    # Monospace glyphs are taller than wide; scale rows so proportions hold.
    rows = max(1, round((h / w) * width * (CHAR_W / LINE_H)))
    img = img.resize((width, rows), Image.LANCZOS)

    data = list(img.getdata())
    top = len(CHARSET) - 1
    lines = []
    for y in range(rows):
        row = data[y * width:(y + 1) * width]
        lines.append("".join(CHARSET[(p * top) // 255] for p in row))
    return lines


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(lines: list[str], width: int) -> str:
    rows = len(lines)
    text_w = width * CHAR_W
    svg_w = round(text_w + 2 * PAD)
    svg_h = PAD + rows * LINE_H + LINE_H + PAD  # extra line for the cursor

    # Typing choreography: each line reveals left-to-right; lines start
    # top-to-bottom on a stagger. Total reveal ~2.7s.
    per_line = 0.45
    stagger = max(0.03, round(2.2 / max(rows, 1), 3))

    style = f"""
    text {{
      font-family: {MONO_STACK};
      font-size: {FONT_SIZE}px;
      fill: {FG};
      white-space: pre;
    }}
    .r {{ animation: type {per_line}s steps(24, end) both; }}
    #cur {{ fill: {FG}; animation: blink 1.2s infinite; }}
    @keyframes type {{
      from {{ clip-path: inset(-2px 100% -2px -2px); }}
      to   {{ clip-path: inset(-2px -2px -2px -2px); }}
    }}
    @keyframes blink {{
      0%, 49% {{ opacity: 1; }}
      50%, 100% {{ opacity: 0; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .r, #cur {{ animation: none; }}
    }}
    """

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" '
        f'width="{svg_w}" height="{svg_h}" role="img" '
        f'aria-label="ASCII art portrait of Sai Praneeth Medisetti" '
        f'xml:space="preserve">',
        "<title>ASCII portrait — Sai Praneeth Medisetti</title>",
        f"<style>{style}</style>",
        f'<rect x="0.5" y="0.5" width="{svg_w - 1}" height="{svg_h - 1}" '
        f'rx="10" fill="{BG}" stroke="{BORDER}"/>',
    ]

    for i, line in enumerate(lines):
        content = esc(line.rstrip())
        if not content:
            continue  # fully dark row: background already shows it
        y = PAD + i * LINE_H + FONT_SIZE - 1
        delay = round(0.15 + i * stagger, 3)
        parts.append(
            f'<text class="r" x="{PAD}" y="{y}" '
            f'style="animation-delay:{delay}s">{content}</text>'
        )

    # Blinking block cursor on a fresh prompt line under the portrait.
    cur_y = PAD + rows * LINE_H + 1
    parts.append(
        f'<rect id="cur" x="{PAD}" y="{cur_y}" '
        f'width="{CHAR_W:g}" height="{FONT_SIZE}"/>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("photo", nargs="?", default="photo.jpg",
                    help="input photo (default: photo.jpg)")
    ap.add_argument("output", nargs="?", default="portrait.svg",
                    help="output SVG (default: portrait.svg)")
    ap.add_argument("--width", type=int, default=60,
                    help="ASCII columns (default: 60)")
    ap.add_argument("--invert", action="store_true",
                    help="invert luminance (use for photos on light backgrounds)")
    args = ap.parse_args()

    try:
        lines = image_to_ascii(args.photo, args.width, args.invert)
    except FileNotFoundError:
        sys.exit(f"Photo not found: {args.photo!r} — put your photo next to "
                 "the repo root or pass a path.")

    svg = build_svg(lines, args.width)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {args.output}: {args.width}x{len(lines)} chars, "
          f"{len(svg):,} bytes")


if __name__ == "__main__":
    main()
