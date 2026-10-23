"""Statistics aggregation and a small dependency-free SVG line chart.

Replaces the PHP ``libchart`` PNGs that were written into ``public_html`` on
every page view.
"""
from dataclasses import dataclass

from markupsafe import Markup, escape


@dataclass
class YearStats:
    year: int
    weeks: list          # [(week, starts, stops)] for every week 1..max_week
    starts: int
    stops: int


def yearly_stats(weekly):
    """Turn ``{year: {week: [starts, stops]}}`` into a list of ``YearStats`` (newest first)."""
    years = []
    for year in sorted(weekly, reverse=True):
        data = weekly[year]
        last_week = max(52, max(data))
        weeks = [(w, *data.get(w, (0, 0))) for w in range(1, last_week + 1)]
        years.append(YearStats(year, weeks, sum(s for _, s, _ in weeks), sum(e for _, _, e in weeks)))
    return years


def line_chart(series, labels, width=900, height=240, title=""):
    """Render *series* ``{name: [values]}`` over *labels* as inline SVG."""
    pad_l, pad_r, pad_t, pad_b = 40, 12, 28, 28
    plot_w, plot_h = width - pad_l - pad_r, height - pad_t - pad_b
    peak = max([1] + [v for values in series.values() for v in values])
    step = 1
    for candidate in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500):
        step = candidate
        if peak / candidate <= 5:
            break
    top = ((peak + step - 1) // step) * step
    n = max(1, len(labels) - 1)

    def x(i):
        return pad_l + plot_w * i / n

    def y(v):
        return pad_t + plot_h * (1 - v / top)

    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="{escape(title)}" xmlns="http://www.w3.org/2000/svg">']
    if title:
        parts.append(f'<text class="chart-title" x="{pad_l}" y="18">{escape(title)}</text>')
    for tick in range(0, top + 1, step):
        parts.append(f'<line class="grid" x1="{pad_l}" x2="{width - pad_r}" y1="{y(tick):.1f}" y2="{y(tick):.1f}"/>')
        parts.append(f'<text class="axis" x="{pad_l - 6}" y="{y(tick) + 4:.1f}" text-anchor="end">{tick}</text>')
    for i, label in enumerate(labels):
        if i % 4 == 0 or i == len(labels) - 1:
            parts.append(f'<text class="axis" x="{x(i):.1f}" y="{height - 8}" '
                         f'text-anchor="middle">{escape(label)}</text>')
    for idx, (name, values) in enumerate(series.items()):
        points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
        parts.append(f'<polyline class="series s{idx}" points="{points}"><title>{escape(name)}</title></polyline>')
        lx = width - pad_r - 110 * (len(series) - idx)
        parts.append(f'<rect class="legend s{idx}" x="{lx}" y="9" width="12" height="4"/>'
                     f'<text class="axis" x="{lx + 16}" y="16">{escape(name)}</text>')
    parts.append("</svg>")
    return Markup("".join(parts))
