"""The dark glass look shared by the README images.

The project cards, the terminal and the activity heatmap (rendered by the health data repository)
stack the same layers: a dark diagonal gradient, blurred color glows, a white sheen at the top and a
rim light along the edge. GitHub shows README images through <img>, which blocks anything an SVG
loads from elsewhere, so the images embed what they need and use only system fonts.
"""

# Transparent edge around every panel. Tiles side by side keep a gap, and since the cards row is
# four 206-wide tiles, a full-width panel drawn 824 wide lines up with the row's outer edges.
MARGIN = 3
ROW_WIDTH = 824

SANS = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", '
    '"Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans SC", "WenQuanYi Micro Hei", sans-serif'
)
MONO = (
    'ui-monospace, "SF Mono", SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", '
    '"DejaVu Sans Mono", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Noto Sans CJK SC", '
    '"Noto Sans SC", "WenQuanYi Micro Hei", monospace'
)


def defs(width, height, radius, base, blur=24):
    """Clip path, gradients and the glow filter; ids: panel, base, sheen, rim, glow."""
    inner_w, inner_h = width - 2 * MARGIN, height - 2 * MARGIN
    return (
        f'<clipPath id="panel"><rect x="{MARGIN}" y="{MARGIN}" width="{inner_w}" height="{inner_h}" rx="{radius}"/></clipPath>\n'
        f'<linearGradient id="base" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{base[0]}"/>'
        f'<stop offset="1" stop-color="{base[1]}"/></linearGradient>\n'
        # the sheen fades out over the same distance on every panel, however tall it is
        f'<linearGradient id="sheen" x1="0" y1="{MARGIN}" x2="0" y2="{MARGIN + 86}" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="#FFFFFF" stop-opacity="0.10"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>\n'
        '<linearGradient id="rim" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.34"/>'
        '<stop offset="0.5" stop-color="#FFFFFF" stop-opacity="0.10"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0.06"/></linearGradient>\n'
        f'<filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="{blur}"/></filter>'
    )


def background(width, height, glows, inner=""):
    """The panel's fill and glows, with anything in `inner` drawn under the sheen."""
    inner_w, inner_h = width - 2 * MARGIN, height - 2 * MARGIN
    lights = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" fill-opacity="{opacity}" filter="url(#glow)"/>'
        for color, cx, cy, r, opacity in glows
    )
    return (
        f'<g clip-path="url(#panel)">\n'
        f'<rect x="{MARGIN}" y="{MARGIN}" width="{inner_w}" height="{inner_h}" fill="url(#base)"/>\n'
        f"{lights}\n{inner}"
        f'<rect x="{MARGIN}" y="{MARGIN}" width="{inner_w}" height="{inner_h}" fill="url(#sheen)"/>\n'
        "</g>"
    )


def rim(width, height, radius):
    inner_w, inner_h = width - 2 * MARGIN, height - 2 * MARGIN
    return (
        f'<rect x="{MARGIN + 0.5}" y="{MARGIN + 0.5}" width="{inner_w - 1}" height="{inner_h - 1}" '
        f'rx="{radius - 0.5}" fill="none" stroke="url(#rim)"/>'
    )


def num(value):
    """Short decimal for SVG attributes."""
    return f"{value:.2f}".rstrip("0").rstrip(".")
