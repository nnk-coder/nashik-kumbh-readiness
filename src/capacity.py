"""Crowd capacity, throughput, egress and overflow. Pure functions.

No network, no OpenStreetMap, no Earth Engine — everything here takes plain
numbers so the judgement can be unit tested in milliseconds and argued with
line by line. The GIS layer supplies areas and widths; this decides what they
mean.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Iterable, Sequence

from . import config as C


def _na(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


# --- Density ---------------------------------------------------------------


def fruin_band(density: float | None) -> tuple[str, str] | None:
    """Level-of-service letter and what it feels like, or None if unknown."""
    if _na(density):
        return None
    d = float(density)
    for lo, hi, letter, meaning in C.FRUIN_BANDS:
        if lo <= d < hi:
            return (letter, meaning)
    return ("F", C.FRUIN_BANDS[-1][3])


def holding_capacity(area_m2: float | None, density: float = C.DENSITY_PLANNING) -> float | None:
    """How many people an area holds at a given density."""
    if _na(area_m2) or area_m2 <= 0:
        return None
    return round(float(area_m2) * density)


def density_at(area_m2: float | None, people: float | None) -> float | None:
    if _na(area_m2) or _na(people) or area_m2 <= 0:
        return None
    return round(float(people) / float(area_m2), 2)


# --- Flow ------------------------------------------------------------------


def effective_width(width_m: float | None) -> float | None:
    """Usable width after the boundary layer lost at each edge.

    A 4 m lane with stalls down both sides does not move 4 m of crowd.
    """
    if _na(width_m):
        return None
    w = float(width_m) - 2 * C.BOUNDARY_LAYER_M
    return round(max(0.0, w), 2)


def flow_capacity_per_min(
    width_m: float | None, specific_flow: float = C.SPECIFIC_FLOW_PLANNING
) -> float | None:
    """People per minute a route of this width can pass."""
    ew = effective_width(width_m)
    if ew is None or ew <= 0:
        return None
    return round(ew * specific_flow)


def egress_time_min(
    population: float | None,
    total_exit_width_m: float | None,
    specific_flow: float = C.SPECIFIC_FLOW_PLANNING,
) -> float | None:
    """Minutes to clear a site through its exits, ignoring travel distance.

    This is the optimistic bound: it assumes orderly flow at the planning
    rate and no counter-flow. A real evacuation is slower.
    """
    if _na(population) or population <= 0:
        return 0.0
    cap = flow_capacity_per_min(total_exit_width_m, specific_flow)
    if cap is None or cap <= 0:
        return None
    return round(float(population) / cap, 1)


# --- Throughput, which is what actually binds ------------------------------


def site_throughput_per_hour(
    area_m2: float | None,
    dwell_minutes: float = C.GHAT_DWELL_MINUTES,
    density: float = C.DENSITY_PLANNING,
) -> float | None:
    """How many people can pass through a bathing area in an hour.

    Instantaneous capacity is the wrong measure for a ghat: people arrive,
    bathe and leave. Throughput is capacity multiplied by how many times the
    space turns over in an hour.
    """
    cap = holding_capacity(area_m2, density)
    if cap is None or dwell_minutes <= 0:
        return None
    return round(cap * (60.0 / float(dwell_minutes)))


# --- Demand ----------------------------------------------------------------


def peak_hour_arrivals(
    total_attendance: float = C.ATTENDANCE_EXPECTED,
    site_weight: float = 1.0,
    peak_day_share: float = C.PEAK_DAY_SHARE,
    peak_hour_share: float = C.PEAK_HOUR_SHARE,
) -> float:
    """People presenting at one site in the busiest hour of the busiest day."""
    return round(total_attendance * peak_day_share * peak_hour_share * site_weight)


@dataclass
class Breach:
    demand: float
    capacity: float
    surplus: float
    ratio: float | None

    def as_dict(self) -> dict:
        return asdict(self)


def breach(demand: float | None, capacity: float | None) -> Breach | None:
    """By how much peak-hour demand exceeds what a site can process."""
    if _na(demand) or _na(capacity):
        return None
    surplus = max(0.0, float(demand) - float(capacity))
    ratio = round(float(demand) / float(capacity), 2) if capacity else None
    return Breach(round(float(demand)), round(float(capacity)), round(surplus), ratio)


# --- Overflow --------------------------------------------------------------


def overflow_allocation(
    surplus: float | None,
    candidates: Sequence[dict],
    density: float = C.OVERFLOW_HOLDING_DENSITY,
) -> dict:
    """Place the people a site cannot process into nearby holding areas.

    `candidates` are open spaces: {"name", "area_m2", "distance_m"}. They are
    filled nearest first, because a crowd diverted further is a crowd that
    will not go. Returns what is absorbed, by where, and what is left over —
    the residual is the number that has to be held upstream, at the railway
    stations and road approaches, before it ever reaches the ghat.
    """
    if _na(surplus) or surplus <= 0:
        return {"surplus": 0, "allocated": [], "absorbed": 0, "residual": 0}

    usable = sorted(
        (c for c in candidates if not _na(c.get("area_m2")) and c["area_m2"] > 0),
        key=lambda c: c.get("distance_m", 0) or 0,
    )
    remaining = float(surplus)
    allocated = []
    for c in usable:
        if remaining <= 0:
            break
        cap = holding_capacity(c["area_m2"], density) or 0
        take = min(cap, remaining)
        if take <= 0:
            continue
        allocated.append(
            {
                "name": c.get("name") or "unnamed open space",
                "distance_m": round(c.get("distance_m") or 0),
                "capacity": cap,
                "holds": round(take),
            }
        )
        remaining -= take
    return {
        "surplus": round(float(surplus)),
        "allocated": allocated,
        "absorbed": round(float(surplus) - remaining),
        "residual": round(max(0.0, remaining)),
    }


def hold_upstream_duration_min(
    residual: float | None, throughput_per_hour: float | None
) -> float | None:
    """Minutes the residual crowd must be held before the site can take it."""
    if _na(residual) or residual <= 0:
        return 0.0
    if _na(throughput_per_hour) or throughput_per_hour <= 0:
        return None
    return round(float(residual) / float(throughput_per_hour) * 60.0, 1)


# --- Chokepoints -----------------------------------------------------------


def narrowest_link(links: Iterable[dict]) -> dict | None:
    """The tightest segment on an approach route — where a crush starts.

    `links` are {"name", "width_m", ...}. The 2003 Ramkund deaths happened on
    exactly such a link, not at the water's edge.
    """
    usable = [l for l in links if not _na(l.get("width_m"))]
    if not usable:
        return None
    worst = min(usable, key=lambda l: float(l["width_m"]))
    out = dict(worst)
    out["effective_width_m"] = effective_width(worst["width_m"])
    out["flow_per_min"] = flow_capacity_per_min(worst["width_m"])
    return out
