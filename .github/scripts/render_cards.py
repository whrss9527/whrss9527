"""Render the project tiles in assets/cards from the icons in assets/icons.

Run it again after changing a tile's text or colors:

    python3 .github/scripts/render_cards.py

Each tile shows its app's latest version from releases.json next to this script, which
update_releases.py refreshes before rendering the tiles again. The README sizes the
tiles at a quarter of the page width each, so the row spans the page in any window; when a
tile ends up narrower than 120px (phones), it keeps only its icon and name.
"""

import base64
import json
import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from glass import MARGIN, MONO, ROW_WIDTH, SANS, background, defs, rim

ROOT = Path(__file__).resolve().parents[2]
ICONS = ROOT / "assets" / "icons"
CARDS = ROOT / "assets" / "cards"
RELEASES = Path(__file__).with_name("releases.json")

WIDTH, HEIGHT = ROW_WIDTH // 4, 156
RADIUS = 16
PAD = 16
ICON = 56  # visible size of the icon's rounded square
LEFT, TOP = MARGIN + PAD, MARGIN + PAD
RIGHT = WIDTH - MARGIN - PAD
NAME_Y, TAGLINE_Y = TOP + ICON + 31, TOP + ICON + 53  # baselines
PILL = 9.5  # font size of the version in the pill


@dataclass
class Card:
    slug: str
    name: str
    tagline: str
    platform: str
    base: tuple  # top-left and bottom-right colors of the background
    glows: list  # (color, cx, cy, r, opacity)
    motif: str


CARDS_DATA = [
    Card(
        slug="pop",
        name="Pop",
        tagline="长按右键，一划即达",
        platform="macOS 15+",
        base=("#1D1A5C", "#0E0C2C"),
        glows=[("#5B7BFF", 28, 22, 70, 0.55), ("#8B5CF6", 200, 150, 80, 0.45)],
        motif="ring",
    ),
    Card(
        slug="meno",
        name="Meno",
        tagline="安静的菜单栏，由玻璃打造",
        platform="macOS 14+",
        base=("#1C1747", "#0C1630"),
        glows=[("#6D5CF0", 28, 22, 70, 0.55), ("#22C3E6", 20, 160, 70, 0.30), ("#C58BF2", 206, 0, 70, 0.35)],
        motif="glass",
    ),
    Card(
        slug="stox",
        name="Stox",
        tagline="一眼看盘，一键隐身",
        platform="macOS 13+",
        base=("#1A1E30", "#0A0C14"),
        glows=[("#FA4D45", 185, 35, 70, 0.26), ("#3B4A7A", 28, 22, 70, 0.45)],
        motif="chart",
    ),
    Card(
        slug="proxi",
        name="Proxi",
        tagline="开发者的代理开关",
        platform="macOS 14+",
        base=("#10275A", "#081330"),
        glows=[("#2F6BEA", 28, 22, 70, 0.60), ("#22C55E", 200, 150, 70, 0.28)],
        motif="toggle",
    ),
]


def opaque_bounds(png):
    """Width of the opaque area of an 8-bit RGBA PNG, as a fraction of the canvas.

    The icons ship with different margins around their rounded square, so this keeps them the same size.
    """
    offset, idat = 8, b""
    while offset < len(png):
        length = struct.unpack(">I", png[offset:offset + 4])[0]
        kind = png[offset + 4:offset + 8]
        chunk = png[offset + 8:offset + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            idat += chunk
        offset += 12 + length
    if depth != 8 or color != 6 or interlace:
        return 0.8  # the macOS icon grid
    raw, stride = zlib.decompress(idat), width * 4
    previous, position, left, right = bytearray(stride), 0, width, -1
    for _ in range(height):
        kind = raw[position]
        line = bytearray(raw[position + 1:position + 1 + stride])
        position += 1 + stride
        for x in range(stride):
            a = line[x - 4] if x >= 4 else 0
            b = previous[x]
            c = previous[x - 4] if x >= 4 else 0
            if kind == 1:
                line[x] = (line[x] + a) & 255
            elif kind == 2:
                line[x] = (line[x] + b) & 255
            elif kind == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        for x in range(width):
            if line[x * 4 + 3] > 200:
                left, right = min(left, x), max(right, x)
        previous = line
    return (right - left + 1) / width


# The motifs sit in the top right corner, next to the icon, and run off the edge.

def ring_motif():
    """The ring menu from Pop's icon."""
    cx, cy, outer, inner, parts = 194, 40, 54, 33, 10
    shapes = []
    for index in range(parts):
        start = math.radians(-90 - 180 / parts + index * 360 / parts + 2.5)
        end = math.radians(-90 + 180 / parts + index * 360 / parts - 2.5)
        points = [
            (cx + outer * math.cos(start), cy + outer * math.sin(start)),
            (cx + outer * math.cos(end), cy + outer * math.sin(end)),
            (cx + inner * math.cos(end), cy + inner * math.sin(end)),
            (cx + inner * math.cos(start), cy + inner * math.sin(start)),
        ]
        path = (
            f"M{points[0][0]:.1f},{points[0][1]:.1f} A{outer},{outer} 0 0 1 {points[1][0]:.1f},{points[1][1]:.1f} "
            f"L{points[2][0]:.1f},{points[2][1]:.1f} A{inner},{inner} 0 0 0 {points[3][0]:.1f},{points[3][1]:.1f} Z"
        )
        # light up the segment pointing down and left, the way a swipe selects one in Pop
        opacity = 0.16 if index == 7 else 0.06
        shapes.append(f'<path d="{path}" fill="#FFFFFF" fill-opacity="{opacity}"/>')
    shapes.append(f'<circle cx="{cx}" cy="{cy}" r="12" fill="none" stroke="#FFFFFF" stroke-opacity="0.10" stroke-width="6"/>')
    return "".join(shapes)


def glass_motif():
    """Meno's glass pill with its level bars."""
    return (
        '<rect x="124" y="24" width="110" height="42" rx="21" fill="#FFFFFF" fill-opacity="0.07" '
        'stroke="#FFFFFF" stroke-opacity="0.16"/>'
        '<rect x="144" y="39" width="5" height="12" rx="2.5" fill="#FFFFFF" fill-opacity="0.16"/>'
        '<rect x="155" y="35.5" width="5" height="19" rx="2.5" fill="#FFFFFF" fill-opacity="0.2"/>'
        '<rect x="166" y="32" width="5" height="26" rx="2.5" fill="#FFFFFF" fill-opacity="0.28"/>'
    )


def chart_motif():
    """Stox's rising line over a faint grid."""
    values = [0.28, 0.40, 0.34, 0.52, 0.45, 0.63, 0.57, 0.76]
    left, right, top, bottom = 124, 186, 26, 62
    points = [
        (left + (right - left) * i / (len(values) - 1), bottom - (bottom - top) * (v - 0.28) / 0.48)
        for i, v in enumerate(values)
    ]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    grid = "".join(
        f'<line x1="112" y1="{y}" x2="{WIDTH - MARGIN}" y2="{y}" stroke="#FFFFFF" stroke-opacity="0.07"/>' for y in (26, 44, 62)
    )
    end_x, end_y = points[-1]
    return (
        grid
        + f'<polyline points="{line}" fill="none" stroke="#FA4D45" stroke-opacity="0.85" stroke-width="2.5" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        + f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="7" fill="#FA4D45" fill-opacity="0.2"/>'
        + f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="3.2" fill="#FA4D45"/>'
    )


def toggle_motif():
    """Proxi's switch, turned on."""
    return (
        '<rect x="122" y="23" width="110" height="44" rx="22" fill="#FFFFFF" fill-opacity="0.08" '
        'stroke="#FFFFFF" stroke-opacity="0.18"/>'
        '<circle cx="182" cy="45" r="24" fill="#22C55E" fill-opacity="0.2" filter="url(#soft)"/>'
        '<circle cx="182" cy="45" r="15" fill="#22C55E" fill-opacity="0.5"/>'
        '<circle cx="182" cy="45" r="15" fill="none" stroke="#FFFFFF" stroke-opacity="0.24"/>'
    )


MOTIFS = {"ring": ring_motif, "glass": glass_motif, "chart": chart_motif, "toggle": toggle_motif}


def render(card, version):
    png = (ICONS / f"{card.slug}.png").read_bytes()
    box = ICON / opaque_bounds(png)
    icon_x, icon_y = LEFT - (box - ICON) / 2, TOP - (box - ICON) / 2
    icon = base64.b64encode(png).decode()

    # the version is set in a monospace font, ~0.6em per character; centered, so a font
    # with narrower digits only shifts the padding
    label = version or card.platform
    pill_width = len(label) * PILL * 0.6 + 14
    pill_x = RIGHT - pill_width

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label={quoteattr(f"{card.name}：{card.tagline}")}>
<title>{escape(card.name)} · {escape(card.tagline)}</title>
<defs>
{defs(WIDTH, HEIGHT, RADIUS, card.base)}
<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7"/></filter>
<filter id="lift" x="-30%" y="-30%" width="160%" height="170%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#000000" flood-opacity="0.35"/></filter>
<style>
text {{ font-family: {SANS}; fill: #FFFFFF; }}
.name {{ font-size: 21px; font-weight: 700; letter-spacing: -0.2px; }}
.tagline {{ font-size: 12.5px; font-weight: 500; fill-opacity: 0.9; }}
.version {{ font-family: {MONO}; font-size: {PILL}px; font-weight: 500; fill-opacity: 0.72; }}
@media (max-width: 120px) {{
  .detail {{ display: none; }}
  .name {{ font-size: 30px; transform: translateY(18px); }}
}}
</style>
</defs>
{background(WIDTH, HEIGHT, card.glows, inner=f'<g class="detail">{MOTIFS[card.motif]()}</g>')}
{rim(WIDTH, HEIGHT, RADIUS)}
<image x="{icon_x:.2f}" y="{icon_y:.2f}" width="{box:.2f}" height="{box:.2f}" filter="url(#lift)" href="data:image/png;base64,{icon}"/>
<text x="{LEFT}" y="{NAME_Y}" class="name">{escape(card.name)}</text>
<g class="detail">
<rect x="{pill_x:.1f}" y="{NAME_Y - 14.5}" width="{pill_width:.1f}" height="17" rx="8.5" fill="#FFFFFF" fill-opacity="0.07" stroke="#FFFFFF" stroke-opacity="0.2"/>
<text x="{pill_x + pill_width / 2:.1f}" y="{NAME_Y - 2.9}" text-anchor="middle" class="version">{escape(label)}</text>
<text x="{LEFT}" y="{TAGLINE_Y}" class="tagline">{escape(card.tagline)}</text>
</g>
</svg>
'''


def main():
    releases = json.loads(RELEASES.read_text(encoding="utf-8")) if RELEASES.exists() else {}
    CARDS.mkdir(parents=True, exist_ok=True)
    for card in CARDS_DATA:
        (CARDS / f"{card.slug}.svg").write_text(render(card, releases.get(card.slug)), encoding="utf-8")
        print(f"assets/cards/{card.slug}.svg")


if __name__ == "__main__":
    main()
