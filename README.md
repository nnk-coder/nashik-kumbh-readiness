# Nashik Simhastha — Amrit Snan site readiness

Crowd capacity, overflow and sanitation at the Nashik–Trimbakeshwar Simhastha
bathing sites, measured entirely from open data.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/YOUR-GITHUB-USERNAME/nashik-kumbh-readiness/blob/main/notebooks/nashik_readiness.ipynb)

**[→ Published site](https://YOUR-GITHUB-USERNAME.github.io/nashik-kumbh-readiness/)**

---

## The question

The Simhastha runs from **31 October 2026 to 24 July 2028**, and the crush risk
concentrates on four Amrit Snan mornings: **2 and 31 August and 11 September
2027** at Nashik, **12 September** at Trimbakeshwar. The state expects around
**12 crore** visitors, roughly four times the 2.5 crore of 2015.

> In the busiest hour of the busiest morning, how many people can physically
> stand at each bathing site — and where do the ones who cannot go?

## Why Nashik is not Prayagraj

Nashik's planners have been studying Prayagraj 2025 as a template. On the two
risks that actually kill people, it does not transfer.

- **Prayagraj spreads onto open sandbanks. Nashik's ghats sit inside a dense
  historic city.** In 2003, 39 people died at Ramkund when about 30,000 were
  held on a narrow approach street. Prayagraj 2025's failures — a barrier
  breaking, exits and pontoon bridges closed — were failures of a wide site.
  Nashik's would be failures of a narrow one.
- **Prayagraj is in January. Nashik's Snans are in August and September** —
  monsoon and immediate post-monsoon, on a river that floods the city.

## What it measures

| Check | Weight | Method |
|---|---|---|
| **Can the site process the hour's arrivals?** | 30 | Open ground × density × turnover against assumed peak-hour arrivals |
| **Would one closure break the plan?** | 20 | Leave-one-out across routes, holding areas and facility clusters |
| **Can it be cleared in an emergency?** | 15 | Population ÷ effective exit width × specific flow |
| **Is any approach route dangerously narrow?** | 15 | Narrowest link on any route reaching the site |
| **Are there enough toilets?** | 10 | CPHEEO community toilet norm vs. what OSM maps |
| **Are there enough drinking water points?** | 10 | One tap per 50 people vs. what OSM maps |

Flags are weighted into a 0–100 risk score. Higher means *resolve this first*,
not *this will fail*.

### Single points of failure

A site can pass every capacity check and still be one blocked lane away from a
disaster. At Prayagraj in 2025 the crush was made worse by exits and pontoon
bridges being **closed while people were already moving** — the capacity
existed on paper and was not available on the night.

So each site is also tested by removing things one at a time:

- **Close each approach route** and recompute egress. A route carrying more
  than 40% of exit capacity has no real alternative; the card reports what
  closing it costs in minutes, and whether it strands the site entirely.
- **Lose each holding area** and recompute the residual. These Snans fall in
  August and September, so a maidan that is waterlogged, fenced for works or
  taken for parking is not a hypothetical.
- **Lose the largest facility cluster** and recompute the queue. Facilities
  within 120 m are treated as one cluster because they share a tanker, a
  desludging route and a power feed, so they fail together. The card flags
  when losing one tips a working queue into one that never clears — which is
  how a sanitation outage becomes a crowd problem, with demand walking off
  through a dense site to find the next block.

### The part most capacity studies skip

Reporting that a site is over capacity is easy. This also answers **what
happens to the surplus**: it finds every mapped open space within 1.2 km, fills
them nearest-first at a holding density, and reports the **residual** — the
number with nowhere to go, and how many minutes they must be held upstream at
the railway stations and road approaches before the ghat can take them.

Sanitation works the same way: not just how many toilets are missing, but the
**queue** — Erlang C, computed per block of 20 units rather than pooled across
the site, because people queue at the block in front of them.

## How it is built

```
src/config.py      every threshold, norm and assumption, with its source
src/capacity.py    crowd maths — pure, no network
src/sanitation.py  CPHEEO norms and queueing — pure, no network
src/resilience.py  leave-one-out failure analysis — pure, no network
src/geo.py         OSM elements → areas, routes, open space, clusters (shapely)
src/osm.py         the only networked module: Overpass queries
src/assess.py      orchestration; per-site failures are caught, not fatal
src/card.py        one readiness card per site
src/site.py        the published index
tests/             102 tests, no network, no credentials
```

Three deliberate choices:

1. **Every arguable number lives in `src/config.py`** — densities, flow rates,
   dwell time, arrival shares, toilet norms — with its source inline. Disagree
   with the 15% peak-day share and you change one line.
2. **The judgement is separate from the data.** `capacity.py` and
   `sanitation.py` have no network and no geometry, so the whole rubric is
   tested in under a second. `geo.py` is tested against a synthetic OSM extract
   built in the test file, so the full pipeline runs offline.
3. **A check that cannot be answered says so.** Unresolved checks are reported
   as unresolved and scored as clear, so every score is a lower bound, and each
   card shows how much of the rubric was resolved.

## Running it

**In Colab** — click the badge. No account, no API key, no credentials; about
five minutes.

**Locally:**

```bash
pip install -r requirements.txt
python -m pytest -q          # 102 tests, no network needed
python -c "
from src import assess, card, site
import datetime as dt
r = assess.assess_all()
assess.save_results(r); card.write_cards(r)
site.write_site(r, dt.date.today().isoformat())
"
```

Outputs land in `outputs/` and `docs/`. Enable GitHub Pages on the `docs/`
folder of `main` to publish.

## What this gets wrong

- **OpenStreetMap is not an asset register.** A toilet that exists but was
  never mapped counts as missing. Sanitation gaps are an upper bound until the
  Authority supplies its own inventory.
- **Most road widths are inferred from road class**, because Indian streets
  rarely carry a `width` tag. Each card reports what share was inferred. This
  is the weakest input and the first thing a site visit should replace.
- **Open ground is an upper bound** — the precinct less buildings and water.
  Barriers, akhara enclosures, vehicle routes and stalls take more away.
- **The arrival assumptions are assumptions.** Peak-day and peak-hour shares
  are reasoned from Prayagraj 2025, not observed at Nashik; site weights are a
  planning split, not a forecast.
- **Queueing assumes people distribute evenly between blocks.** They do not, so
  real waits are worse than reported.
- **Nothing here models behaviour.** Crowd collapse is dynamic; this is a
  static capacity check. It finds sites that cannot work arithmetically. A site
  that passes still needs a simulation.

**A screening tool, not a safety case.** Not a prediction of harm, and not a
statement about any authority's preparations.

## Sources

- Geometry and facilities — [OpenStreetMap](https://www.openstreetmap.org/) contributors, ODbL
- Toilet and water norms — CPHEEO, *Advisory on Public and Community Toilets*
- Crowd density bands after Fruin; critical density after G. Keith Still
- Event dates, attendance and budget — Maharashtra government announcements

Code MIT licensed. A personal methodology prototype, published as independent
work; not affiliated with, endorsed by, or produced for any authority.
