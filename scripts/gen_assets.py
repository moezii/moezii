"""Render the profile as a terminal UI with an integrated activity pane.

Edit profile.json for copy. Run `python scripts/gen_assets.py` to render.
Add --refresh-streaks to fetch the public streak provider used by the old README.
Only aggregate contribution counts and dates are saved. No token is required.
"""

import argparse
from datetime import date, datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import textwrap
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
MONO = "'JetBrains Mono', 'Cascadia Mono', Consolas, 'Liberation Mono', monospace"
BG, FG, MUTED, BORDER = "#303030", "#eeeeee", "#b3b3b3", "#b6b6b6"
GREEN, BLUE, CYAN, YELLOW, RED = "#b3cf77", "#3b78ae", "#81c2cb", "#e1ca6b", "#e9a3af"
HIGHLIGHTS = {
    "systems focus": GREEN, "full-stack": GREEN, "low-latency": CYAN,
    "concurrent event processing": GREEN, "distributed messaging": GREEN,
    "crypto networks": YELLOW, "parallel state-space search": GREEN,
    "scheduling": CYAN, "message ordering": CYAN, "backpressure": CYAN,
    "idempotency": CYAN, "UAV firmware": GREEN, "firmware": GREEN,
    "ground-control interfaces": CYAN, "video/telemetry relays": CYAN,
    "agentic harnesses": YELLOW, "Windows internals": RED,
    "privilege escalation": RED, "browser sandbox escapes": RED,
    "code-execution chains": RED, "WAF/parser differentials": YELLOW,
    "automated reconnaissance": CYAN,
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_stats(raw):
    if not isinstance(raw, dict) or raw.get("mode") != "daily":
        raise ValueError("Expected daily streak data; keeping the existing snapshot.")
    if type(raw.get("totalContributions")) is not int or raw["totalContributions"] < 0:
        raise ValueError("Invalid contribution total; keeping the existing snapshot.")
    result = {"mode": "daily", "totalContributions": raw["totalContributions"]}
    first = raw.get("firstContribution")
    result["firstContribution"] = date.fromisoformat(first).isoformat() if first else None
    for key in ("currentStreak", "longestStreak"):
        streak = raw.get(key)
        if not isinstance(streak, dict) or type(streak.get("length")) is not int or streak["length"] < 0:
            raise ValueError(f"Invalid {key}; keeping the existing snapshot.")
        result[key] = {"length": streak["length"]}
        for field in ("start", "end"):
            value = streak.get(field)
            result[key][field] = date.fromisoformat(value).isoformat() if value else None
        if result[key]["start"] and result[key]["end"] and result[key]["start"] > result[key]["end"]:
            raise ValueError(f"Invalid {key} dates; keeping the existing snapshot.")
    return result


def refresh_stats(profile):
    query = urlencode({"user": profile["username"], "type": "json", "timezone": profile["timezone"]})
    source = "https://streak-stats.demolab.com/?" + query
    request = Request(source, headers={"User-Agent": "github-profile-renderer/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        raw = json.load(response)
    snapshot = validate_stats(raw)
    snapshot["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    snapshot["source"] = source
    # Validate the entire response before replacing a working snapshot.
    ASSETS.mkdir(exist_ok=True)
    temporary = ASSETS / "streak.json.tmp"
    temporary.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    temporary.replace(ASSETS / "streak.json")
    return snapshot


def wrapped(paragraph, columns):
    return textwrap.wrap(paragraph, columns, break_long_words=False, break_on_hyphens=False)


def lines_count(paragraphs, columns):
    return sum(len(wrapped(p, columns)) for p in paragraphs) + max(0, len(paragraphs) - 1)


def highlighted(paragraph, line, offset):
    colors = [FG] * len(paragraph)
    for phrase, color in HIGHLIGHTS.items():
        start = paragraph.find(phrase)
        if start >= 0:
            colors[start:start + len(phrase)] = [color] * len(phrase)
    selected = colors[offset:offset + len(line)]
    pieces, left = [], 0
    for i in range(1, len(line) + 1):
        if i == len(line) or selected[i] != selected[left]:
            pieces.append(f'<tspan fill="{selected[left]}">{escape(line[left:i])}</tspan>')
            left = i
    return "".join(pieces)


def short_date(value):
    return date.fromisoformat(value).strftime("%d %b %Y").lstrip("0") if value else "—"


def streak_range(streak):
    start, end = streak.get("start"), streak.get("end")
    if not start or not end:
        return "no streak yet"
    if start == end:
        return short_date(start)
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    if a.year == b.year and a.month == b.month:
        return f"{a.day}–{b.day} {b:%b %Y}"
    return f"{a:%d %b} – {b:%d %b %Y}"


class Terminal:
    def __init__(self, width, height, static=False):
        self.width, self.height = width, height
        self.static = static
        self.defs, self.command_css = [], []
        self.command_index = 0
        self.parts = [f'<rect width="{width}" height="{height}" fill="{BG}"/>']

    def text(self, x, y, value, color=FG, size=14, weight=400, delay=None, extra=""):
        if value == "":
            return
        animation = f' class="reveal" style="animation-delay:{delay:.3f}s"' if delay is not None else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" '
            f'xml:space="preserve"{animation}{extra}>{escape(str(value))}</text>'
        )

    def panel(self, x, y, width, height, title, active=False):
        color = GREEN if active else BORDER
        self.parts.append(f'<g data-pane="{escape(title, quote=True)}" data-bounds="{x} {y} {width} {height}">')
        self.parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="4" fill="{BG}" stroke="{color}" stroke-width="1.2"/>')
        self.parts.append(f'<path d="M{x + 4} {y + 1}H{x + width - 4}Q{x + width - 1} {y + 1} {x + width - 1} {y + 4}V{y + 28}H{x + 1}V{y + 4}Q{x + 1} {y + 1} {x + 4} {y + 1}Z" fill="#262626"/>')
        self.parts.append(f'<path d="M{x + 1} {y + 28.5}H{x + width - 1}" stroke="{color}" stroke-opacity=".6"/>')
        self.text(x + 11, y + 19, ">_", GREEN if active else CYAN, 12, 600)
        self.text(x + 37, y + 19, title, GREEN if active else FG, 12, 600)
        controls = x + width - 49
        self.parts.append(
            f'<g aria-hidden="true" stroke="{MUTED}" stroke-width="1" fill="none">'
            f'<path d="M{controls} {y + 17}h7"/>'
            f'<rect x="{controls + 15}" y="{y + 11}" width="6" height="6"/>'
            f'<path d="M{controls + 31} {y + 11}l6 6m0 -6l-6 6"/></g>'
        )

    def close_panel(self):
        self.parts.append('</g>')

    def command(self, x, y, value, begin, size=13):
        self.command_index += 1
        identifier = f'command-{self.command_index}'
        extent = len(value) * size * .6
        duration = min(.55, len(value) * .035)
        self.text(x, y, "❯", GREEN, size, 600)
        start = x + 20
        self.defs.append(
            f'<clipPath id="{identifier}"><rect x="{start}" y="{y - size}" '
            f'width="{extent + 1}" height="{size + 5}" class="typed" '
            f'style="animation:type {duration:.3f}s steps({len(value)},end) {begin}s both"/></clipPath>'
        )
        self.text(start, y, value, FG, size,
                  extra=f' clip-path="url(#{identifier})" textLength="{extent}" lengthAdjust="spacingAndGlyphs"')
        self.command_css.append(
            f'@keyframes track-{identifier} {{ from {{ transform:translateX(0); }} to {{ transform:translateX({extent}px); }} }}'
        )
        self.parts.append(
            f'<g class="typing-cursor" opacity="0" style="animation:cursor-life {duration:.3f}s linear {begin}s">'
            f'<rect x="{start}" y="{y - size + 2}" width="7" height="{size + 1}" fill="{GREEN}" '
            f'style="animation:track-{identifier} {duration:.3f}s steps({len(value)},end) {begin}s both"/></g>'
        )

    def ready(self, x, y, delay, active=False):
        self.parts.append(f'<g class="reveal" style="animation-delay:{delay}s">')
        self.text(x, y, "~", CYAN, 12.5)
        self.text(x + 17, y, "❯", GREEN, 12.5, 600)
        self.parts.append(
            f'<rect class="caret" x="{x + 35}" y="{y - 11}" width="7" height="13" '
            f'fill="{GREEN if active else MUTED}" style="animation-delay:{delay % 1:.2f}s" aria-hidden="true"/>'
        )
        self.parts.append('</g>')

    def prose(self, x, y, paragraphs, columns, size, line_height, delay, gutter=False):
        row = 0
        for paragraph in paragraphs:
            offset = 0
            for line in wrapped(paragraph, columns):
                offset = paragraph.index(line, offset)
                if gutter:
                    self.text(x - 17, y, "+", GREEN, size, delay=delay + row * .035)
                content = highlighted(paragraph, line, offset)
                self.parts.append(
                    f'<text x="{x}" y="{y}" font-size="{size}" xml:space="preserve" '
                    f'class="reveal" style="animation-delay:{delay + row * .035:.3f}s">{content}</text>'
                )
                offset += len(line)
                y += line_height
                row += 1
            y += line_height
            row += 1
        return y - line_height

    def finish(self, description):
        css = """
          .reveal { animation: reveal .18s ease-out both; }
          @keyframes reveal { from { opacity: 0; transform: translateY(2px); } to { opacity: 1; transform: translateY(0); } }
          .selection { transform-box: fill-box; transform-origin: left; animation: select .45s cubic-bezier(.23,1,.32,1) both; }
          @keyframes select { from { transform: scaleX(0); } to { transform: scaleX(1); } }
          .caret { animation: blink 1.2s step-end infinite; }
          @keyframes blink { 50% { opacity: 0; } }
          .typed { transform-box: fill-box; transform-origin: left center; }
          @keyframes type { from { transform: scaleX(0); } to { transform: scaleX(1); } }
          @keyframes cursor-life { 0%, 99.9% { opacity: 1; } 100% { opacity: 0; } }
          @media (prefers-reduced-motion: reduce) {
            .reveal, .selection, .caret, .typed { animation: none !important; }
            .typing-cursor { display: none; }
          }
        """
        css += "\n".join(self.command_css)
        if self.static:
            css += ".reveal, .selection, .caret, .typed { animation: none !important; } .typing-cursor { display: none; }"
        return "\n".join([
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}" font-family="{escape(MONO, quote=True)}" '
            'role="img" aria-labelledby="title desc">',
            '<title id="title">Systems engineering, software, and security</title>',
            f'<desc id="desc">{escape(description)}</desc>',
            '<defs>' + ''.join(self.defs) + '</defs>',
            f'<style>{css}</style>', *self.parts, '</svg>', '',
        ])


def render(profile, stats, mobile=False, static=False):
    width = 380 if mobile else 920
    margin, gap = 12, 16
    inner_width = width - 2 * margin
    left_width, right_x = 274, 302
    right_width = width - margin - right_x
    font_size, line_height = (15, 21) if mobile else (15, 21)
    columns = 35 if mobile else 63
    about_height = 104 + lines_count(profile["about"], columns) * line_height
    research_height = 156 + lines_count(profile["research"], columns) * line_height
    stack_height = 92 + len(profile["stack"]) * 18
    status_height = 136
    focus_height = 94 + len(profile["focus"]) * 21

    if mobile:
        about_y = 16 + status_height + gap
        research_y = about_y + about_height + gap
        stack_y = research_y + research_height + gap
        activity_y = stack_y + stack_height + gap
        activity_height = 300
    else:
        about_y = 16
        research_y = about_y + about_height + gap
        stack_y = 16 + status_height + gap + focus_height + gap
        activity_y = max(research_y + research_height, stack_y + stack_height) + gap
        activity_height = 188
    height = activity_y + activity_height + 38
    terminal = Terminal(width, height, static)

    # Each pane is a separate shell window, with its own command and ready prompt.
    terminal.panel(margin, 16, inner_width if mobile else left_width, status_height, "[1] status")
    terminal.command(margin + 12, 16 + 52, "cat ~/.role", .05, 12.5)
    terminal.text(margin + 12, 16 + 78, profile["identity"], FG, 15, 600, .55)
    terminal.text(margin + 12, 16 + 100, "systems / full-stack", CYAN, 13.5, delay=.6)
    terminal.ready(margin + 12, 16 + status_height - 15, .84)
    terminal.close_panel()

    if not mobile:
        focus_y = 16 + status_height + gap
        terminal.panel(margin, focus_y, left_width, focus_height, "[2] focus", active=True)
        terminal.command(margin + 12, focus_y + 52, "cat focus.list", .1, 12.5)
        terminal.parts.append(f'<rect class="selection" x="{margin + 2}" y="{focus_y + 63}" width="{left_width - 4}" height="22" fill="{BLUE}" style="animation-delay:.58s"/>')
        for index, label in enumerate(profile["focus"]):
            terminal.text(margin + 12, focus_y + 78 + index * 21, ("❯ " if index == 0 else "  ") + label,
                          FG if index == 0 else MUTED, 13.5, delay=.65 + index * .035)
        terminal.ready(margin + 12, focus_y + focus_height - 15, 1.03, active=True)
        terminal.close_panel()

    x, pane_width = (margin, inner_width) if mobile else (right_x, right_width)
    terminal.panel(x, about_y, pane_width, about_height, "[0] profile")
    terminal.command(x + 13, about_y + 52, "cat profile.md", .2)
    terminal.prose(x + 14, about_y + 79, profile["about"], columns, font_size, line_height, .77)
    terminal.ready(x + 13, about_y + about_height - 15, 1.5)
    terminal.close_panel()

    terminal.panel(x, research_y, pane_width, research_height, "[4] research")
    terminal.command(x + 13, research_y + 52, "cat research.md", .3)
    end = terminal.prose(x + 14, research_y + 79, profile["research"], columns, font_size, line_height, .87)
    first = " · ".join(profile["research_tools"][:4])
    second = " · ".join(profile["research_tools"][4:])
    terminal.text(x + 13, end + 8, first, YELLOW, 12.5, delay=1.25)
    terminal.text(x + 13, end + 29, second, YELLOW, 12.5, delay=1.3)
    terminal.ready(x + 13, research_y + research_height - 15, 1.58)
    terminal.close_panel()

    sx, sw = (margin, inner_width) if mobile else (margin, left_width)
    terminal.panel(sx, stack_y, sw, stack_height, "[3] stack")
    terminal.command(sx + 12, stack_y + 52, "cat stack.list", .15, 12.5)
    for index, line in enumerate(profile["stack"]):
        terminal.text(sx + 12, stack_y + 78 + index * 18, line,
                      GREEN if index < 6 else FG, 13, delay=.7 + index * .025)
    terminal.ready(sx + 12, stack_y + stack_height - 15, 1.3)
    terminal.close_panel()

    # The streak is drawn in the same SVG and theme, not a separate card or disclosure.
    terminal.panel(margin, activity_y, inner_width, activity_height, "[5] activity")
    terminal.command(margin + 13, activity_y + 52, "streak --daily", .4)
    current, longest = stats["currentStreak"], stats["longestStreak"]
    first_contribution = stats.get("firstContribution")
    total_range = "since " + short_date(first_contribution) if first_contribution else "all time"
    cards = [
        (f'{stats["totalContributions"]:,}', "contributions", total_range),
        (str(current["length"]), "current streak / days", streak_range(current)),
        (str(longest["length"]), "longest streak / days", streak_range(longest)),
    ]
    if mobile:
        for index, (number, label, dates) in enumerate(cards):
            row_y = activity_y + 86 + index * 62
            terminal.text(margin + 17, row_y, number, GREEN, 24, 600, 1.4 + index * .08)
            terminal.text(margin + 115, row_y - 5, label, FG, 12.5, delay=1.4 + index * .08)
            terminal.text(margin + 115, row_y + 15, dates, MUTED, 11.5, delay=1.48 + index * .08)
    else:
        cell = inner_width / 3
        for index, (number, label, dates) in enumerate(cards):
            center = margin + cell * (index + .5)
            if index:
                terminal.parts.append(f'<path d="M{margin + cell * index} {activity_y + 68}v72" stroke="#5b5b5b"/>')
            terminal.text(center, activity_y + 93, number, GREEN, 27, 600, 1.4 + index * .08, ' text-anchor="middle"')
            terminal.text(center, activity_y + 117, label, FG, 12.5, delay=1.48 + index * .08, extra=' text-anchor="middle"')
            terminal.text(center, activity_y + 138, dates, MUTED, 11.5, delay=1.55 + index * .08, extra=' text-anchor="middle"')

    fetched = datetime.fromisoformat(stats["fetched_at"]).date()
    terminal.text(width - margin - 12, activity_y + activity_height - 12,
                  f"updated {fetched:%d %b %Y}", MUTED, 10.5, extra=' text-anchor="end"')
    terminal.ready(margin + 13, activity_y + activity_height - 15, 1.95)
    terminal.close_panel()
    terminal.text(margin + 2, height - 12, "systems · software · security" if mobile else "[1] Profile   [2] Focus   [3] Stack   [4] Research   [5] Activity", CYAN, 11)

    description = accessible_text(profile, stats)
    return terminal.finish(description)


def accessible_text(profile, stats):
    return (" ".join(profile["about"]) + " Research interests: " + " ".join(profile["research"])
            + " Tools: " + ", ".join(profile["research_tools"]) + ". Stack: "
            + "; ".join(line for line in profile["stack"] if line) + ". "
            + f'{stats["totalContributions"]:,} contributions, current streak {stats["currentStreak"]["length"]} days, '
            + f'longest streak {stats["longestStreak"]["length"]} days.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-streaks", action="store_true")
    args = parser.parse_args()
    profile = read_json(ROOT / "profile.json")
    if not re.fullmatch(r"[A-Za-z0-9-]+", profile["username"]):
        raise ValueError("Invalid GitHub username")
    stats = refresh_stats(profile) if args.refresh_streaks else read_json(ASSETS / "streak.json")
    validate_stats(stats)
    datetime.fromisoformat(stats["fetched_at"])
    ASSETS.mkdir(exist_ok=True)
    for mobile in (False, True):
        for static in (False, True):
            suffix = ("-mobile" if mobile else "") + ("-static" if static else "")
            destination = ASSETS / f"terminal{suffix}.svg"
            destination.write_text(render(profile, stats, mobile, static), encoding="utf-8", newline="\n")
            print(f"Wrote {destination.name}")
    alt = escape(accessible_text(profile, stats), quote=True)
    readme = f'''<picture>
  <source media="(prefers-reduced-motion: reduce) and (max-width: 600px)" srcset="./assets/terminal-mobile-static.svg" />
  <source media="(prefers-reduced-motion: reduce)" srcset="./assets/terminal-static.svg" />
  <source media="(max-width: 600px)" srcset="./assets/terminal-mobile.svg" />
  <img src="./assets/terminal.svg" width="100%" alt="{alt}" />
</picture>
'''
    (ROOT / "README.md").write_text(readme, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
