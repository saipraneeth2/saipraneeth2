#!/usr/bin/env python3
"""Generate metrics.svg: a 13-week commit calendar + language breakdown.

Usage:
    python scripts/metrics_card.py [username] [output]

Defaults: saipraneeth2 -> metrics.svg

Standard library only — no dependencies, no external services.

Data sources (public GitHub REST API):
  * /users/{user}/events/public  — push events from the last ~90 days
    (this is everything GitHub exposes without a personal access token)
  * /repos/{user}/{repo}/languages — byte counts per language, non-fork repos

Auth: reads the GITHUB_TOKEN env var if present (GitHub Actions provides
one automatically) for a higher rate limit; also works unauthenticated for
local runs. On any API failure the script exits non-zero WITHOUT writing,
so a previously committed metrics.svg is never clobbered with bad data.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
WEEKS = 13

# ---------------------------------------------------------------- theme ----
BG = "#0a1220"
BORDER = "#1c2f4d"
FG = "#7cc4ff"
VAL = "#d5e6fb"
MUTED = "#5c7ea8"
SUB = "#8fb6dd"
TRACK = "#16233d"
RAMP = ("#16233d", "#274a73", "#3f6ea6", "#5d9ad4", "#7cc4ff")  # 0 -> max

# GitHub linguist colors for common languages; anything else falls back to FG.
LANG_COLORS = {
    "Python": "#3572A5", "Swift": "#F05138", "HTML": "#e34c26",
    "CSS": "#563d7c", "JavaScript": "#f1e05a", "TypeScript": "#3178c6",
    "Jupyter Notebook": "#DA5B0B", "Shell": "#89e051", "R": "#198CE7",
    "SCSS": "#c6538c", "Java": "#b07219", "C++": "#f34b7d", "SQL": "#e38c00",
}

MONO_STACK = ("'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, "
              "'Courier New', monospace")

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Denver")   # Fort Collins
except Exception:                     # pragma: no cover
    TZ = dt.timezone.utc


def gh_get(url: str):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-metrics-card",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_daily_commits(user: str) -> dict[dt.date, int]:
    """Commits per local date, from public PushEvents (~90-day window)."""
    counts: dict[dt.date, int] = {}
    for page in range(1, 4):  # events API caps at 300 events / 90 days
        try:
            events = gh_get(
                f"{API}/users/{user}/events/public?per_page=100&page={page}")
        except urllib.error.HTTPError as e:
            if e.code in (404, 422):
                break  # past the pagination window
            raise
        if not events:
            break
        for ev in events:
            if ev.get("type") != "PushEvent":
                continue
            when = dt.datetime.fromisoformat(
                ev["created_at"].replace("Z", "+00:00")).astimezone(TZ).date()
            payload = ev.get("payload", {})
            n = (payload.get("distinct_size")
                 or payload.get("size")
                 or len(payload.get("commits", [])))
            counts[when] = counts.get(when, 0) + int(n)
    return counts


def fetch_languages(user: str) -> list[tuple[str, int]]:
    """Aggregate language bytes across the user's non-fork public repos."""
    totals: dict[str, int] = {}
    repos = gh_get(f"{API}/users/{user}/repos?per_page=100&type=owner")
    for repo in repos:
        if repo.get("fork"):
            continue
        try:
            langs = gh_get(repo["languages_url"])
        except urllib.error.HTTPError:
            continue  # e.g. empty repo
        for lang, size in langs.items():
            totals[lang] = totals.get(lang, 0) + int(size)
    return sorted(totals.items(), key=lambda kv: kv[1], reverse=True)


def render(user: str, commits: dict[dt.date, int],
           languages: list[tuple[str, int]], today: dt.date) -> str:
    W, H, pad = 840, 248, 24
    cell, step = 14, 18

    # Grid columns are Sunday-started weeks, ending with the current week.
    last_sunday = today - dt.timedelta(days=(today.weekday() + 1) % 7)
    sundays = [last_sunday - dt.timedelta(weeks=k)
               for k in range(WEEKS - 1, -1, -1)]

    total = sum(n for d, n in commits.items() if d >= sundays[0])
    this_week = sum(n for d, n in commits.items() if d >= last_sunday)
    peak = max((commits.get(sun + dt.timedelta(days=r), 0)
                for sun in sundays for r in range(7)), default=0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        f'aria-label="Commit calendar for the last {WEEKS} weeks and '
        f'language breakdown for {user}">',
        f"<title>{user} — public push activity, last {WEEKS} weeks</title>",
        f'<style>text{{font-family:{MONO_STACK};}}</style>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" '
        f'fill="{BG}" stroke="{BORDER}"/>',
        # Header
        f'<text x="{pad}" y="36" font-size="14" font-weight="bold" '
        f'fill="{FG}">{user} — public push activity</text>',
        f'<text x="{W - pad}" y="36" text-anchor="end" font-size="10" '
        f'fill="{MUTED}">updated {today.isoformat()}</text>',
    ]

    if total > 0:
        subtitle = (f"this week: {this_week} commit"
                    f"{'s' if this_week != 1 else ''} · "
                    f"last {WEEKS} weeks: {total}")
    else:
        subtitle = f"no public push events in the last {WEEKS} weeks"
    parts.append(f'<text x="{pad}" y="56" font-size="12" '
                 f'fill="{SUB}">{subtitle}</text>')

    # ---- commit grid (left) -------------------------------------------
    gx, gy = 52, 92
    parts.append(f'<g font-size="9" fill="{MUTED}">')
    for label, row in (("M", 1), ("W", 3), ("F", 5)):
        parts.append(f'<text x="{pad}" y="{gy + row * step + 10}">{label}</text>')
    parts.append("</g>")

    prev_month = None
    for c, sun in enumerate(sundays):
        if sun.month != prev_month:
            parts.append(f'<text x="{gx + c * step}" y="{gy - 8}" '
                         f'font-size="9" fill="{MUTED}">'
                         f'{sun.strftime("%b")}</text>')
            prev_month = sun.month
        for r in range(7):
            day = sun + dt.timedelta(days=r)
            if day > today:
                continue
            n = commits.get(day, 0)
            if n <= 0:
                color = RAMP[0]
            else:
                level = max(1, min(4, round(n / peak * 4))) if peak else 1
                color = RAMP[level]
            parts.append(
                f'<rect x="{gx + c * step}" y="{gy + r * step}" '
                f'width="{cell}" height="{cell}" rx="3" fill="{color}">'
                f'<title>{day.isoformat()}: {n} commit'
                f'{"s" if n != 1 else ""}</title></rect>')

    # Legend
    ly = gy + 7 * step + 12
    parts.append(f'<text x="{gx}" y="{ly + 9}" font-size="9" '
                 f'fill="{MUTED}">less</text>')
    for i, color in enumerate(RAMP):
        parts.append(f'<rect x="{gx + 30 + i * 14}" y="{ly}" width="10" '
                     f'height="10" rx="2" fill="{color}"/>')
    parts.append(f'<text x="{gx + 30 + len(RAMP) * 14 + 4}" y="{ly + 9}" '
                 f'font-size="9" fill="{MUTED}">more</text>')

    # ---- languages (right) --------------------------------------------
    lx, lw = 330, 320
    parts.append(f'<text x="{lx}" y="{gy - 8}" font-size="11" '
                 f'fill="{MUTED}">languages · public repos by bytes</text>')
    lang_total = sum(size for _, size in languages) or 1
    if languages:
        for i, (lang, size) in enumerate(languages[:5]):
            y = gy + 10 + i * 25
            pct = size / lang_total * 100
            fill_w = max(3, round(size / lang_total * lw))
            color = LANG_COLORS.get(lang, FG)
            parts.append(f'<text x="{lx}" y="{y + 9}" font-size="11" '
                         f'fill="{VAL}">{lang[:16]}</text>')
            parts.append(f'<rect x="{lx + 120}" y="{y}" width="{lw}" '
                         f'height="11" rx="5" fill="{TRACK}"/>')
            parts.append(f'<rect x="{lx + 120}" y="{y}" width="{fill_w}" '
                         f'height="11" rx="5" fill="{color}"/>')
            parts.append(f'<text x="{lx + 120 + lw + 8}" y="{y + 9}" '
                         f'font-size="10" fill="{SUB}">{pct:.1f}%</text>')
    else:
        parts.append(f'<text x="{lx}" y="{gy + 20}" font-size="11" '
                     f'fill="{SUB}">no public language data yet</text>')

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    user = sys.argv[1] if len(sys.argv) > 1 else "saipraneeth2"
    output = sys.argv[2] if len(sys.argv) > 2 else "metrics.svg"
    try:
        commits = fetch_daily_commits(user)
        languages = fetch_languages(user)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        sys.exit(f"GitHub API request failed ({e}); keeping the previous "
                 f"{output} untouched.")
    today = dt.datetime.now(TZ).date()
    svg = render(user, commits, languages, today)
    with open(output, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Wrote {output}: {sum(commits.values())} commits mapped, "
          f"{len(languages)} languages, {len(svg):,} bytes")


if __name__ == "__main__":
    main()
