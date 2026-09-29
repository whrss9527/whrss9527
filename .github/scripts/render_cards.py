"""Render the project tiles in assets/cards from the icons in assets/icons.

Run it again after changing a tile's text or colors:

    python3 .github/scripts/render_cards.py

GitHub shows README images through <img>, which blocks anything an SVG loads from
elsewhere, so each tile embeds its icon and uses only system fonts. The README sizes
the tiles as a share of the page width to keep them in one row; when a tile ends up
narrower than 120px (phones), it keeps only its icon and name.
"""

import base64
import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ROOT = Path(__file__).resolve().parents[2]
ICONS = ROOT / "assets" / "icons"
CARDS = ROOT / "assets" / "cards"

WIDTH, HEIGHT = 206, 156
MARGIN = 3  # transparent edge, so tiles side by side keep a gap
RADIUS = 16
PAD = 16
ICON = 56  # visible size of the icon's rounded square
LEFT, TOP = MARGIN + PAD, MARGIN + PAD
RIGHT = WIDTH - MARGIN - PAD
NAME_Y, TAGLINE_Y = TOP + ICON + 31, TOP + ICON + 53  # baselines
FONTS = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", '
    '"Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei", sans-serif'
)


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
        tagline="一个开关，管好所有代理",
        platform="macOS 14+",
        base=("#10275A", "#081330"),
        glows=[("#2F6BEA", 28, 22, 70, 0.60), ("#22C55E", 200, 150, 70, 0.28)],
        motif="toggle",
    ),
]


def text_width(text, size):
    """Rough advance width; the platform label is centered, so small errors only shift the padding."""
    width = 0.0
    for char in text:
        if ord(char) > 0x2E80:
            width += 1.0
        elif char == " ":
            width += 0.3
        elif char.isupper():
            width += 0.66
        elif char.isdigit() or char in "+-":
            width += 0.6
        else:
            width += 0.54
    return width * size


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


def render(card):
    png = (ICONS / f"{card.slug}.png").read_bytes()
    box = ICON / opaque_bounds(png)
    icon_x, icon_y = LEFT - (box - ICON) / 2, TOP - (box - ICON) / 2
    icon = base64.b64encode(png).decode()

    glows = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" fill-opacity="{opacity}" filter="url(#glow)"/>'
        for color, cx, cy, r, opacity in card.glows
    )
    platform_width = text_width(card.platform, 9.5) + 14
    platform_x = RIGHT - platform_width
    tile_w, tile_h = WIDTH - 2 * MARGIN, HEIGHT - 2 * MARGIN

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label={quoteattr(f"{card.name}：{card.tagline}")}>
<title>{escape(card.name)} · {escape(card.tagline)}</title>
<defs>
<clipPath id="tile"><rect x="{MARGIN}" y="{MARGIN}" width="{tile_w}" height="{tile_h}" rx="{RADIUS}"/></clipPath>
<linearGradient id="base" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{card.base[0]}"/><stop offset="1" stop-color="{card.base[1]}"/></linearGradient>
<linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.10"/><stop offset="0.55" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
<linearGradient id="rim" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.34"/><stop offset="0.5" stop-color="#FFFFFF" stop-opacity="0.10"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0.06"/></linearGradient>
<filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="24"/></filter>
<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7"/></filter>
<filter id="lift" x="-30%" y="-30%" width="160%" height="170%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#000000" flood-opacity="0.35"/></filter>
<style>
text {{ font-family: {FONTS}; fill: #FFFFFF; }}
.name {{ font-size: 21px; font-weight: 700; letter-spacing: -0.2px; }}
.tagline {{ font-size: 12.5px; font-weight: 500; fill-opacity: 0.9; }}
.platform {{ font-size: 9.5px; font-weight: 500; fill-opacity: 0.66; }}
@media (max-width: 120px) {{
  .detail {{ display: none; }}
  .name {{ font-size: 30px; transform: translateY(18px); }}
}}
</style>
</defs>
<g clip-path="url(#tile)">
<rect x="{MARGIN}" y="{MARGIN}" width="{tile_w}" height="{tile_h}" fill="url(#base)"/>
{glows}
<g class="detail">{MOTIFS[card.motif]()}</g>
<rect x="{MARGIN}" y="{MARGIN}" width="{tile_w}" height="{tile_h}" fill="url(#sheen)"/>
</g>
<rect x="{MARGIN + 0.5}" y="{MARGIN + 0.5}" width="{tile_w - 1}" height="{tile_h - 1}" rx="{RADIUS - 0.5}" fill="none" stroke="url(#rim)"/>
<image x="{icon_x:.2f}" y="{icon_y:.2f}" width="{box:.2f}" height="{box:.2f}" filter="url(#lift)" href="data:image/png;base64,{icon}"/>
<text x="{LEFT}" y="{NAME_Y}" class="name">{escape(card.name)}</text>
<g class="detail">
<rect x="{platform_x:.1f}" y="{NAME_Y - 14.5}" width="{platform_width:.1f}" height="17" rx="8.5" fill="#FFFFFF" fill-opacity="0.07" stroke="#FFFFFF" stroke-opacity="0.2"/>
<text x="{platform_x + platform_width / 2:.1f}" y="{NAME_Y - 2.8}" text-anchor="middle" class="platform">{escape(card.platform)}</text>
<text x="{LEFT}" y="{TAGLINE_Y}" class="tagline">{escape(card.tagline)}</text>
</g>
</svg>
'''


def main():
    CARDS.mkdir(parents=True, exist_ok=True)
    for card in CARDS_DATA:
        (CARDS / f"{card.slug}.svg").write_text(render(card), encoding="utf-8")
        print(f"assets/cards/{card.slug}.svg")


if __name__ == "__main__":
    main()
