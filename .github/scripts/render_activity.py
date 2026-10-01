"""Render the activity panel in assets/activity.svg from AppleHealthData.svg.

The health data repository pushes AppleHealthData.svg, a heatmap with a square for every day
since 2021, and each square names its day in a <title> ("2026-09-30 周三 · 568 kcal"). This
reads the days back and draws them in the README's glass style at a third of the height: a row
per year and a square per week, colored by the week's daily average. The full heatmap stays
one click away.

    python3 .github/scripts/render_activity.py

The figures follow the full heatmap: windows end the day before the last day, which is still
in progress, and averages skip days without activity.
"""

import re
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from glass import MARGIN, MONO, ROW_WIDTH, SANS, background, defs, num, rim

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "AppleHealthData.svg"
OUT = ROOT / "assets" / "activity.svg"

DAY = re.compile(r"<title>(\d{4}-\d{2}-\d{2}) 周. · (?:([\d,]+) kcal|无记录)</title>")
WIDTH, RADIUS, PAD = ROW_WIDTH, 16, 22
ICON = 40
LABEL, TOTAL = 44, 46  # widths of the years on the left and their totals on the right
GAP, ROW_GAP = 2.2, 4.2  # between weeks, and a little more between years
# weekly averages sit between 300 and 800 kcal, so the steps are finer than the daily heatmap's
SHADES = [(400, "#5A2638"), (500, "#832E44"), (600, "#AC354F"), (700, "#D63C5A"), (None, "#FF4466")]
SMALL = 520  # below this rendered width (phones), drop the small print and enlarge the figures


def read_days(svg):
    days = {}
    for match in DAY.finditer(svg):
        value = match.group(2)
        days[date.fromisoformat(match.group(1))] = int(value.replace(",", "")) if value else 0
    if len(days) < 60:
        raise SystemExit("found too few days in AppleHealthData.svg; has its format changed?")
    return days


def active(days, end, length):
    """The values of the days with activity among the `length` days that end on `end`."""
    return [value for offset in range(length) if (value := days.get(end - timedelta(days=offset)))]


def average(values):
    return sum(values) / len(values) if values else 0


def figures(days):
    end = max(days) - timedelta(days=1)
    year, recent, before = active(days, end, 365), active(days, end, 30), active(days, end - timedelta(days=30), 30)
    best = max((day for day in days if end - timedelta(days=364) <= day <= end), key=days.get, default=end)
    trend = ""
    if recent and before:
        change = average(recent) / average(before) - 1
        trend = f"{'↑' if change >= 0 else '↓'}{abs(change):.0%}"
    return [
        ("近一年累计", sum(year), ""),
        ("近一年日均", round(average(year)), ""),
        ("近一年最高", days.get(best, 0), f"{best.month}月{best.day}日"),
        ("近 30 天日均", round(average(recent)), trend),
    ]


def shade(value):
    return next(color for limit, color in SHADES if limit is None or value < limit)


def week(day):
    """Weeks count from January 1st, so the columns line up across years."""
    return (day.timetuple().tm_yday - 1) // 7


def width(text, size):
    return sum(size if ord(char) > 0x2E80 else size * 0.6 for char in text)


def ring(x, y):
    """Apple Health's Move ring on a black tile."""
    center, radius, stroke = ICON / 2, ICON * 0.3, ICON * 0.15
    length = 2 * 3.14159 * radius
    return (
        f'<g transform="translate({x} {y})"><rect width="{ICON}" height="{ICON}" rx="{num(ICON * 0.24)}" filter="url(#lift)"/>'
        f'<rect x=".5" y=".5" width="{ICON - 1}" height="{ICON - 1}" rx="{num(ICON * 0.24 - 0.5)}" fill="none" stroke="#FFFFFF" stroke-opacity="0.12"/>'
        f'<circle cx="{center}" cy="{center}" r="{num(radius)}" fill="none" stroke="#FA114F" stroke-opacity="0.25" stroke-width="{num(stroke)}"/>'
        f'<circle cx="{center}" cy="{center}" r="{num(radius)}" fill="none" stroke="url(#move)" stroke-width="{num(stroke)}" '
        f'stroke-linecap="round" stroke-dasharray="{num(length * 0.82)} {num(length)}" transform="rotate(-90 {center} {center})"/></g>'
    )


def render(days):
    last = max(days)
    stats = figures(days)
    years = sorted({day.year for day in days}, reverse=True)
    left, top = MARGIN + PAD, MARGIN + PAD
    right = WIDTH - MARGIN - PAD
    parts = []

    # header: the ring, a title, and the day the data runs to
    stamp = f"截至 {last.month}月{last.day}日"
    stamp_width = width(stamp, 10.5) + 18
    parts.append(
        ring(left, top)
        + f'<text x="{left + ICON + 14}" y="{top + 18}" class="title">活动能量</text>'
        + f'<text x="{left + ICON + 14}" y="{top + 36}" class="sub wide">Apple 健康 · {years[-1]} 年起每天的活动消耗</text>'
        + f'<g class="wide"><rect x="{num(right - stamp_width)}" y="{top + 2}" width="{num(stamp_width)}" height="20" rx="10" '
        'fill="#FFFFFF" fill-opacity="0.06" stroke="#FFFFFF" stroke-opacity="0.18"/>'
        f'<text x="{num(right - stamp_width / 2)}" y="{top + 15.5}" text-anchor="middle" class="stamp">{stamp}</text></g>'
    )

    # four figures in columns split by hairlines
    y = top + ICON + 26
    column = (right - left) / 4
    for index, (label, value, note) in enumerate(stats):
        x = left + index * column + (16 if index else 0)
        if index:
            parts.append(f'<rect x="{num(left + index * column)}" y="{y - 2}" width="1" height="44" fill="#FFFFFF" fill-opacity="0.1"/>')
        parts.append(f'<text x="{num(x)}" y="{y + 10}" class="label">{label}</text>'
                     f'<text x="{num(x)}" y="{y + 38}" class="value">{value:,}<tspan class="unit wide"> kcal</tspan></text>')
        if note:
            parts.append(f'<text x="{num(left + (index + 1) * column - 4)}" y="{y + 10}" text-anchor="end" class="note wide">{note}</text>')

    # a row per year, a square per week; weeks that haven't come yet are left out
    grid_left = left + LABEL
    pitch = (right - left - LABEL - TOTAL) / 53
    cell = pitch - GAP
    y += 70
    parts.append("".join(
        f'<text x="{num(grid_left + week(date(2026, month, 1)) * pitch)}" y="{y}" class="axis wide">{month}月</text>'
        for month in range(1, 13)
    ))
    y += 9
    for row, year in enumerate(years):
        weeks = {}
        for day, value in days.items():
            if day.year == year:
                weeks.setdefault(week(day), []).append(value)
        top_of_row = y + row * (cell + ROW_GAP)
        cells = []
        for column_index, values in sorted(weeks.items()):
            values = [value for value in values if value]
            fill = f'fill="{shade(average(values))}"' if values else 'class="none"'
            cells.append(f'<rect x="{num(grid_left + column_index * pitch)}" y="{num(top_of_row)}" '
                         f'width="{num(cell)}" height="{num(cell)}" rx="2.4" {fill}/>')
        middle = top_of_row + cell / 2 + 3.8
        total = sum(value for day, value in days.items() if day.year == year)
        parts.append("".join(cells)
                     + f'<text x="{left}" y="{num(middle)}" class="year wide">{year}</text>'
                     + f'<text x="{right}" y="{num(middle)}" text-anchor="end" class="total wide">{total / 1000:.0f}k</text>')

    # legend
    y += len(years) * (cell + ROW_GAP) + 14
    bounds = [limit for limit, _ in SHADES[:-1]]
    steps = [f"< {bounds[0]}"] + [f"{low}–{high}" for low, high in zip(bounds, bounds[1:])] + [f"≥ {bounds[-1]}"]
    parts.append(f'<text x="{left}" y="{y}" class="axis wide">每周日均 kcal</text>')
    x = left + width("每周日均 kcal", 10.5) + 14
    for text, color in [("无记录", None)] + list(zip(steps, (color for _, color in SHADES))):
        fill = f'fill="{color}"' if color else 'class="none"'
        parts.append(f'<g class="wide"><rect x="{num(x)}" y="{y - 9}" width="10" height="10" rx="2.5" {fill}/>'
                     f'<text x="{num(x + 15)}" y="{y}" class="axis">{escape(text)}</text></g>')
        x += 15 + width(text, 10.5) + 14
    # the README links the panel to the full heatmap
    parts.append(f'<text x="{right}" y="{y}" text-anchor="end" class="axis wide">逐日热力图 ↗</text>')
    height = round(y + PAD - 4 + MARGIN)

    summary = "，".join(f"{label} {value:,} kcal" for label, value, _ in stats)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-label={quoteattr(f"活动能量：{summary}")}>
<title>活动能量：{escape(summary)}</title>
<defs>
{defs(WIDTH, height, RADIUS, ("#1B1A2E", "#0B0B14"), blur=38)}
<linearGradient id="move" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#E6004C"/><stop offset="1" stop-color="#FF4F7E"/></linearGradient>
<filter id="lift" x="-30%" y="-30%" width="160%" height="170%"><feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#000000" flood-opacity="0.35"/></filter>
<style>
text {{ font-family: {SANS}; fill: #FFFFFF; }}
.title {{ font-size: 19px; font-weight: 700; letter-spacing: -0.2px; }}
.sub {{ font-size: 12.5px; fill-opacity: 0.62; }}
.stamp {{ font-family: {MONO}; font-size: 10.5px; fill-opacity: 0.66; }}
.label {{ font-size: 12px; fill-opacity: 0.6; }}
.note {{ font-family: {MONO}; font-size: 10.5px; fill-opacity: 0.55; }}
.value {{ font-size: 22px; font-weight: 600; letter-spacing: -0.3px; }}
.unit {{ font-size: 12px; font-weight: 400; fill-opacity: 0.6; letter-spacing: 0; }}
.axis {{ font-size: 10.5px; fill-opacity: 0.5; }}
.year {{ font-family: {MONO}; font-size: 11px; font-weight: 600; fill-opacity: 0.85; }}
.total {{ font-family: {MONO}; font-size: 11px; fill-opacity: 0.5; }}
.none {{ fill: #FFFFFF; fill-opacity: 0.07; }}
@media (max-width: {SMALL}px) {{
  .wide {{ display: none; }}
  .title {{ font-size: 30px; }}
  .label {{ font-size: 20px; transform: translateY(-6px); }}
  .value {{ font-size: 34px; transform: translateY(10px); }}
}}
</style>
</defs>
{background(WIDTH, height, [("#FA114F", WIDTH - 40, -10, 150, 0.24), ("#6D5CF0", 30, height + 20, 170, 0.20)])}
{rim(WIDTH, height, RADIUS)}
{"".join(parts)}
</svg>
'''


def main():
    days = read_days(SOURCE.read_text(encoding="utf-8"))
    OUT.write_text(render(days), encoding="utf-8")
    print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
