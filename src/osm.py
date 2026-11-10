"""OpenStreetMap extraction through the Overpass API. The only networked module.

Everything it returns is plain JSON for src/geo.py to turn into geometry, so
the analysis can be tested without touching the network.
"""

from __future__ import annotations

import time

import requests

from . import config as C

_QUERY = """
[out:json][timeout:{timeout}];
(
  way(around:{radius},{lat},{lon})["building"];
  way(around:{radius},{lat},{lon})["natural"="water"];
  way(around:{radius},{lat},{lon})["waterway"~"riverbank|river"];
  way(around:{radius},{lat},{lon})["landuse"="reservoir"];
  way(around:{radius},{lat},{lon})["highway"];
  way(around:{radius},{lat},{lon})["leisure"];
  way(around:{radius},{lat},{lon})["landuse"];
  way(around:{radius},{lat},{lon})["amenity"];
  node(around:{radius},{lat},{lon})["amenity"];
);
out geom center tags;
"""


def fetch(lat: float, lon: float, radius_m: int = C.OSM_RADIUS_M, retries: int = 3) -> list[dict]:
    """Every feature within `radius_m` of a point.

    Overpass is a free public service and rate-limits; failures are retried
    with a growing pause rather than hammered.
    """
    q = _QUERY.format(
        timeout=C.OVERPASS_TIMEOUT_S, radius=int(radius_m), lat=lat, lon=lon
    )
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(
                C.OVERPASS_URL,
                data={"data": q},
                timeout=C.OVERPASS_TIMEOUT_S + 30,
                headers={"User-Agent": "nashik-kumbh-readiness/0.1 (open-data prototype)"},
            )
            if r.status_code == 200:
                return r.json().get("elements", [])
            last = f"HTTP {r.status_code}"
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Overpass failed after {retries} attempts: {last}")
