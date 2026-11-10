"""Toilets and drinking water: what the norms require, what is on the ground,
and how long the queue gets. Pure functions.

Required counts follow CPHEEO's Advisory on Public and Community Toilets.
Queueing uses Erlang C, computed by the numerically stable Erlang B
recursion so it holds up at the thousands-of-units scale this event needs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from . import config as C


def _na(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def _ceil_div(n: float, d: float) -> int:
    """CPHEEO says 'or part thereof' throughout, so always round up."""
    return int(math.ceil(n / d)) if d else 0


# --- Required units, CPHEEO public toilet norms ---------------------------


def public_wc_men(persons: float) -> int:
    """One per 100 up to 400 persons; above that one per 250 or part."""
    if persons <= 0:
        return 0
    if persons <= C.PT_MEN_WC_FIRST_BLOCK:
        return _ceil_div(persons, C.PT_MEN_WC_PER_FIRST)
    base = C.PT_MEN_WC_FIRST_BLOCK // C.PT_MEN_WC_PER_FIRST
    return base + _ceil_div(persons - C.PT_MEN_WC_FIRST_BLOCK, C.PT_MEN_WC_PER_ABOVE)


def public_wc_women(persons: float) -> int:
    """Two per 100 up to 200 persons; above that one per 100 or part."""
    if persons <= 0:
        return 0
    if persons <= C.PT_WOMEN_WC_FIRST_BLOCK:
        return 2 * _ceil_div(persons, C.PT_WOMEN_WC_PER_FIRST)
    base = 2 * (C.PT_WOMEN_WC_FIRST_BLOCK // C.PT_WOMEN_WC_PER_FIRST)
    return base + _ceil_div(persons - C.PT_WOMEN_WC_FIRST_BLOCK, C.PT_WOMEN_WC_PER_ABOVE)


def urinals_men(persons: float) -> int:
    """One per 50 persons or part thereof."""
    return _ceil_div(persons, C.PT_MEN_URINAL_PER) if persons > 0 else 0


def community_seats(persons: float, male_share: float = C.MALE_SHARE) -> dict:
    """Community toilet norms: one seat per 35 men, one per 25 women.

    The closer analogue for a temporary settlement than the public toilet
    table, and it demands roughly an order of magnitude more units.
    """
    if persons <= 0:
        return {"men": 0, "women": 0, "total": 0}
    men = _ceil_div(persons * male_share, C.CT_SEATS_PER_MAN)
    women = _ceil_div(persons * (1 - male_share), C.CT_SEATS_PER_WOMAN)
    return {"men": men, "women": women, "total": men + women}


def toilets_required(persons: float | None, male_share: float = C.MALE_SHARE) -> dict | None:
    """Required units under both CPHEEO tables, so the gap can be read either way."""
    if _na(persons) or persons <= 0:
        return None
    p = float(persons)
    men_p, women_p = p * male_share, p * (1 - male_share)
    pt_men, pt_women = public_wc_men(men_p), public_wc_women(women_p)
    ct = community_seats(p, male_share)
    return {
        "persons": round(p),
        "public_wc_men": pt_men,
        "public_wc_women": pt_women,
        "public_wc_total": pt_men + pt_women,
        "urinals_men": urinals_men(men_p),
        "community_seats_men": ct["men"],
        "community_seats_women": ct["women"],
        "community_seats_total": ct["total"],
    }


def water_taps_required(persons: float | None) -> int | None:
    """One tap with drainage per 50 persons or part thereof."""
    if _na(persons) or persons <= 0:
        return None
    return _ceil_div(float(persons), C.WATER_TAP_PER)


# --- Queueing --------------------------------------------------------------


def _erlang_b(load: float, servers: int) -> float:
    """Erlang B by recursion — stable for thousands of servers."""
    b = 1.0
    for k in range(1, servers + 1):
        b = (load * b) / (k + load * b)
    return b


def erlang_c(load: float, servers: int) -> float:
    """Probability an arrival has to wait. `load` is offered load in erlangs."""
    if servers <= 0:
        return 1.0
    if load >= servers:
        return 1.0
    b = _erlang_b(load, servers)
    rho = load / servers
    denom = 1.0 - rho * (1.0 - b)
    return 1.0 if denom <= 0 else min(1.0, b / denom)


@dataclass
class Queue:
    units: int
    demand_per_hour: float
    capacity_per_hour: float
    utilisation: float | None
    wait_minutes: float | None
    stable: bool
    backlog_per_hour: float

    def as_dict(self) -> dict:
        return asdict(self)


def queue_state(
    units: int | None,
    users_per_hour: float | None,
    service_minutes: float,
) -> Queue | None:
    """How long the queue gets, given units, demand and service time.

    When demand exceeds capacity there is no steady-state wait: the queue
    grows without bound. Reporting a finite number there would be the most
    misleading thing this model could do, so it reports the growth rate
    instead.
    """
    if _na(units) or _na(users_per_hour) or service_minutes <= 0:
        return None
    units = int(units)
    lam = float(users_per_hour)
    mu = 60.0 / service_minutes                      # services per unit per hour
    capacity = units * mu
    load = lam / mu if mu else 0.0                   # erlangs

    if units <= 0 or lam <= 0:
        return Queue(units, round(lam), round(capacity), None, None, units > 0, 0.0)

    if lam >= capacity:
        return Queue(
            units, round(lam), round(capacity),
            round(lam / capacity, 2) if capacity else None,
            None, False, round(lam - capacity),
        )

    c = erlang_c(load, units)
    wait_hours = c / (units * mu - lam)
    return Queue(
        units, round(lam), round(capacity),
        round(load / units, 3), round(wait_hours * 60.0, 2), True, 0.0,
    )


def queue_state_blocked(
    units: int | None,
    users_per_hour: float | None,
    service_minutes: float,
    block_units: int = C.TOILET_BLOCK_UNITS,
) -> Queue | None:
    """The wait at one block, with demand shared evenly across blocks.

    Treating every unit on the site as one pooled queue makes the wait
    collapse towards zero whenever utilisation is below 1, which is not what
    anyone has ever experienced at a mela. Splitting demand across blocks of
    `block_units` reproduces the queue a person actually stands in. It still
    assumes people distribute themselves evenly between blocks, which they do
    not, so it remains an optimistic figure.
    """
    if _na(units) or _na(users_per_hour) or block_units <= 0:
        return None
    units = int(units)
    if units <= 0:
        return queue_state(units, users_per_hour, service_minutes)
    blocks = max(1, int(math.ceil(units / block_units)))
    per_block_units = max(1, units // blocks)
    per_block_demand = float(users_per_hour) / blocks
    q = queue_state(per_block_units, per_block_demand, service_minutes)
    if q is None:
        return None
    # report site-wide totals with the per-block wait
    return Queue(
        units=units,
        demand_per_hour=round(float(users_per_hour)),
        capacity_per_hour=round(q.capacity_per_hour * blocks),
        utilisation=q.utilisation,
        wait_minutes=q.wait_minutes,
        stable=q.stable,
        backlog_per_hour=round(q.backlog_per_hour * blocks),
    )


def units_for_target_wait(
    users_per_hour: float | None,
    service_minutes: float,
    target_wait_min: float = C.TARGET_QUEUE_WAIT_MIN,
    cap: int = 2_000_000,
    block_units: int = C.TOILET_BLOCK_UNITS,
) -> int | None:
    """Fewest units that keep the per-block wait within the target. CPHEEO
    designs to peak-hour demand against a 5-10 minute wait."""
    if _na(users_per_hour) or users_per_hour <= 0 or service_minutes <= 0:
        return None
    mu = 60.0 / service_minutes
    n = max(1, int(math.ceil(users_per_hour / mu)))
    while n < cap:
        q = queue_state_blocked(n, users_per_hour, service_minutes, block_units)
        if q and q.stable and q.wait_minutes is not None and q.wait_minutes <= target_wait_min:
            return n
        n += max(1, n // 50)
    return None


# --- Demand ----------------------------------------------------------------


def toilet_users_per_hour(
    people_present: float | None, use_rate: float = C.TOILET_USE_RATE_PEAK_HOUR
) -> float | None:
    if _na(people_present):
        return None
    return round(float(people_present) * use_rate)


def water_users_per_hour(
    people_present: float | None, use_rate: float = C.WATER_USE_RATE_PEAK_HOUR
) -> float | None:
    if _na(people_present):
        return None
    return round(float(people_present) * use_rate)


# --- Gap -------------------------------------------------------------------


def gap(required: int | None, mapped: int | None) -> dict | None:
    """Shortfall against the norm, and what share of it is missing."""
    if _na(required) or required <= 0:
        return None
    have = 0 if _na(mapped) else int(mapped)
    short = max(0, int(required) - have)
    return {
        "required": int(required),
        "mapped": have,
        "shortfall": short,
        "share_missing": round(short / int(required), 3),
    }


def coverage_share(
    points_in_range: int | None, area_m2: float | None, radius_m: float = C.CT_WALK_DISTANCE_M
) -> float | None:
    """Rough share of an area lying within walking distance of a facility.

    Each facility is credited with a circle of `radius_m`, capped at 1.0. It
    ignores overlap and street-network detour, so it flatters the real
    picture and is reported as an upper bound.
    """
    if _na(points_in_range) or _na(area_m2) or area_m2 <= 0:
        return None
    covered = int(points_in_range) * math.pi * radius_m**2
    return round(min(1.0, covered / float(area_m2)), 3)
