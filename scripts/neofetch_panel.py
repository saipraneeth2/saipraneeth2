#!/usr/bin/env python3
"""Generate a neofetch-style terminal info panel as an SVG.

Usage:
    python scripts/neofetch_panel.py [output]

Default output: panel.svg

Standard library only — no dependencies.

Edit the INFO/USER_AT_HOST constants below to change the card contents.
The card uses the same palette as portrait.svg (#0a1220 background,
#7cc4ff ice-blue) and ends with a row of ANSI-style color blocks like a
real neofetch printout. A light staggered fade-in is applied via CSS; any
renderer that ignores CSS shows the finished card as a static image.
"""

from __future__ import annotations

import sys

# ---------------------------------------------------------------- theme ----
BG = "#0a1220"
BORDER = "#1c2f4d"
KEY = "#7cc4ff"      # ice blue — keys, user@host
VAL = "#d5e6fb"      # soft ice white — values
DIM = "#33507a"      # separator dashes
DOTS = ("#2b4a72", "#3f6ea6", "#7cc4ff")  # terminal chrome, theme-toned

# ANSI-style palette blocks (terminal colors, tuned for the dark theme).
ANSI = ("#16233d", "#ff6b81", "#69db7c", "#ffd43b",
        "#7cc4ff", "#b197fc", "#66d9e8", "#e7f0fb")

# -------------------------------------------------------------- contents ---
HEADER = "Sai Praneeth Medisetti"
INFO = [
    ("Role", "Business & Data Analyst"),
    ("Education", "MCIS, Colorado State University '26"),
    ("Stack", "SQL · Python · Power BI · Excel"),
    ("Focus", "dashboards, process improvement, decisions from messy data"),
    ("Portfolio", "saipraneeth2.github.io"),
    ("Status", "open to full-time roles"),
]

# ------------------------------------------------- monospace glyph metrics --
FONT_SIZE = 13
CHAR_W = 7.8         # 0.6em advance
LINE_H = 21
PAD_X = 24
TOP = 52             # first text baseline (below the chrome dots)

MONO_STACK = ("'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, "
              "'Courier New', monospace")


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg() -> str:
    header_len = len(HEADER)
    longest = max(
        [header_len] + [len(k) + 2 + len(v) for k, v in INFO]
    )
    svg_w = round(longest * CHAR_W + 2 * PAD_X)

    n_lines = 2 + len(INFO)                    # header + separator + info
    blocks_y = TOP + n_lines * LINE_H - 4      # a blank-ish gap, then blocks
    block_w, block_h, gap = 24, 14, 6
    svg_h = blocks_y + block_h + 24

    style = f"""
    text {{
      font-family: {MONO_STACK};
      font-size: {FONT_SIZE}px;
      white-space: pre;
    }}
    .f {{ animation: fadein 0.5s ease-out both; }}
    @keyframes fadein {{
      from {{ opacity: 0; }}
      to   {{ opacity: 1; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      .f {{ animation: none; }}
    }}
    """

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" '
        f'width="{svg_w}" height="{svg_h}" role="img" '
        f'aria-label="Terminal info panel for Sai Praneeth Medisetti: '
        f'Business and Data Analyst, MCIS Colorado State University 2026, '
        f'SQL Python Power BI Excel, open to full-time roles" '
        f'xml:space="preserve">',
        "<title>Sai Praneeth Medisetti — profile panel</title>",
        f"<style>{style}</style>",
        f'<rect x="0.5" y="0.5" width="{svg_w - 1}" height="{svg_h - 1}" '
        f'rx="10" fill="{BG}" stroke="{BORDER}"/>',
    ]

    # Terminal chrome dots (theme-toned, not the stoplight colors).
    for i, c in enumerate(DOTS):
        parts.append(f'<circle cx="{PAD_X + i * 18}" cy="22" r="5" fill="{c}"/>')

    def line(i: int, inner: str) -> str:
        y = TOP + i * LINE_H
        delay = round(0.1 + i * 0.12, 2)
        return (f'<text class="f" x="{PAD_X}" y="{y}" '
                f'style="animation-delay:{delay}s">{inner}</text>')

    # Header: full name in bold ice-blue
    parts.append(line(0,
        f'<tspan fill="{KEY}" font-weight="bold">{esc(HEADER)}</tspan>'))
    # ----------------
    parts.append(line(1, f'<tspan fill="{DIM}">{"-" * header_len}</tspan>'))
    # Key: value rows
    for i, (k, v) in enumerate(INFO, start=2):
        parts.append(line(i,
            f'<tspan fill="{KEY}" font-weight="bold">{esc(k)}:</tspan>'
            f'<tspan fill="{VAL}"> {esc(v)}</tspan>'))

    # ANSI-style color blocks, like the tail of a real neofetch.
    delay = round(0.1 + (len(INFO) + 2) * 0.12, 2)
    parts.append(f'<g class="f" style="animation-delay:{delay}s">')
    for i, c in enumerate(ANSI):
        x = PAD_X + i * (block_w + gap)
        parts.append(f'<rect x="{x}" y="{blocks_y}" width="{block_w}" '
                     f'height="{block_h}" rx="2" fill="{c}"/>')
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    output = sys.argv[1] if len(sys.argv) > 1 else "panel.svg"
    svg = build_svg()
    with open(output, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {output}: {len(svg):,} bytes")


if __name__ == "__main__":
    main()
