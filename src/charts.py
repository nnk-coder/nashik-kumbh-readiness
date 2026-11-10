"""Hand-rolled inline SVG charts. No library, no build step, no CDN.

Colours come from CSS custom properties defined in docs/assets/style.css, so
every chart follows the page into dark mode without a second palette here.
"""

from __future__ import annotations

import html
import math
from typing import Sequence


def _na(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def _nice_ticks(lo: float, hi: float, count: int = 4) -> list[float]:
    """Round axis values a human would choose."""
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / count
    mag = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        step = mag * mult
        if raw <= step:
            break
    start = math.floor(lo / step) * step
    ticks, v = [], start
    while v <= hi + step * 0.5:
        if v >= lo - step * 0.01:
            ticks.append(round(v, 10))
        v += step
    return ticks


def line_chart(
    labels: Sequence[str],
    values: Sequence[float | None],
    *,
    width: int = 720,
    height: int = 300,
    colour: str = "var(--series-1)",
    fill: bool = True,
    y_suffix: str = "",
    y_decimals: int = 2,
    annotations: Sequence[dict] = (),
    aria: str = "time series",
) -> str:
    """One series over time, with axes, gridlines and optional callouts.

    `annotations` entries: {"index": int, "text": str, "side": "above"|"below"}
    """
    pts = [(i, float(v)) for i, v in enumerate(values) if not _na(v)]
    if len(pts) < 2:
        return "<p class='na'>Not enough observations to plot.</p>"

    pad_l, pad_r, pad_t, pad_b = 58, 18, 26, 42
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    ys = [v for _, v in pts]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or 1.0
    lo, hi = lo - span * 0.12, hi + span * 0.18
    ticks = _nice_ticks(lo, hi)
    lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])

    n = len(labels) - 1 or 1

    def px(i: float) -> float:
        return pad_l + i / n * plot_w

    def py(v: float) -> float:
        return pad_t + plot_h - (v - lo) / (hi - lo) * plot_h

    parts = [
        f"<svg class='chart' viewBox='0 0 {width} {height}' "
        f"preserveAspectRatio='xMidYMid meet' role='img' "
        f"aria-label='{html.escape(aria)}'>"
    ]

    for t in ticks:
        y = py(t)
        parts.append(
            f"<line class='grid' x1='{pad_l}' y1='{y:.1f}' "
            f"x2='{width - pad_r}' y2='{y:.1f}'/>"
        )
        parts.append(
            f"<text class='tick' x='{pad_l - 10}' y='{y + 4:.1f}' "
            f"text-anchor='end'>{t:,.{y_decimals}f}{html.escape(y_suffix)}</text>"
        )

    step = max(1, len(labels) // 6)
    for i in range(0, len(labels), step):
        parts.append(
            f"<text class='tick' x='{px(i):.1f}' y='{height - pad_b + 22}' "
            f"text-anchor='middle'>{html.escape(str(labels[i]))}</text>"
        )

    line = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in pts)
    if fill:
        base = pad_t + plot_h
        area = (
            f"{px(pts[0][0]):.1f},{base:.1f} {line} "
            f"{px(pts[-1][0]):.1f},{base:.1f}"
        )
        parts.append(
            f"<polygon points='{area}' fill='{colour}' opacity='0.12'/>"
        )
    parts.append(
        f"<polyline points='{line}' fill='none' stroke='{colour}' "
        f"stroke-width='2.5' stroke-linejoin='round' stroke-linecap='round'/>"
    )

    for a in annotations:
        i = a["index"]
        match = next((v for j, v in pts if j == i), None)
        if match is None:
            continue
        x, y = px(i), py(match)
        above = a.get("side", "above") == "above"
        ty = y - 18 if above else y + 30
        anchor = "start" if i < n * 0.6 else "end"
        tx = x + 10 if anchor == "start" else x - 10
        parts.append(
            f"<line class='callout' x1='{x:.1f}' y1='{y:.1f}' "
            f"x2='{x:.1f}' y2='{ty + (8 if above else -8):.1f}'/>"
        )
        parts.append(
            f"<circle cx='{x:.1f}' cy='{y:.1f}' r='5' fill='{colour}' "
            f"stroke='var(--bg)' stroke-width='2'/>"
        )
        parts.append(
            f"<text class='callout-text' x='{tx:.1f}' y='{ty:.1f}' "
            f"text-anchor='{anchor}'>{html.escape(a['text'])}</text>"
        )

    parts.append("</svg>")
    return "".join(parts)


def weight_bars(weights: dict, fired: dict | None = None, width: int = 720) -> str:
    """The risk score's composition as proportional bars."""
    total = sum(weights.values()) or 1
    rows, y = [], 0
    row_h, gap = 46, 10
    height = len(weights) * (row_h + gap)
    for key, w in weights.items():
        on = bool((fired or {}).get(key))
        bar_w = w / total * (width - 300)
        label = key.replace("_", " ").capitalize()
        cls = "wbar on" if on else "wbar"
        rows.append(
            f"<rect class='{cls}' x='240' y='{y + 10}' width='{bar_w:.1f}' "
            f"height='{row_h - 20}' rx='5'/>"
            f"<text class='wlabel' x='230' y='{y + row_h / 2 + 5}' "
            f"text-anchor='end'>{html.escape(label)}</text>"
            f"<text class='wval' x='{250 + bar_w:.1f}' "
            f"y='{y + row_h / 2 + 5}'>{w:.0f}</text>"
        )
        y += row_h + gap
    return (
        f"<svg class='chart' viewBox='0 0 {width} {height}' "
        f"preserveAspectRatio='xMidYMid meet' role='img' "
        f"aria-label='weights making up the risk score'>{''.join(rows)}</svg>"
    )


def completeness_ring(fraction: float, size: int = 92) -> str:
    """A small dial: how much of the rubric was actually resolved."""
    frac = max(0.0, min(1.0, float(fraction or 0.0)))
    r = size / 2 - 8
    circ = 2 * math.pi * r
    dash = circ * frac
    cx = cy = size / 2
    return (
        f"<svg class='ring' viewBox='0 0 {size} {size}' width='{size}' "
        f"height='{size}' role='img' aria-label='{frac:.0%} of checks resolved'>"
        f"<circle cx='{cx}' cy='{cy}' r='{r}' class='ring-track'/>"
        f"<circle cx='{cx}' cy='{cy}' r='{r}' class='ring-fill' "
        f"stroke-dasharray='{dash:.1f} {circ - dash:.1f}' "
        f"transform='rotate(-90 {cx} {cy})'/>"
        f"<text x='{cx}' y='{cy + 6}' text-anchor='middle' "
        f"class='ring-text'>{frac:.0%}</text></svg>"
    )


def grouped_bars(
    labels: Sequence[str],
    series: Sequence[dict],
    *,
    width: int = 760,
    height: int = 330,
    value_fmt: str = "{:,.0f}",
    aria: str = "comparison by category",
) -> str:
    """Two or three measures side by side for each category.

    `series` entries: {"name", "values", "colour"}.
    """
    if not labels or not series:
        return "<p class='na'>Nothing to plot.</p>"
    pad_l, pad_r, pad_t, pad_b = 16, 16, 40, 62
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    all_vals = [float(v) for s in series for v in s["values"] if not _na(v)]
    hi = max(all_vals) if all_vals else 1.0
    hi = hi * 1.18 or 1.0

    n_cat = len(labels)
    group_w = plot_w / n_cat
    bar_w = min(46.0, (group_w * 0.68) / len(series))
    parts = [
        f"<svg class='chart' viewBox='0 0 {width} {height}' "
        f"preserveAspectRatio='xMidYMid meet' role='img' aria-label='{html.escape(aria)}'>"
    ]
    base = pad_t + plot_h
    parts.append(
        f"<line class='grid' x1='{pad_l}' y1='{base}' x2='{width - pad_r}' y2='{base}'/>"
    )

    for ci, label in enumerate(labels):
        gx = pad_l + ci * group_w + group_w / 2
        start = gx - (bar_w * len(series)) / 2
        for si, s in enumerate(series):
            v = s["values"][ci] if ci < len(s["values"]) else None
            if _na(v):
                continue
            h = max(1.0, float(v) / hi * plot_h)
            x = start + si * bar_w
            parts.append(
                f"<rect x='{x:.1f}' y='{base - h:.1f}' width='{bar_w - 5:.1f}' "
                f"height='{h:.1f}' rx='3' fill='{s['colour']}'/>"
            )
            parts.append(
                f"<text class='tick' x='{x + (bar_w - 5) / 2:.1f}' y='{base - h - 7:.1f}' "
                f"text-anchor='middle'>{html.escape(value_fmt.format(float(v)))}</text>"
            )
        parts.append(
            f"<text class='cat' x='{gx:.1f}' y='{base + 22}' "
            f"text-anchor='middle'>{html.escape(str(label))}</text>"
        )

    lx = pad_l
    for s in series:
        parts.append(
            f"<rect x='{lx}' y='{height - 22}' width='13' height='13' rx='3' fill='{s['colour']}'/>"
            f"<text class='tick' x='{lx + 19}' y='{height - 11}'>{html.escape(s['name'])}</text>"
        )
        lx += 22 + len(s["name"]) * 7.4
    parts.append("</svg>")
    return "".join(parts)


def hbar(rows: Sequence[dict], *, width: int = 740, colour: str = "var(--series-1)") -> str:
    """Horizontal bars: {"label", "value" (0-1), "display"}."""
    rows = [r for r in rows if not _na(r.get("value"))]
    if not rows:
        return "<p class='na'>Nothing to plot.</p>"
    row_h, gap, label_w = 40, 9, 230
    height = len(rows) * (row_h + gap)
    track = width - label_w - 90
    out, y = [], 0
    for r in rows:
        v = max(0.0, min(1.0, float(r["value"])))
        out.append(
            f"<text class='wlabel' x='{label_w - 12}' y='{y + row_h / 2 + 5}' "
            f"text-anchor='end'>{html.escape(str(r['label']))}</text>"
            f"<rect x='{label_w}' y='{y + 9}' width='{track}' height='{row_h - 18}' "
            f"rx='5' fill='var(--line)'/>"
            f"<rect x='{label_w}' y='{y + 9}' width='{track * v:.1f}' "
            f"height='{row_h - 18}' rx='5' fill='{colour}'/>"
            f"<text class='wval' x='{label_w + track + 10}' y='{y + row_h / 2 + 5}'>"
            f"{html.escape(str(r.get('display') or f'{v:.0%}'))}</text>"
        )
        y += row_h + gap
    return (
        f"<svg class='chart' viewBox='0 0 {width} {height}' "
        f"preserveAspectRatio='xMidYMid meet' role='img' "
        f"aria-label='share by item'>{''.join(out)}</svg>"
    )
