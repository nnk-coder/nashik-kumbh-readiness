"""The published index page, written for a reader with no technical background.

Structured as an argument: what has gone wrong before, how much of it was
foreseeable, how this measures it, one site worked through, what it would be
worth, and what it cannot see.
"""

from __future__ import annotations

import html
import json
import math
from pathlib import Path

from . import capacity as CAP, charts, config as C

LIGHT = {"green": "#1a7f44", "amber": "#b06b00", "red": "#b3261e"}
SERIES_DEMAND = "#b3261e"
SERIES_CAPACITY = "#2B5CE6"


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


# --- diagrams --------------------------------------------------------------


def method_flowchart() -> str:
    """Five stages, with the evidence fanning out and funnelling back in."""
    feeds = [
        ("Buildings", "what is already standing"),
        ("Streets", "how wide the ways in are"),
        ("Open space", "where a crowd could be held"),
        ("Toilets, water", "what is on the ground"),
        ("CPHEEO norms", "what the rules require"),
    ]
    w, h, mid = 1300, 470, 240
    edges, pills, nodes = [], [], []

    def box(x, num, title, body, bw=185):
        return (
            f"<g class='fnode'><rect x='{x}' y='{mid - 58}' width='{bw}' height='116' rx='14'/>"
            f"<text class='fnum' x='{x + 16}' y='{mid - 30}'>{num}</text>"
            f"<text class='ftitle' x='{x + 16}' y='{mid - 6}'>{title}</text>"
            f"<foreignObject x='{x + 14}' y='{mid + 4}' width='{bw - 28}' height='54'>"
            f"<div xmlns='http://www.w3.org/1999/xhtml' class='fbody'>{body}</div>"
            f"</foreignObject></g>"
        )

    px, pw, ph, s4 = 440, 255, 56, 830
    for (name, what), y in zip(feeds, [25, 100, 175, 250, 325]):
        cy = y + ph / 2
        edges.append(f"<path class='fedge' d='M390 {mid} C 415 {mid}, 415 {cy:.0f}, {px} {cy:.0f}'/>")
        edges.append(
            f"<path class='fedge' d='M{px + pw} {cy:.0f} C {px + pw + 50} {cy:.0f}, "
            f"{s4 - 50} {mid}, {s4} {mid}'/>"
        )
        pills.append(
            f"<g class='fpill'><rect x='{px}' y='{y}' width='{pw}' height='{ph}' rx='12'/>"
            f"<text class='fpill-name' x='{px + 14}' y='{y + 23}'>{html.escape(name)}</text>"
            f"<text class='fpill-what' x='{px + 14}' y='{y + 42}'>{html.escape(what)}</text></g>"
        )

    nodes.append(box(0, "1", "The crowd", "12 crore over the event; four Amrit Snan mornings."))
    nodes.append(box(205, "2", "The place", "Draw the precinct around each bathing site."))
    nodes.append(box(s4, "4", "The test", "Capacity, queues, and what one closure costs."))
    nodes.append(box(1050, "5", "The verdict", "A risk score, and what to fix first.", bw=240))
    edges.append(f"<path class='fedge strong' d='M185 {mid} L205 {mid}'/>")
    edges.append(f"<path class='fedge strong' d='M{s4 + 185} {mid} L1050 {mid}'/>")

    tag = (
        f"<g class='ftag'><rect x='{px + 28}' y='402' width='186' height='34' rx='17'/>"
        f"<text x='{px + 121}' y='424' text-anchor='middle'>Data cost: &#8377;0</text></g>"
    )
    stage3 = (
        f"<text class='fstage' x='{px + pw / 2}' y='14' text-anchor='middle'>"
        f"3 &#183; The evidence &#8212; open data, no account needed</text>"
    )
    return (
        f"<svg class='flow' viewBox='0 0 {w} {h}' preserveAspectRatio='xMidYMid meet' "
        f"role='img' aria-label='How the assessment works, in five stages'>"
        + "".join(edges) + "".join(pills) + "".join(nodes) + stage3 + tag + "</svg>"
    )


def cascade_diagram() -> str:
    steps = [
        ("12 crore", "expected over the whole Simhastha", "#2B5CE6"),
        ("1.8 crore", f"on the busiest Amrit Snan ({C.PEAK_DAY_SHARE:.0%})", "#2E6FD6"),
        ("36 lakh", f"in the pre-dawn hour ({C.PEAK_HOUR_SHARE:.0%})", "#C0478F"),
        ("at four sites", "split by assumed share of arrivals", "#b3261e"),
    ]
    w, h, bw, gap = 1120, 150, 240, 52
    out = [
        f"<svg class='flow' viewBox='0 0 {w} {h}' preserveAspectRatio='xMidYMid meet' "
        f"role='img' aria-label='How 12 crore visitors becomes a peak-hour crowd'>"
    ]
    for i, (big, small, colour) in enumerate(steps):
        x = i * (bw + gap)
        out.append(
            f"<g><rect x='{x}' y='30' width='{bw}' height='86' rx='12' fill='{colour}' opacity='0.10'/>"
            f"<text x='{x + 18}' y='70' class='casc-big' fill='{colour}'>{html.escape(big)}</text>"
            f"<foreignObject x='{x + 16}' y='78' width='{bw - 32}' height='34'>"
            f"<div xmlns='http://www.w3.org/1999/xhtml' class='casc-small'>{html.escape(small)}</div>"
            f"</foreignObject></g>"
        )
        if i < len(steps) - 1:
            ax = x + bw
            out.append(
                f"<path d='M{ax + 8} 73 L{ax + gap - 14} 73' class='casc-arrow'/>"
                f"<path d='M{ax + gap - 20} 67 L{ax + gap - 10} 73 L{ax + gap - 20} 79' class='casc-head'/>"
            )
    out.append("</svg>")
    return "".join(out)


# --- narrative sections ----------------------------------------------------

PROBLEMS = [
    ("2003", "Nashik, Ramkund", "39 dead, 57 injured",
     "About 30,000 pilgrims were held by barricades on a narrow street leading to Ramkund. A scramble started and the crowd collapsed.",
     "A route too narrow for the crowd fed into it."),
    ("2025", "Prayagraj, Mauni Amavasya", "37 official, BBC investigation found at least 82",
     "A barrier broke during the Amrit Snan. People fleeing were caught at a closed exit; pontoon bridges they turned to had been shut.",
     "Capacity that existed on paper was not available on the night."),
    ("2015", "Nashik, previous Simhastha", "2.5 crore attended",
     "No mass-casualty incident, but the city handled roughly a quarter of the crowd now expected.",
     "The precedent everyone plans from is four times too small."),
]

PREDICTABILITY = [
    ("A route too narrow for the crowd sent down it", "Yes", "Years ahead",
     "Street widths and the open ground at each ghat are in open map data today.", True),
    ("One closure removing most of the exit capacity", "Yes", "Years ahead",
     "Leave-one-out on the route network. No new data needed.", True),
    ("Overflow with nowhere to go", "Yes", "Years ahead",
     "Open space within walking distance is mapped; so is how much of the surplus it absorbs.", True),
    ("Toilet and water queues collapsing", "Mostly", "Months ahead",
     "Requires the authority's own facility inventory to be exact; open data gives the order of magnitude.", True),
    ("Where a crowd will actually choose to go", "No", "&mdash;",
     "Behavioural, and needs a dynamic simulation plus on-the-ground stewarding plans.", False),
    ("A barrier failing, or a decision taken at 1am", "No", "&mdash;",
     "Operational. Mitigated by redundancy, which is exactly what the failure analysis measures.", False),
]


def problem_section() -> str:
    rows = "\n".join(
        f"<tr><td class='yr'>{html.escape(y)}</td><td><b>{html.escape(place)}</b>"
        f"<div class='sub2'>{html.escape(toll)}</div></td>"
        f"<td>{html.escape(what)}</td><td class='src'>{html.escape(lesson)}</td></tr>"
        for y, place, toll, what, lesson in PROBLEMS
    )
    return f"""
<section>
  <p class="eyebrow">The problem</p>
  <h2>This has already happened, twice, in living memory</h2>
  <p class="lede">Crowd collapse at a Kumbh is not a freak event. It has a
    mechanism, and the mechanism repeats: more people are fed towards a point
    than the ground at that point can clear, and then something closes.</p>
  <table class="evidence problems">
    <thead><tr><th>Year</th><th>Where</th><th>What happened</th><th>The mechanism</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="note">Nashik now expects roughly <b>four times</b> the crowd it
    handled in 2015, on ghats inside a dense historic city rather than on open
    sandbanks, during the monsoon rather than the dry season.</p>
</section>"""


def predictability_section() -> str:
    rows = "\n".join(
        f"<tr class='{'yes' if ok else 'no'}'><td>{html.escape(mode)}</td>"
        f"<td><span class='tag {'tyes' if ok else 'tno'}'>{html.escape(seen)}</span></td>"
        f"<td class='num'>{ahead}</td><td class='src'>{why}</td></tr>"
        for mode, seen, ahead, why, ok in PREDICTABILITY
    )
    n_yes = sum(1 for *_x, ok in PREDICTABILITY if ok)
    return f"""
<section>
  <p class="eyebrow">Predictability</p>
  <h2>How much of it can you see coming?</h2>
  <p class="lede">The honest answer is: most of the arithmetic, none of the
    behaviour. <b>{n_yes} of {len(PREDICTABILITY)}</b> failure modes below are
    visible from data that already exists, years before the event. The rest are
    not, and no amount of mapping will make them so.</p>
  <table class="evidence predict">
    <thead><tr><th>Failure mode</th><th>Foreseeable?</th><th>How far ahead</th><th>Why</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="note">That split is the argument for doing this early. The
    foreseeable half is cheap to check and expensive to discover late &mdash;
    widening an approach route is a civil works decision with a lead time of
    years, not a decision anyone can take on the morning of a Snan.</p>
</section>"""


def demand_chart(records: list[dict]) -> str:
    labels = [str(r.get("name")) for r in records]
    return charts.grouped_bars(
        labels,
        [
            {"name": "Arriving in the peak hour", "values": [_n(r.get("peak_hour_arrivals")) for r in records], "colour": SERIES_DEMAND},
            {"name": "The site can process", "values": [_n(r.get("throughput_per_hour")) for r in records], "colour": SERIES_CAPACITY},
        ],
        aria="peak-hour arrivals against what each site can process",
    )


def failure_chart(records: list[dict]) -> str:
    rows = []
    for r in records:
        top = (r.get("route_criticality") or [{}])[0]
        if top.get("share_of_exit_capacity") is None:
            continue
        rows.append(
            {
                "label": f"{r.get('name')} — {top.get('name')}",
                "value": top["share_of_exit_capacity"],
                "display": f"{top['share_of_exit_capacity']:.0%}",
            }
        )
    return charts.hbar(rows, colour=SERIES_DEMAND)


def worked_example(records: list[dict]) -> str:
    if not records:
        return ""
    r = max(records, key=lambda x: (_n(x.get("score")), _n(x.get("peak_hour_arrivals"))))
    b, o = r.get("breach") or {}, r.get("overflow") or {}
    sp = r.get("single_point") or {}
    narrow = r.get("narrowest") or {}
    reasons = "".join(f"<li>{html.escape(x)}</li>" for x in (sp.get("reasons") or []))
    light = r.get("traffic_light", "green")
    return f"""
<section class="worked">
  <p class="eyebrow">One site, start to finish</p>
  <h2>{html.escape(str(r.get('name')))}</h2>
  <p class="lede">The same checks every site gets, shown in full.</p>
  <div class="kpis">
    <div class="kpi"><b>{_n(r.get('peak_hour_arrivals')):,.0f}</b><span>arrive in the busiest hour</span></div>
    <div class="kpi"><b>{_n(r.get('throughput_per_hour')):,.0f}</b><span>the ground can process</span></div>
    <div class="kpi"><b style="color:{LIGHT['red']}">{_n(o.get('residual')):,.0f}</b><span>with nowhere to go</span></div>
    <div class="kpi"><b>{_n(r.get('hold_upstream_min')):,.0f} min</b><span>they must be held upstream</span></div>
  </div>
  <p>The open ground is <b>{_n(r.get('open_m2')):,.0f} m²</b> once buildings and
    water are removed. At a managed standing density that holds
    <b>{_n(r.get('holding_capacity')):,.0f}</b> people, turning over every
    {C.GHAT_DWELL_MINUTES:.0f} minutes. Demand runs
    <b>{_n(b.get('ratio')):,.2f}×</b> that. The narrowest way in is
    <b>{html.escape(str(narrow.get('name') or 'not resolved'))}</b> at
    <b>{_n(narrow.get('width_m')):,.1f} m</b>.</p>
  <div class="callout" style="border-color:{LIGHT[light]}">
    <h3>And if one thing fails</h3>
    <ul>{reasons or '<li>No single closure breaks the plan on this evidence.</li>'}</ul>
  </div>
  <p><a class="btn" href="cards/{html.escape(str(r.get('id')))}.html">See the full card &rarr;</a></p>
</section>"""


def value_section(records: list[dict]) -> str:
    residual = sum(_n((r.get("overflow") or {}).get("residual")) for r in records)
    return f"""
<section class="versus">
  <p class="eyebrow">What it is worth</p>
  <h2>The cheapest thing you can do before anyone travels</h2>
  <div class="vgrid">
    <div class="vcol old">
      <h3>A site assessment the usual way</h3>
      <p class="vbig">Weeks</p>
      <ul>
        <li>Engineers and stewards walk each site</li>
        <li>One site at a time, in sequence</li>
        <li>Cost scales with every site added</li>
        <li>Describes the site as it is today</li>
      </ul>
    </div>
    <div class="vcol new">
      <h3>This, first</h3>
      <p class="vbig">Minutes</p>
      <ul>
        <li>Runs from a desk, before anyone travels</li>
        <li>Every site at once, re-runnable whenever plans change</li>
        <li>Data costs nothing; the tenth site is free</li>
        <li>Tests the plan against arithmetic, not impressions</li>
      </ul>
    </div>
  </div>
  <p class="note"><b>It does not replace a site visit.</b> It decides which
    sites are worth one, what to measure when you get there, and which
    questions to put to the people who already know the ground. On this run it
    puts a number on something no walk-round would surface:
    <b>{residual:,.0f} people</b> with nowhere to go in a single hour, and the
    specific routes, holding grounds and facility clusters whose loss would
    make that worse.</p>
</section>"""


# --- table and map ---------------------------------------------------------


def _rows(records: list[dict]) -> str:
    out = []
    for r in records:
        light = r.get("traffic_light", "green")
        b, o = r.get("breach") or {}, r.get("overflow") or {}
        out.append(
            "<tr>"
            f"<td><a href='cards/{html.escape(str(r.get('id')))}.html'>{html.escape(str(r.get('name')))}</a>"
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


# --- page ------------------------------------------------------------------


def render_index(records: list[dict], as_of: str) -> str:
    n = len(records)
    counts = {k: sum(1 for r in records if r.get("traffic_light") == k) for k in LIGHT}
    residual = sum(_n((r.get("overflow") or {}).get("residual")) for r in records)
    t_req = sum(_n((r.get("toilet_gap") or {}).get("required")) for r in records)
    t_map = sum(_n((r.get("toilet_gap") or {}).get("mapped")) for r in records)
    mean_comp = sum(_n(r.get("evidence_completeness")) for r in records) / n if n else 0
    spf = sum(1 for r in records if (r.get("single_point") or {}).get("flagged"))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nashik Simhastha — Amrit Snan site readiness</title>
<meta name="description" content="Crowd capacity, overflow and sanitation at the Nashik Simhastha bathing sites, measured from open data.">
<link rel="stylesheet" href="assets/style.css">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
</head><body>
<main class="site">

<header class="hero">
  <p class="eyebrow">Open-data prototype &middot; {html.escape(as_of)}</p>
  <h1>Four bathing sites. One pre-dawn hour. How many people can actually stand there?</h1>
  <p class="lede">The Nashik&ndash;Trimbakeshwar Simhastha runs from 31 October 2026
    to 24 July 2028. The risk concentrates on four Amrit Snan mornings in
    August and September 2027, when the state expects around <b>12 crore</b>
    visitors in total &mdash; roughly four times the 2015 event.</p>
  <p class="lede">This measures the open ground at each bathing site, works out
    what it can process in the busiest hour, says where the people it cannot
    process are supposed to go, checks the toilets and drinking water against
    national norms, and then asks what one closure would do to all of it.</p>
  <p class="lede small">Everything here comes from public map data and
    published standards. No account, no licence, no site visit.</p>
</header>

<section class="stats">
  <div class="stat"><b>{n}</b><span>sites assessed</span></div>
  <div class="stat"><b style="color:{LIGHT['red']}">{counts['red']}</b><span>resolve first</span></div>
  <div class="stat"><b>{residual:,.0f}</b><span>with nowhere to go</span></div>
  <div class="stat"><b>{spf}</b><span>sites with no redundancy</span></div>
  <div class="stat"><b>{t_req:,.0f}</b><span>toilet seats required</span></div>
  <div class="stat"><b>{t_map:,.0f}</b><span>seats mapped</span></div>
</section>

{problem_section()}

{predictability_section()}

<section>
  <p class="eyebrow">How it works</p>
  <h2>From a map anyone can download to a number you can argue with</h2>
  <div class="flowwrap">{method_flowchart()}</div>
  <h3>Step 1 in detail: where the crowd number comes from</h3>
  <div class="flowwrap">{cascade_diagram()}</div>
  <p class="note">Every multiplier is a stated assumption living in one
    configuration file. The peak-day share follows Prayagraj 2025, where about
    a quarter of expected attendance came on a single morning; Nashik spreads
    across more Snan days, so {C.PEAK_DAY_SHARE:.0%} is used here. Disagree with any of
    them and the whole page recalculates.</p>
</section>

<section>
  <h2>Demand against what the ground can take</h2>
  <div class="chartbox">{demand_chart(records)}</div>
  <p class="note">"Can process" is standing capacity multiplied by how many
    times the space turns over in an hour at a {C.GHAT_DWELL_MINUTES:.0f}-minute dwell.
    Throughput, not instantaneous capacity, is what binds at a bathing ghat:
    people arrive, bathe and leave.</p>
</section>

{worked_example(records)}

<section>
  <h2>All four sites</h2>
  <div id="map" style="height:420px;border-radius:12px;overflow:hidden"></div>
  <table class="portfolio" id="pf">
    <thead><tr>
      <th>Site</th><th>Peak-hour arrivals</th><th>Can process</th>
      <th>Ratio</th><th>Nowhere to go</th><th>Narrowest route</th><th>Risk</th>
    </tr></thead>
    <tbody>{_rows(records)}</tbody>
  </table>
  <p class="note">Click a column heading to sort.</p>
</section>

<section>
  <p class="eyebrow">Single points of failure</p>
  <h2>How much rides on one route</h2>
  <p class="lede">At Prayagraj in 2025 the crush was made worse by exits and
    pontoon bridges being <b>closed while people were already moving</b>. The
    capacity existed on paper and was not available on the night. So each site
    is also tested by removing one thing at a time.</p>
  <div class="chartbox">{failure_chart(records)}</div>
  <p class="note">Share of a site's total exit capacity carried by its single
    busiest route. Above {C.SINGLE_ROUTE_SHARE_FLAG:.0%} there is no meaningful
    alternative: closing it is not a degradation, it is an incident. The same
    test runs over holding grounds and over toilet and water clusters.</p>
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
    An unresolved check is reported as unresolved and scored as clear, so every
    score here is a lower bound.</p>
</section>

{value_section(records)}

<section class="limits">
  <p class="eyebrow">Read this part</p>
  <h2>Six things this gets wrong &mdash; and why they are published</h2>
  <ol class="limitlist">
    <li><b>OpenStreetMap is not an asset register.</b> A toilet that exists but
      was never mapped counts as missing, so the sanitation gaps are an upper
      bound until the authority supplies its own inventory.</li>
    <li><b>Most road widths are inferred, not measured.</b> Indian streets
      rarely carry a width tag, so widths come from road class. Each card says
      what share was inferred; this is the first thing a site visit replaces.</li>
    <li><b>Open ground is an upper bound.</b> It is the precinct less buildings
      and water. Barriers, akhara enclosures, vehicle routes and stalls all
      take more away.</li>
    <li><b>The arrival assumptions are assumptions.</b> Peak-day and peak-hour
      shares are reasoned from Prayagraj 2025, not observed at Nashik, and the
      site weights are a planning split rather than a forecast.</li>
    <li><b>Queueing assumes people spread evenly between blocks.</b> They do
      not, so real waits are worse than the figures here.</li>
    <li><b>Nothing here models behaviour.</b> Crowd collapse is a dynamic
      process; this is a static capacity check. It finds sites that cannot work
      arithmetically. A site that passes still needs a simulation.</li>
  </ol>
  <p class="note">And the standing rule: <b>this is a screening tool, not a
    safety case.</b> It is not a prediction of harm, and not a statement about
    any authority's preparations.</p>
</section>

<footer class="sitefoot">
  <p><b>Sources</b> &middot; Geometry and facilities: OpenStreetMap contributors
     (ODbL) &middot; Toilet and water norms: CPHEEO, Advisory on Public and
     Community Toilets &middot; Crowd density bands after Fruin; critical
     density after G. Keith Still &middot; Event dates and attendance:
     Maharashtra government announcements &middot; 2003 and 2025 incident
     details from published reports.</p>
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
