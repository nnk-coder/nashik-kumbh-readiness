"""One readiness card per bathing site."""

from __future__ import annotations

import html
import math
from pathlib import Path

from . import charts, config as C

LIGHT = {"green": "#1a7f44", "amber": "#b06b00", "red": "#b3261e"}
TINT = {"green": "#e7f4ec", "amber": "#fdf1de", "red": "#fbeae8"}
BAND = {
    "green": "no change needed on this evidence",
    "amber": "resolve before the Snan",
    "red": "resolve before the Snan — several checks failed",
}
NR = "<span class='na'>not resolved</span>"

FLAG_LABELS = {
    "throughput_shortfall": "Can the site process the hour's arrivals?",
    "egress_time": "Can it be cleared quickly in an emergency?",
    "chokepoint": "Is any approach route dangerously narrow?",
    "toilet_gap": "Are there enough toilets?",
    "water_gap": "Are there enough drinking water points?",
}
FLAG_RULES = {
    "throughput_shortfall": "Raised when peak-hour arrivals exceed what the open ground can turn over in an hour.",
    "egress_time": f"Raised when clearing a full site through its approach routes would take more than {C.EGRESS_TIME_FLAG_MIN:.0f} minutes.",
    "chokepoint": f"Raised when the narrowest link on an approach route is under {C.CHOKEPOINT_MIN_WIDTH_M:.0f} m wide. This is the mechanism that killed 39 people at Ramkund in 2003.",
    "toilet_gap": f"Raised when more than {C.TOILET_GAP_FLAG:.0%} of the seats required by CPHEEO's community toilet norm are missing from the map.",
    "water_gap": f"Raised when more than {C.WATER_GAP_FLAG:.0%} of the taps required by CPHEEO (one per {C.WATER_TAP_PER:.0f} people) are missing from the map.",
}


def _isna(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def _e(v) -> str:
    return html.escape(str(v)) if not _isna(v) else "&mdash;"


def _n(v, suffix: str = "", nd: int = 0) -> str:
    if _isna(v):
        return NR
    try:
        return f"{float(v):,.{nd}f}{suffix}"
    except (TypeError, ValueError):
        return html.escape(str(v))


def _cascade(r: dict) -> str:
    """The demand chain, shown so every multiplier can be argued with."""
    rows = [
        ("Expected attendance over the event", _n(C.ATTENDANCE_EXPECTED), "state figure, ~4&times; the 2.5 crore of 2015"),
        ("Busiest day", _n(C.ATTENDANCE_EXPECTED * C.PEAK_DAY_SHARE), f"{C.PEAK_DAY_SHARE:.0%} of the total on one Amrit Snan"),
        ("Busiest hour", _n(C.ATTENDANCE_EXPECTED * C.PEAK_DAY_SHARE * C.PEAK_HOUR_SHARE), f"{C.PEAK_HOUR_SHARE:.0%} of that day, in the pre-dawn window"),
        (f"Presenting at {html.escape(str(r.get('name')))}", _n(r.get("peak_hour_arrivals")), f"{r.get('weight', 0):.0%} of arrivals assumed to come here"),
    ]
    return "\n".join(
        f"<tr><th scope='row'>{k}</th><td class='num'>{v}</td><td class='src'>{s}</td></tr>"
        for k, v, s in rows
    )


def _overflow_rows(r: dict) -> str:
    o = r.get("overflow") or {}
    rows = []
    for a in o.get("allocated", []):
        rows.append(
            f"<tr><td>{html.escape(str(a['name']))}</td>"
            f"<td class='num'>{a['distance_m']:,} m</td>"
            f"<td class='num'>{a['capacity']:,}</td>"
            f"<td class='num'>{a['holds']:,}</td></tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='4' class='na'>No mapped open space within reach.</td></tr>")
    return "\n".join(rows)


def _link_rows(r: dict) -> str:
    out = []
    for l in (r.get("approach_links") or [])[:8]:
        tagged = l.get("width_source") == "tagged"
        out.append(
            f"<tr><td>{html.escape(str(l['name']))}</td>"
            f"<td class='num'>{l['width_m']:.1f} m</td>"
            f"<td class='num'>{l.get('flow_per_min') or ''}</td>"
            f"<td class='src'>{'tagged in OSM' if tagged else 'inferred from road class'}</td></tr>"
        )
    return "\n".join(out) or "<tr><td colspan='4' class='na'>No approach routes resolved.</td></tr>"


def _queue_line(q: dict | None, label: str) -> str:
    if not q:
        return f"<li>{html.escape(label)}: {NR}</li>"
    if not q["stable"]:
        return (
            f"<li><b>{html.escape(label)}: the queue never clears.</b> "
            f"{q['demand_per_hour']:,} people an hour against capacity for "
            f"{q['capacity_per_hour']:,}; the backlog grows by "
            f"{q['backlog_per_hour']:,} every hour.</li>"
        )
    return (
        f"<li>{html.escape(label)}: about <b>{q['wait_minutes']:.0f} minutes</b> "
        f"of queueing at {q['units']:,} units.</li>"
    )


def render_card(r: dict) -> str:
    name = str(r.get("name"))
    light = r.get("traffic_light", "green")
    colour, tint = LIGHT[light], TINT[light]
    completeness = r.get("evidence_completeness") or 0.0
    b = r.get("breach") or {}
    o = r.get("overflow") or {}
    narrow = r.get("narrowest") or {}
    tg, wg = r.get("toilet_gap") or {}, r.get("water_gap") or {}

    flags_html = "\n".join(
        f"<li class='{'fired' if v else 'clear'}'>"
        f"<span class='mark'>{'FLAG' if v else 'clear'}</span>"
        f"<span class='flabel'>{html.escape(FLAG_LABELS[k])}</span>"
        f"<span class='weight'>{C.READINESS_WEIGHTS[k]:.0f} pts</span>"
        f"<span class='rule'>{FLAG_RULES[k]}</span></li>"
        for k, v in (r.get("flags") or {}).items()
    )

    errors = ""
    if r.get("errors"):
        items = "".join(f"<li>{html.escape(str(e))}</li>" for e in r["errors"])
        errors = f"<details class='errors'><summary>Query errors ({len(r['errors'])})</summary><ul>{items}</ul></details>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(name)} — Simhastha readiness</title>
<link rel="stylesheet" href="../assets/style.css">
</head><body class="card-page">
<article class="card">
  <header style="border-left:10px solid {colour};background:{tint}">
    <p class="eyebrow">Amrit Snan site readiness</p>
    <h1>{html.escape(name)}</h1>
    <p class="sub">{html.escape(str(r.get('city')))} &middot;
      {_n(r.get('lat'), '', 4)}, {_n(r.get('lon'), '', 4)} &middot;
      precinct measured within {_n(r.get('assembly_radius_m'), ' m')}</p>
    <div class="scorebox">
      <div>
        <div class="score" style="color:{colour}">{r.get('score', 0):.0f}<span>/100</span></div>
        <div class="scorelabel">readiness risk</div>
      </div>
      <div class="light" style="background:{colour}">{html.escape(BAND[light])}</div>
      <div class="ringbox">{charts.completeness_ring(completeness)}<span>of checks<br>resolved</span></div>
    </div>
    <p class="sitenote">{html.escape(str(r.get('note') or ''))}</p>
  </header>

  <section>
    <h2>The hour that matters</h2>
    <p class="lede">Every number below follows from these four. Change a
      multiplier and the whole card changes with it.</p>
    <table class="evidence">
      <thead><tr><th>Step</th><th>People</th><th>Assumption</th></tr></thead>
      <tbody>{_cascade(r)}</tbody>
    </table>
  </section>

  <section>
    <h2>What the ground can take</h2>
    <div class="kpis">
      <div class="kpi"><b>{_n(r.get('open_m2'), ' m²')}</b><span>open ground, after buildings and water are removed</span></div>
      <div class="kpi"><b>{_n(r.get('holding_capacity'))}</b><span>standing capacity at {C.DENSITY_PLANNING:.0f}/m²</span></div>
      <div class="kpi"><b>{_n(r.get('throughput_per_hour'))}</b><span>can pass through per hour at a {C.GHAT_DWELL_MINUTES:.0f}-minute dwell</span></div>
      <div class="kpi"><b style="color:{colour}">{_n(b.get('ratio'), '×', 2)}</b><span>arrivals against that throughput</span></div>
    </div>
    <p class="note">If the hour's arrivals all stood in the precinct at once the
      density would be <b>{_n(r.get('density_if_all_present'), '/m²', 1)}</b>
      &mdash; Fruin band {_e(r.get('fruin_band'))}. They physically cannot, and
      that is the point: the excess does not disappear, it backs up along the
      approach routes, which is where crowd collapse happens.</p>
  </section>

  <section>
    <h2>When capacity breaches</h2>
    <div class="kpis">
      <div class="kpi"><b>{_n(b.get('surplus'))}</b><span>more than the site can process this hour</span></div>
      <div class="kpi"><b>{_n(o.get('absorbed'))}</b><span>absorbed by open space within {C.OVERFLOW_WALK_RADIUS_M:.0f} m</span></div>
      <div class="kpi"><b style="color:{LIGHT['red']}">{_n(o.get('residual'))}</b><span>left with nowhere to go</span></div>
      <div class="kpi"><b>{_n(r.get('hold_upstream_min'), ' min')}</b><span>the residual must be held upstream before the site can take it</span></div>
    </div>
    <table class="evidence">
      <thead><tr><th>Holding area</th><th>Distance</th><th>Capacity at {C.OVERFLOW_HOLDING_DENSITY:.0f}/m²</th><th>Allocated</th></tr></thead>
      <tbody>{_overflow_rows(r)}</tbody>
    </table>
    <p class="note">Nearest first, because a crowd sent further is a crowd that
      will not go. The residual is the number that has to be stopped at the
      railway stations and road approaches, before it ever reaches the ghat.</p>
  </section>

  <section>
    <h2>Approach routes</h2>
    <p class="lede">The narrowest link is <b>{html.escape(str(narrow.get('name') or 'not resolved'))}</b>
      at <b>{_n(narrow.get('width_m'), ' m', 1)}</b>, passing about
      <b>{_n(narrow.get('flow_per_min'))}</b> people a minute.
      Clearing a full site takes <b>{_n(r.get('egress_time_min'), ' minutes', 0)}</b>.</p>
    <table class="evidence">
      <thead><tr><th>Route</th><th>Width</th><th>People/min</th><th>Width from</th></tr></thead>
      <tbody>{_link_rows(r)}</tbody>
    </table>
    <p class="note">{_n((r.get('inferred_width_share') or 0) * 100, '%')} of these
      widths are inferred from road class rather than measured. That is the
      weakest input on this card and the first thing a site visit should replace.</p>
  </section>

  <section>
    <h2>Toilets and drinking water</h2>
    <div class="kpis">
      <div class="kpi"><b>{_n(tg.get('required'))}</b><span>toilet seats required by CPHEEO's community norm</span></div>
      <div class="kpi"><b>{_n(tg.get('mapped'))}</b><span>mapped in OpenStreetMap</span></div>
      <div class="kpi"><b>{_n(r.get('toilets_for_target_wait'))}</b><span>needed to hold the queue to {C.TARGET_QUEUE_WAIT_MIN:.0f} minutes</span></div>
      <div class="kpi"><b>{_n(wg.get('required'))}</b><span>water taps required, one per {C.WATER_TAP_PER:.0f} people</span></div>
    </div>
    <ul class="queues">
      {_queue_line(r.get('toilet_queue_as_mapped'), 'Toilets, at what is mapped today')}
      {_queue_line(r.get('toilet_queue_at_norm'), 'Toilets, at the CPHEEO norm')}
      {_queue_line(r.get('water_queue_as_mapped'), 'Water points, at what is mapped today')}
    </ul>
    <p class="note">Queues are computed per block of
      {C.TOILET_BLOCK_UNITS} units, not across the whole site: people queue at
      the block in front of them. Pooling every unit into one queue would make
      the wait collapse to almost nothing, which is not what anyone has
      experienced at a mela. <b>OpenStreetMap is not an inventory</b> &mdash; a
      facility that exists but is unmapped counts as missing here, so the gap
      is an upper bound until the Authority supplies its own asset list.</p>
  </section>

  <section>
    <h2>The rubric</h2>
    <ul class="flags">{flags_html}</ul>
    {charts.weight_bars(C.READINESS_WEIGHTS, r.get('flags'))}
    <p class="note">The score is the combined weight of the checks that failed.
      It ranks what to resolve first. It is not a prediction, not a safety
      certificate, and not a statement about any authority's preparations.</p>
    {errors}
  </section>

  <footer>
    <p>Geometry and facilities from OpenStreetMap contributors (ODbL).
      Toilet and water norms from CPHEEO's Advisory on Public and Community
      Toilets. Crowd density bands after Fruin.</p>
    <p><a class="btn" href="../index.html">&larr; Back to all sites</a></p>
  </footer>
</article>
</body></html>
"""


def write_cards(records: list[dict], docs_dir: str = "docs") -> list[str]:
    out = Path(docs_dir) / "cards"
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for r in records:
        p = out / f"{str(r.get('id')).replace('/', '-')}.html"
        p.write_text(render_card(r), encoding="utf-8")
        paths.append(str(p))
    return paths
