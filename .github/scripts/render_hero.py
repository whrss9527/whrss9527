"""Render the terminal at the top of the README into assets/hero.svg.

Run it again after changing the text or the stack:

    python3 .github/scripts/render_hero.py

When the image loads, the terminal types its commands and stops on the last frame; with reduced
motion it shows the last frame right away. Text sits on a fixed character grid (wide CJK characters
take two cells, as in a real terminal), so the layout doesn't depend on which monospace font the
viewer has. Rendered narrower than 520px (phones), the image switches to a shorter session with
larger text, since the full one would scale down past reading size.
"""

import json
import random
import unicodedata
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from glass import MARGIN, MONO, ROW_WIDTH, SANS, background, defs, num, rim

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "hero.svg"
# logos and brand colors from Simple Icons (CC0), keyed by their slugs
ICONS = json.loads(Path(__file__).with_name("stack_icons.json").read_text(encoding="utf-8"))

WIDTH = ROW_WIDTH
RADIUS = 16
BAR = 36  # title bar
PAD = 22
FS, LH = 13, 22  # font size and line height of the desktop session
SMALL, PHONE = 520, 1.95  # below this rendered width, show the phone session, scaled up this much

NAME = "了迹奇有没"
REVERSED = NAME[::-1]  # the name is 没有奇迹了 ("no more miracles") backwards
ABOUT = [
    ("服务端工程师，也给 Mac 做些顺手的小工具。", "out"),
    ("最近的四个都住在菜单栏里：原生 Swift，玻璃质感，开源免费。", "dim"),
]
# tree lists directories alphabetically, so these names keep the order
STACK = [
    ("lang", [("go", "Go"), ("kotlin", "Kotlin"), ("swift", "Swift"), ("openjdk", "Java"),
              ("python", "Python"), ("javascript", "JavaScript"), ("gnubash", "Shell")]),
    ("middleware", [("grpc", "gRPC"), ("mysql", "MySQL"), ("redis", "Redis"), ("apachekafka", "Kafka"),
                    ("sqs", "SQS"), ("mongodb", "MongoDB")]),
    ("ops", [("docker", "Docker"), ("nomad", "Nomad"), ("jenkins", "Jenkins"), ("kubernetes", "Kubernetes"),
             ("opentelemetry", "OpenTelemetry"), ("prometheus", "Prometheus")]),
    ("tools", [("git", "Git"), ("github", "GitHub"), ("gitlab", "GitLab"), ("obsidian", "Obsidian"),
               ("claude", "Claude")]),
]

# 16x16 bitmaps from GNU Unifont 15.1 (OFL-1.1 / GPL-2.0+ with the font embedding exception),
# one row of 16 pixels per four hex digits, the same layout as unifont.hex
GLYPHS = {
    "了": "00007FF800100020004001800100010001000100010001000100010005000200",
    "迹": "00402020102017FE00900090F294129214921110111012501420280047FE0000",
    "奇": "010001003FF8028004400820FFFE001000101F90109010901F90001000500020",
    "有": "02000200FFFE040004000FF0081018102FF0481088100FF00810081008500820",
    "没": "000021F01110111081104210540E180013F82208E108211020A0204021B00E0E",
}
PIXEL, GLYPH_GAP = 5, 12  # banner pixel size and the space between characters, desktop units

# Colors: the four apps' accents, so the terminal matches the cards below it
PROMPT, CHEVRON, COMMAND, STRING, DIRECTORY = "#22C3E6", "#C58BF2", "#4ADE80", "#F5C26B", "#6C9BFF"
INK = ["#22C3E6", "#5B7BFF", "#A66BF5", "#FA4D8C"]  # banner gradient, left to right
# brand colors too dark for the glass get a light stand-in
TINT = {"openjdk": "#F89820", "apachekafka": "#E8E8F0", "github": "#E8E8F0", "opentelemetry": "#F5A800",
        "mysql": "#5D9BD5", "python": "#5A9BD5", "grpc": "#3FB6B2", "sqs": "#FF9900"}


def cells(char):
    return 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1


def banner_path():
    """All lit pixels of the name as one path, at one unit per pixel."""
    squares, left = [], 0
    for char in NAME:
        bits = GLYPHS[char]
        for row in range(16):
            line = int(bits[row * 4:row * 4 + 4], 16)
            for col in range(16):
                if line & (0x8000 >> col):
                    squares.append(f"M{num(left + col + 0.08)} {num(row + 0.08)}h.84v.84h-.84z")
        left += 16 + GLYPH_GAP / PIXEL
    return "".join(squares), left - GLYPH_GAP / PIXEL


# Simple Icons has no gRPC or SQS logo, and the MySQL one carries its wordmark, which turns to
# mush at this size; these get simple drawings on the same 24-unit grid instead
STAND_INS = {
    "grpc": ('<g fill="none" stroke="{color}" stroke-width="2.4"><circle cx="5" cy="12" r="3"/><circle cx="19" cy="5" r="3"/>'
             '<circle cx="19" cy="19" r="3"/><path d="M7.7 10.7l8.6-4.4M7.7 13.3l8.6 4.4"/></g>'),  # linked nodes
    "sqs": ('<g fill="{color}"><rect x="1" y="7" width="5" height="10" rx="1.2"/><rect x="8" y="7" width="5" height="10" '
            'rx="1.2" opacity=".75"/><rect x="15" y="7" width="5" height="10" rx="1.2" opacity=".5"/>'
            '<path d="M21 9.5l3 2.5-3 2.5z"/></g>'),  # a queue
    "mysql": ('<g fill="none" stroke="{color}" stroke-width="2.2"><ellipse cx="12" cy="5" rx="8" ry="3"/>'
              '<path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/></g>'),  # a database
}


def icon(slug, x, y, size):
    color = TINT.get(slug) or "#" + ICONS[slug]["hex"]
    drawing = STAND_INS[slug].format(color=color) if slug in STAND_INS else f'<path fill="{color}" d="{ICONS[slug]["path"]}"/>'
    return f'<g transform="translate({num(x)} {num(y)}) scale({size / 24:.4f})">{drawing}</g>'


NAME_PATH, NAME_WIDTH = banner_path()


class Session:
    """One terminal session: lays out the lines and keeps the typing timeline."""

    def __init__(self, scale, top, seed):
        self.scale = scale
        self.fs, self.lh = FS * scale, LH * scale
        self.cw = self.fs * 0.6
        self.left = MARGIN + PAD * scale
        self.top = top  # top of the next line
        self.parts = []
        self.cursor = []  # (time, x, baseline)
        self.random = random.Random(seed)
        self.time = 0.15

    def baseline(self):
        return self.top + self.lh * 0.68

    def glyphs(self, x, text):
        """x of each character on the grid; wide characters are centered in their two cells."""
        xs = []
        for char in text:
            width = cells(char)
            xs.append(x + (self.fs * 0.1 if width == 2 else 0))
            x += width * self.cw
        return " ".join(num(value) for value in xs), x

    def appear(self, delay):
        return f'class="a" style="animation-delay:{delay:.2f}s"'

    def prompt(self, command, pause=0.32):
        """A prompt, then the command typed one key at a time."""
        y, x = self.baseline(), self.left
        shown = self.time
        keys = [f'<tspan class="prompt" x="{num(x)}">~</tspan>']
        x += 2 * self.cw  # "~ ", then a chevron drawn in the next cell, so every font gets the same one
        chevron = x + self.cw * 0.18, y - self.fs * 0.62, x + self.cw * 0.72, y - self.fs * 0.355, y - self.fs * 0.09
        x += 2 * self.cw
        self.cursor.append((shown, x, y))
        self.time += 0.38
        for text, kind in command:
            for char in text:
                self.time += 0.04 + self.random.random() * 0.06
                xs, x = self.glyphs(x, char)
                keys.append(f'<tspan class="{kind} a" x="{xs}" style="animation-delay:{self.time:.2f}s">{escape(char)}</tspan>')
                self.cursor.append((self.time, x, y))
        self.parts.append(
            f'<g {self.appear(shown)}><path class="chevron" style="stroke-width:{num(self.fs * 0.15)}px" '
            f'd="M{num(chevron[0])} {num(chevron[1])}L{num(chevron[2])} {num(chevron[3])}L{num(chevron[0])} {num(chevron[4])}"/>'
            f'<text y="{num(y)}">{"".join(keys)}</text></g>'
        )
        self.top += self.lh
        self.time += pause

    def output(self, text, kind, grid=True):
        """A line of output; prose can leave the grid so Chinese reads at its natural spacing."""
        xs = self.glyphs(self.left, text)[0] if grid else num(self.left)
        self.parts.append(f'<text {self.appear(self.time)} y="{num(self.baseline())}"><tspan class="{kind}" x="{xs}">{escape(text)}</tspan></text>')
        self.top += self.lh
        self.time += 0.05

    def banner(self):
        """The name in Unifont pixels, printed one pixel row at a time like any other output."""
        pixel = min(PIXEL * self.scale, (WIDTH - 2 * self.left) / NAME_WIDTH)
        y = self.top + self.lh * 0.3
        self.parts.append(
            f'<g {self.appear(self.time)}><g class="rows" style="animation-delay:{self.time:.2f}s">'
            f'<use href="#name" transform="translate({num(self.left)} {num(y)}) scale({num(pixel)})" filter="url(#bloom)" opacity="0.5"/>'
            f'<use href="#name" transform="translate({num(self.left)} {num(y)}) scale({num(pixel)})"/></g></g>'
        )
        self.top = y + 16 * pixel + self.lh * 0.45
        self.time += 0.45

    def tree(self):
        x = self.left
        rule = x + self.cw * 0.5
        top = self.top + self.lh * 0.08
        for index, (directory, items) in enumerate(STACK):
            y = self.baseline()
            middle = y - self.fs * 0.32
            last = index == len(STACK) - 1
            bottom = middle if last else self.top + self.lh + self.lh * 0.08
            branch = (f'<path class="branch" d="M{num(rule)} {num(top)}V{num(bottom)}'
                      f'M{num(rule)} {num(middle)}H{num(rule + self.cw * 2.3)}"/>')
            xs, _ = self.glyphs(x + self.cw * 4, directory + "/")
            texts = [f'<tspan class="directory" x="{xs}">{directory}/</tspan>']
            marks = []
            cursor = x + self.cw * 16.5
            size = self.fs * 0.92
            for slug, name in items:
                marks.append(icon(slug, cursor, y - self.fs * 0.82, size))
                xs, cursor = self.glyphs(cursor + size + self.cw * 0.75, name)
                texts.append(f'<tspan class="item" x="{xs}">{escape(name)}</tspan>')
                cursor += self.cw * 2.2
            self.parts.append(f'<g {self.appear(self.time)}>{branch}{"".join(marks)}<text y="{num(y)}">{"".join(texts)}</text></g>')
            top = self.top + self.lh + self.lh * 0.08
            self.top += self.lh
            self.time += 0.05
        files = sum(len(items) for _, items in STACK)
        self.output(f"{len(STACK)} directories, {files} files", "dim")

    def gap(self, size):
        self.top += size * self.scale

    def render(self, name):
        """The lines, and a block cursor that follows the typing and then blinks on the last prompt.

        The cursor moves with a CSS animation rather than SMIL, so it shares a clock with the text.
        """
        end = self.time
        lift = self.fs * 0.84
        frames = " ".join(
            f"{0 if index == 0 else 100 * time / end:.2f}% {{ transform: translate({num(x)}px, {num(y - lift)}px); }}"
            for index, (time, x, y) in enumerate(self.cursor)
        )
        _, x, y = self.cursor[-1]
        cursor = (
            f'<g class="{name}-caret" transform="translate({num(x)} {num(y - lift)})"><rect class="cursor" '
            f'width="{num(self.cw)}" height="{num(self.fs * 1.1)}" style="animation-delay:{end:.2f}s"/></g>'
        )
        css = f"@keyframes {name}-caret {{ {frames} }}\n  .{name}-caret {{ animation: {name}-caret {end:.2f}s step-end both; }}"
        return "".join(self.parts) + cursor, css


ECHO = [("echo", "command"), (" ", ""), (f'"{REVERSED}"', "string"), (" ", ""), ("|", "operator"),
        (" ", ""), ("rev", "command")]


def session(scale, bar, full, gap):
    """The whole session, or a short one with only the name and the first line about me."""
    terminal = Session(scale, MARGIN + bar + 12 * scale, seed=7)
    terminal.prompt(ECHO)
    terminal.banner()
    terminal.gap(gap)
    terminal.prompt([("whoami", "command")])
    for text, kind in ABOUT if full else ABOUT[:1]:
        terminal.output(text, kind, grid=False)
    if full:
        terminal.gap(gap)
        terminal.prompt([("tree", "command"), (" ", ""), ("~/stack", "path")])
        terminal.tree()
    terminal.gap(gap)
    terminal.prompt([], pause=0)
    return terminal


def title_bar(terminal, bar, height):
    """Traffic lights and a title with the window's size in characters, like Terminal.app's."""
    scale = bar / BAR
    columns = int((WIDTH - 2 * MARGIN - 2 * PAD * terminal.scale) / terminal.cw)
    rows = int((height - 2 * MARGIN - bar) / terminal.lh)
    lights = "".join(
        f'<circle cx="{num(MARGIN + (20 + 20 * index) * scale)}" cy="{num(MARGIN + bar / 2)}" r="{num(6 * scale)}" fill="{color}"/>'
        for index, color in enumerate(["#FF5F57", "#FEBC2E", "#28C840"])
    )
    return (
        f'<rect x="{MARGIN}" y="{num(MARGIN + bar)}" width="{WIDTH - 2 * MARGIN}" height="1" fill="#FFFFFF" fill-opacity="0.08"/>'
        f"{lights}"
        f'<text x="{WIDTH / 2}" y="{num(MARGIN + bar / 2 + 4.3 * scale)}" text-anchor="middle" class="title" '
        f'style="font-size:{num(12.5 * scale)}px">whrss — -zsh — {columns}×{rows}</text>'
    )


def render():
    big = session(1, BAR, full=True, gap=8)
    height = round(big.top + 14 + MARGIN)
    small = session(PHONE, BAR * 1.5, full=False, gap=0)
    assert small.top <= height - MARGIN - 6, "the phone session no longer fits"
    ink = "".join(f'<stop offset="{index / (len(INK) - 1):.2f}" stop-color="{color}"/>' for index, color in enumerate(INK))
    big_lines, big_caret = big.render("big")
    small_lines, small_caret = small.render("small")
    about = f"{NAME}（{REVERSED}倒过来）：{ABOUT[0][0]}"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label={quoteattr(about)}>
<title>{escape(about)}</title>
<defs>
{defs(WIDTH, height, RADIUS, ("#1B1A2E", "#0B0B14"), blur=38)}
<filter id="bloom" x="-10%" y="-30%" width="120%" height="160%"><feGaussianBlur stdDeviation="1.2"/></filter>
<linearGradient id="ink" x1="0" y1="0" x2="{num(NAME_WIDTH)}" y2="0" gradientUnits="userSpaceOnUse">{ink}</linearGradient>
<path id="name" fill="url(#ink)" d="{NAME_PATH}"/>
<style>
text {{ font-family: {MONO}; font-size: {FS}px; fill: #FFFFFF; white-space: pre; }}
.small text {{ font-size: {num(FS * small.scale)}px; }}
.title {{ font-family: {SANS}; font-weight: 500; fill-opacity: 0.5; }}
.prompt {{ fill: {PROMPT}; }}
.chevron {{ fill: none; stroke: {CHEVRON}; stroke-linecap: round; stroke-linejoin: round; }}
.command {{ fill: {COMMAND}; }}
.string {{ fill: {STRING}; }}
.operator {{ fill: {CHEVRON}; }}
.path {{ text-decoration: underline; }}
.out {{ fill-opacity: 0.92; }}
.dim {{ fill-opacity: 0.55; }}
.directory {{ fill: {DIRECTORY}; font-weight: 700; }}
.item {{ fill-opacity: 0.88; }}
.branch {{ fill: none; stroke: #FFFFFF; stroke-opacity: 0.25; }}
.cursor {{ fill: #FFFFFF; fill-opacity: 0.72; }}
.small {{ display: none; }}
@media (max-width: {SMALL}px) {{
  .big {{ display: none; }}
  .small {{ display: inline; }}
}}
@keyframes show {{ to {{ visibility: visible; }} }}
/* the banner's box is 16 pixel rows tall, so each 6.25% step reveals a row; the negative insets leave room for the bloom */
@keyframes rows {{ from {{ clip-path: inset(-12.5% -2% 100% -2%); }} to {{ clip-path: inset(-12.5% -2% -12.5% -2%); }} }}
@keyframes blink {{ 50% {{ fill-opacity: 0; }} }}
@media (prefers-reduced-motion: no-preference) {{
  .a {{ visibility: hidden; animation: show 1ms forwards; }}
  .rows {{ animation: rows 0.45s steps(18, end) both; }}
  .cursor {{ animation: blink 1.1s step-end infinite; }}
  {big_caret}
  {small_caret}
}}
</style>
</defs>
{background(WIDTH, height, [("#5B7BFF", 60, 40, 150, 0.22), ("#C58BF2", WIDTH - 140, 0, 130, 0.13), ("#22C3E6", WIDTH - 60, height, 170, 0.10)])}
{rim(WIDTH, height, RADIUS)}
<g class="big">
{title_bar(big, BAR, height)}
{big_lines}
</g>
<g class="small">
{title_bar(small, BAR * 1.5, height)}
{small_lines}
</g>
</svg>
'''


def main():
    OUT.write_text(render(), encoding="utf-8")
    print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
