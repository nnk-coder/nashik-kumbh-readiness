"""The published index page."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

from . import charts, config as C

LIGHT = {"green": "#1a7f44", "amber": "#b06b00", "red": "#b3261e"}


def _n(v, default=0.0) -> float:
    if v is None:
        return default
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return default if math.isnan(f) else f


def _isna(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def cascade_diagram() -> str:
    """The demand funnel, drawn so the multipliers are visible at a glance."""
    steps = [
        ("12 crore", "expected over the whole Simhastha", "#2B5CE6"),
        ("1.8 crore", f"on the busiest Amrit Snan ({C.PEAK_DAY_SHARE:.0%})", "#2E6FD6"),
        ("36 lakh", f"in the pre-dawn hour ({C.PEAK_HOUR_SHARE:.0%})", "#C0478F"),
        ("at four sites", "split by assumed share of arrivals", "#b3261e"),
    ]
    w, h = 1120, 150
    bw, gap = 240, 52
    out = [
        f"<svg class='flow' viewBox='0 0 {w} {h}' preserveAspectRatio='xMidYMid meet' "
        f"role='img' aria-label='How 12 crore visitors becomes a peak-hour crowd'>"
    ]
    for i, (big, small, colour) in enumerate(steps):
        x = i * (bw + gap)
        out.append(
            f"<g><rect x='{x}' y='30' width='{bw}' height='86' rx='12' "
            f"fill='{colour}' opacity='0.10'/>"
            f"<text x='{x + 18}' y='70' class='casc-big' fill='{colour}'>{html.escape(big)}</text>"
            f"<foreignObject x='{x + 16}' y='78' width='{bw - 32}' height='34'>"
            f"<div xmlns='http://www.w3.org/1999/xhtml' class='casc-small'>{html.escape(small)}</div>"
            f"</foreignObject></g>"
        )
        if i < len(steps) - 1:
            ax = x + bw
            out.append(
                f"<path d='M{ax + 8} 73 L{ax + gap - 14} 73' class='casc-arrow'/>"
                f"<path d='M{ax + gap - 20} 67 L{ax + gap - 10} 73 L{ax + gap - 20} 79' "
                f"class='casc-head'/>"
            )
    out.append("</svg>")
    return "".join(out)


def _rows(records: list[dict]) -> str:
    out = []
    for r in records:
        light = r.get("traffic_light", "green")
        b = r.get("breach") or {}
        o = r.get("overflow") or {}
        slug = str(r.get("id"))
        out.append(
            "<tr>"
            f"<td><a href='cards/{html.escape(slug)}.html'>{html.escape(str(r.get('name')))}</a>"
            f"<div class='sub2'>{html.escape(str(r.get('city')))}</div></td>"
            f"<td data-v='{_n(r.get('peak_hour_arrivals'))}' class='num'>{_n(r.get('peak_hour_arrivals')):,.0f}</td>"
            f"<td data-v='{_n(r.get('throughput_per_hour'))}' class='num'>{_n(r.get('throughput_per_hour')):,.0f}</td>"
            f"<td data-v='{_n(b.get('ratio'))}' class='num'>{_n(b.get('ratio')):,.2f}&times;</td>"
            f"<td data-v='{_n(o.get('residual'))}' class='num'>{_n(o.get('residual')):,.0f}</td>"
            f"<td data-v='{_n((r.get('narrowest') or {}).get('width_m'))}' class='num'>"
            f"{_n((r.get('narrowest') or {}).get('width_m')):,.1f} m</td>"
            f"<td data-v='{_n(r.get('score'))}'>"
            f"<span class='pill' style='background:{LIGHT[light]}'>{_n(r.get('score')):.0f}</span></td>"
            "</tr>"
        )
    return "\n".join(out)


def _markers(records: list[dict]) -> str:
    pts = [
        {
            "name": str(r.get("name")), "lat": _n(r.get("lat")), "lon": _n(r.get("lon")),
            "score": _n(r.get("score")), "light": r.get("traffic_light") or "green",
            "ratio": _n((r.get("breach") or {}).get("ratio")), "slug": str(r.get("id")),
        }
        for r in records
        if not _isna(r.get("lat")) and not _isna(r.get("lon"))
    ]
    return json.dumps(pts, allow_nan=False)


def render_index(records: list[dict], as_of: str) -> str:
    n = len(records)
    counts = {k: sum(1 for r in records if r.get("traffic_light") == k) for k in LIGHT}
    residual = sum(_n((r.get("overflow") or {}).get("residual")) for r in records)
    toilets_req = sum(_n((r.get("toilet_gap") or {}).get("required")) for r in records)
    toilets_map = sum(_n((r.get("toilet_gap") or {}).get("mapped")) for r in records)
    mean_comp = sum(_n(r.get("evidence_completeness")) for r in records) / n if n else 0

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nashik Simhastha — Amrit Snan site readiness</title>
<meta name="description" content="Crowd capacity, overflow and sanitation at the Nashik Simhastha bathing sites, from open data.">
<link rel="stylesheet" href="assets/style.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
</head><body>
<main class="site">

<header class="hero">
  <p class="eyebrow">Open-data prototype &middot; {html.escape(as_of)}</p>
  <h1>Four bathing sites. One pre-dawn hour. How many people can actually stand there?</h1>
  <p class="lede">The Nashik&ndash;Trimbakeshwar Simhastha runs from 31 October 2026
    to 24 July 2028, and the risk concentrates on four Amrit Snan mornings in
    August and September 2027. The state expects around <b>12 crore</b>
    visitors, roughly four times the 2015 event.</p>
  <p class="lede">This measures the open ground at each bathing site from
    OpenStreetMap, works out what it can process in the busiest hour, and says
    where the people it cannot process are supposed to go. It then does the
    same for toilets and drinking water against CPHEEO's norms.</p>
  <p class="lede small">Two things make Nashik unlike Prayagraj, and both make
    the Prayagraj playbook a poor template. Nashik's ghats sit inside a dense
    historic city rather than on open sandbanks &mdash; in 2003, 39 people died
    at Ramkund when about 30,000 were held on a narrow approach street. And the
    Snans fall in the monsoon, not the dry season.</p>
</header>

<section class="stats">
  <div class="stat"><b>{n}</b><span>sites assessed</span></div>
  <div class="stat"><b style="color:{LIGHT['red']}">{counts['red']}</b><span>resolve first</span></div>
  <div class="stat"><b style="color:{LIGHT['amber']}">{counts['amber']}</b><span>resolve soon</span></div>
  <div class="stat"><b>{residual:,.0f}</b><span>with nowhere to go</span></div>
  <div class="stat"><b>{toilets_req:,.0f}</b><span>toilet seats required</span></div>
  <div class="stat"><b>{toilets_map:,.0f}</b><span>seats mapped</span></div>
</section>

<section>
  <p class="eyebrow">How the number is built</p>
  <h2>Twelve crore becomes thirty-six lakh in one hour</h2>
  <div class="flowwrap">{cascade_diagram()}</div>
  <p class="note">Every multiplier is a stated assumption, set in one config
    file and listed on each card. The peak-day share follows Prayagraj 2025,
    where roughly a quarter of expected attendance came on Mauni Amavasya;
    Nashik spreads across more Snan days, so {C.PEAK_DAY_SHARE:.0%} is used here.</p>
</section>

<section>
  <h2>The sites</h2>
  <div id="map" style="height:420px;border-radius:12px;overflow:hidden"></div>
  <table class="portfolio" id="pf">
    <thead><tr>
      <th>Site</th><th>Peak-hour arrivals</th><th>Can process</th>
      <th>Ratio</th><th>Nowhere to go</th><th>Narrowest route</th><th>Risk</th>
    </tr></thead>
    <tbody>{_rows(records)}</tbody>
  </table>
  <p class="note">Click a column heading to sort. "Can process" is standing
    capacity multiplied by how many times the space turns over in an hour at a
    {C.GHAT_DWELL_MINUTES:.0f}-minute dwell &mdash; throughput, not instantaneous capacity,
    is what binds at a bathing ghat.</p>
</section>

<section>
  <h2>What the risk score is made of</h2>
  {charts.weight_bars(C.READINESS_WEIGHTS)}
  <div class="bands">
    <span class="pill" style="background:{LIGHT['green']}">0&ndash;24</span> no change needed on this evidence
    <span class="pill" style="background:{LIGHT['amber']}">25&ndash;54</span> resolve before the Snan
    <span class="pill" style="background:{LIGHT['red']}">55&ndash;100</span> several checks failed
  </div>
  <p class="note">Mean evidence resolved across sites: <b>{mean_comp:.0%}</b>.
    A check that could not be resolved is reported as unresolved and scored as
    clear, so every score here is a lower bound.</p>
</section>

<section class="limits">
  <p class="eyebrow">Read this part</p>
  <h2>Six things this gets wrong &mdash; and why they are published</h2>
  <ol class="limitlist">
    <li><b>OpenStreetMap is not an asset register.</b> A toilet that exists but
      was never mapped counts as missing. The sanitation gaps are an upper
      bound until the Authority supplies its own inventory.</li>
    <li><b>Most road widths are inferred, not measured.</b> Indian streets
      rarely carry a width tag, so widths come from road class. Each card says
      what share was inferred; this is the first thing a site visit replaces.</li>
    <li><b>Open ground is an upper bound.</b> It is the precinct less buildings
      and water. Barriers, akhara enclosures, vehicle routes and stalls all
      take more away.</li>
    <li><b>The arrival assumptions are assumptions.</b> Peak-day and peak-hour
      shares are reasoned from Prayagraj 2025, not observed at Nashik. The
      site weights are a planning split, not a forecast.</li>
    <li><b>Queueing assumes people spread evenly between blocks.</b> They do
      not, so real waits are worse than the figures here.</li>
    <li><b>Nothing here models behaviour.</b> Crowd collapse is a dynamic
      process; this is a static capacity check. It finds sites that cannot
      work arithmetically. A site that passes still needs a simulation.</li>
  </ol>
  <p class="note">And the standing rule: <b>this is a screening tool, not a
    safety case.</b> It is not a prediction of harm and not a statement about
    any authority's preparations.</p>
</section>

<footer class="sitefoot">
  <p><b>Sources</b> &middot; Geometry and facilities: OpenStreetMap contributors
     (ODbL) &middot; Toilet and water norms: CPHEEO, Advisory on Public and
     Community Toilets &middot; Crowd density bands after Fruin; critical
     density after G. Keith Still &middot; Event dates and attendance: Maharashtra
     government announcements.</p>
  <p>A personal methodology prototype, published as independent work. Not
     affiliated with, endorsed by, or produced for any authority. Code MIT licensed.</p>
</footer>
</main>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const PTS = {_markers(records)};
const COL = {json.dumps(LIGHT)};
const map = L.map('map').setView([19.97, 73.67], 11);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
}}).addTo(map);
PTS.forEach(p => {{
  L.circleMarker([p.lat, p.lon], {{
    radius: Math.max(8, Math.min(26, 6 + p.ratio * 3)),
    color: COL[p.light] || '#666', fillColor: COL[p.light] || '#666',
    fillOpacity: 0.55, weight: 2
  }}).addTo(map).bindPopup(
    `<b>${{p.name}}</b><br>${{p.ratio}}&times; over capacity in the peak hour` +
    `<br><a href="cards/${{p.slug}}.html">readiness card</a>`
  );
}});
if (PTS.length) map.fitBounds(PTS.map(p => [p.lat, p.lon]), {{padding: [60, 60]}});

document.querySelectorAll('#pf thead th').forEach((th, i) => {{
  th.style.cursor = 'pointer';
  let asc = false;
  th.addEventListener('click', () => {{
    asc = !asc;
    const tb = document.querySelector('#pf tbody');
    Array.from(tb.rows).sort((a, b) => {{
      const av = a.cells[i].dataset.v, bv = b.cells[i].dataset.v;
      if (av !== undefined && bv !== undefined) return (asc ? 1 : -1) * (parseFloat(av) - parseFloat(bv));
      return (asc ? 1 : -1) * a.cells[i].innerText.localeCompare(b.cells[i].innerText);
    }}).forEach(r => tb.appendChild(r));
  }});
}});

const io = new IntersectionObserver(es => es.forEach(e => {{
  if (e.isIntersecting) {{ e.target.classList.add('in'); io.unobserve(e.target); }}
}}), {{threshold: 0.12}});
document.querySelectorAll('section, .flowwrap').forEach(el => {{
  el.classList.add('reveal'); io.observe(el);
}});
</script>
</body></html>
"""


def write_site(records: list[dict], as_of: str, docs_dir: str = "docs") -> str:
    out = Path(docs_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "index.html"
    p.write_text(render_index(records, as_of), encoding="utf-8")
    return str(p)
