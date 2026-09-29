"""Render the project cards in assets/cards from the icons in assets/icons.

Run it again after changing a card's text or colors:

    python3 .github/scripts/render_cards.py

GitHub shows README images through <img>, which blocks anything an SVG loads from
elsewhere, so each card embeds its icon and uses only system fonts.
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

WIDTH, HEIGHT, RADIUS = 400, 206, 18
PAD = 24
ICON = 64  # visible size of the icon's rounded square
DESCRIPTION_Y = 128  # baseline
CHIP_TOP, CHIP_HEIGHT = 152.5, 27
FONTS = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", '
    '"Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei", sans-serif'
)


@dataclass
class Card:
    slug: str
    name: str
    tagline: str
    description: str
    chips: list
    platform: str
    base: tuple  # top-left and bottom-right colors of the background
    glows: list  # (color, cx, cy, r, opacity)
    motif: str


CARDS_DATA = [
    Card(
        slug="pop",
        name="Pop",
        tagline="长按右键，一划即达",
        description="选中外文即翻译，算式、颜色、图片直接出结果",
        chips=["离线翻译", "20+ 内置功能", "自定义插件"],
        platform="macOS 15+",
        base=("#1D1A5C", "#0E0C2C"),
        glows=[("#5B7BFF", 40, 30, 110, 0.55), ("#8B5CF6", 380, 220, 130, 0.45)],
        motif="ring",
    ),
    Card(
        slug="meno",
        name="Meno",
        tagline="安静的菜单栏，由玻璃打造",
        description="收起不常用的图标，点按、悬停或轻扫即可唤回",
        chips=["快速打开", "规则与场景", "禅模式"],
        platform="macOS 14+",
        base=("#1C1747", "#0C1630"),
        glows=[("#6D5CF0", 40, 30, 110, 0.55), ("#22C3E6", 30, 230, 110, 0.30), ("#C58BF2", 400, 0, 110, 0.35)],
        motif="glass",
    ),
    Card(
        slug="stox",
        name="Stox",
        tagline="一眼看盘，一键隐身",
        description="A 股、港股、美股行情，压缩包不到 1 MB",
        chips=["价格提醒", "iCloud 同步", "一键更新"],
        platform="macOS 13+",
        base=("#1A1E30", "#0A0C14"),
        glows=[("#FA4D45", 360, 50, 110, 0.26), ("#3B4A7A", 40, 30, 110, 0.45)],
        motif="chart",
    ),
    Card(
        slug="proxi",
        name="Proxi",
        tagline="一个开关，管好所有代理",
        description="系统代理、环境变量、git、npm，一键切换",
        chips=["节点与分流", "增强模式", "MCP 自动化"],
        platform="macOS 14+",
        base=("#10275A", "#081330"),
        glows=[("#2F6BEA", 40, 30, 110, 0.60), ("#22C55E", 390, 210, 110, 0.28)],
        motif="toggle",
    ),
]


def text_width(text, size):
    """Rough advance width; chip labels are centered, so small errors only shift the padding."""
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


def ring_motif():
    """The ring menu from Pop's icon, cropped by the right edge."""
    cx, cy, outer, inner, parts = 380, 104, 96, 58, 10
    shapes = []
    for index in range(parts):
        start = math.radians(-90 - 180 / parts + index * 360 / parts + 2.2)
        end = math.radians(-90 + 180 / parts + index * 360 / parts - 2.2)
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
        # light up the segment pointing up and left, the way a swipe selects one in Pop
        opacity = 0.15 if index == 8 else 0.05
        shapes.append(f'<path d="{path}" fill="#FFFFFF" fill-opacity="{opacity}"/>')
    shapes.append(f'<circle cx="{cx}" cy="{cy}" r="20" fill="none" stroke="#FFFFFF" stroke-opacity="0.09" stroke-width="9"/>')
    return "".join(shapes)


def glass_motif():
    """Meno's glass pill with its level bars."""
    return (
        '<rect x="318" y="58" width="150" height="60" rx="30" fill="#FFFFFF" fill-opacity="0.06" '
        'stroke="#FFFFFF" stroke-opacity="0.14"/>'
        '<rect x="344" y="79" width="7" height="18" rx="3.5" fill="#FFFFFF" fill-opacity="0.13"/>'
        '<rect x="359" y="74" width="7" height="28" rx="3.5" fill="#FFFFFF" fill-opacity="0.17"/>'
        '<rect x="374" y="69" width="7" height="38" rx="3.5" fill="#FFFFFF" fill-opacity="0.24"/>'
    )


def chart_motif():
    """Stox's rising line over a faint grid."""
    values = [0.28, 0.40, 0.34, 0.52, 0.45, 0.63, 0.57, 0.76]
    left, right, top, bottom = 300, 384, 60, 104
    points = [
        (left + (right - left) * i / (len(values) - 1), bottom - (bottom - top) * (v - 0.28) / 0.48)
        for i, v in enumerate(values)
    ]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    grid = "".join(
        f'<line x1="288" y1="{y}" x2="400" y2="{y}" stroke="#FFFFFF" stroke-opacity="0.06"/>' for y in (60, 82, 104)
    )
    return (
        grid
        + f'<polyline points="{line}" fill="none" stroke="#FA4D45" stroke-opacity="0.8" stroke-width="3" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
        + f'<circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="9" fill="#FA4D45" fill-opacity="0.18"/>'
        + f'<circle cx="{points[-1][0]:.1f}" cy="{points[-1][1]:.1f}" r="4" fill="#FA4D45"/>'
    )


def toggle_motif():
    """Proxi's switch, turned on."""
    return (
        '<rect x="306" y="54" width="150" height="56" rx="28" fill="#FFFFFF" fill-opacity="0.07" '
        'stroke="#FFFFFF" stroke-opacity="0.16"/>'
        '<circle cx="384" cy="82" r="32" fill="#22C55E" fill-opacity="0.18" filter="url(#soft)"/>'
        '<circle cx="384" cy="82" r="20" fill="#22C55E" fill-opacity="0.42"/>'
        '<circle cx="384" cy="82" r="20" fill="none" stroke="#FFFFFF" stroke-opacity="0.22"/>'
    )


MOTIFS = {"ring": ring_motif, "glass": glass_motif, "chart": chart_motif, "toggle": toggle_motif}


def render(card):
    png = (ICONS / f"{card.slug}.png").read_bytes()
    coverage = opaque_bounds(png)
    box = ICON / coverage
    icon_x = icon_y = PAD - (box - ICON) / 2
    icon = base64.b64encode(png).decode()

    glows = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" fill-opacity="{opacity}" filter="url(#glow)"/>'
        for color, cx, cy, r, opacity in card.glows
    )

    name_x = PAD + ICON + 16
    chip_middle = CHIP_TOP + CHIP_HEIGHT / 2
    chips, x = [], PAD
    for label in card.chips:
        width = text_width(label, 12) + 24
        chips.append(
            f'<rect x="{x:.1f}" y="{CHIP_TOP}" width="{width:.1f}" height="{CHIP_HEIGHT}" rx="{CHIP_HEIGHT / 2}" '
            f'fill="#FFFFFF" fill-opacity="0.08" stroke="#FFFFFF" stroke-opacity="0.16"/>'
            f'<text x="{x + width / 2:.1f}" y="{chip_middle + 4.5}" text-anchor="middle" class="chip">{escape(label)}</text>'
        )
        x += width + 8
    arrow_x, arrow_r = WIDTH - PAD - CHIP_HEIGHT / 2, CHIP_HEIGHT / 2

    platform_width = text_width(card.platform, 11) + 20
    platform_x = WIDTH - PAD - platform_width

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label={quoteattr(f"{card.name}：{card.tagline}")}>
<title>{escape(card.name)} · {escape(card.tagline)}</title>
<defs>
<clipPath id="card"><rect width="{WIDTH}" height="{HEIGHT}" rx="{RADIUS}"/></clipPath>
<linearGradient id="base" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{card.base[0]}"/><stop offset="1" stop-color="{card.base[1]}"/></linearGradient>
<linearGradient id="sheen" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.10"/><stop offset="0.55" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>
<linearGradient id="rim" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.34"/><stop offset="0.5" stop-color="#FFFFFF" stop-opacity="0.10"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0.06"/></linearGradient>
<filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="38"/></filter>
<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>
<filter id="lift" x="-30%" y="-30%" width="160%" height="170%"><feDropShadow dx="0" dy="6" stdDeviation="7" flood-color="#000000" flood-opacity="0.35"/></filter>
<style>
text {{ font-family: {FONTS}; fill: #FFFFFF; }}
.name {{ font-size: 26px; font-weight: 700; letter-spacing: -0.3px; }}
.tagline {{ font-size: 15px; font-weight: 500; fill-opacity: 0.92; }}
.description {{ font-size: 13px; fill-opacity: 0.68; }}
.chip {{ font-size: 12px; font-weight: 500; fill-opacity: 0.88; }}
.platform {{ font-size: 11px; font-weight: 500; fill-opacity: 0.62; letter-spacing: 0.2px; }}
</style>
</defs>
<g clip-path="url(#card)">
<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#base)"/>
{glows}
{MOTIFS[card.motif]()}
<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#sheen)"/>
</g>
<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="{RADIUS - 0.5}" fill="none" stroke="url(#rim)"/>
<image x="{icon_x:.2f}" y="{icon_y:.2f}" width="{box:.2f}" height="{box:.2f}" filter="url(#lift)" href="data:image/png;base64,{icon}"/>
<text x="{name_x}" y="{PAD + 27}" class="name">{escape(card.name)}</text>
<text x="{name_x}" y="{PAD + 53}" class="tagline">{escape(card.tagline)}</text>
<rect x="{platform_x:.1f}" y="{PAD + 0.5}" width="{platform_width:.1f}" height="22" rx="11" fill="#FFFFFF" fill-opacity="0.06" stroke="#FFFFFF" stroke-opacity="0.18"/>
<text x="{platform_x + platform_width / 2:.1f}" y="{PAD + 15.5}" text-anchor="middle" class="platform">{escape(card.platform)}</text>
<text x="{PAD}" y="{DESCRIPTION_Y}" class="description">{escape(card.description)}</text>
{"".join(chips)}
<circle cx="{arrow_x}" cy="{chip_middle}" r="{arrow_r}" fill="#FFFFFF" fill-opacity="0.10" stroke="#FFFFFF" stroke-opacity="0.18"/>
<path d="M{arrow_x - 4},{chip_middle + 4} L{arrow_x + 4},{chip_middle - 4} M{arrow_x - 2},{chip_middle - 4} L{arrow_x + 4},{chip_middle - 4} L{arrow_x + 4},{chip_middle + 2}" fill="none" stroke="#FFFFFF" stroke-opacity="0.9" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
'''


def main():
    CARDS.mkdir(parents=True, exist_ok=True)
    for card in CARDS_DATA:
        (CARDS / f"{card.slug}.svg").write_text(render(card), encoding="utf-8")
        print(f"assets/cards/{card.slug}.svg")


if __name__ == "__main__":
    main()
