"""Single points of failure: what one closure would do.

A site can pass every capacity check and still be one blocked lane away from a
disaster. At Prayagraj in 2025 the crush was made worse by exits and pontoon
bridges being closed while people were already moving — the capacity existed
on paper and was not available on the night.

Everything here is leave-one-out: remove one facility, recompute, and report
what changed. Pure functions; the GIS layer supplies the inventory.
"""

from __future__ import annotations

import math
from typing import Sequence

from . import capacity as CAP
from . import config as C
from . import sanitation as SAN


def _na(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def concentration(values: Sequence[float]) -> float | None:
    """Share of the total carried by the single largest item.

    1.0 means one facility carries everything. It is the quickest read on
    whether a site has redundancy at all.
    """
    vals = [float(v) for v in values if not _na(v) and float(v) > 0]
    if not vals:
        return None
    return round(max(vals) / sum(vals), 3)


# --- routes ----------------------------------------------------------------


def route_criticality(links: Sequence[dict], population: float | None) -> list[dict]:
    """Close each approach route in turn and see what it costs.

    Reported per route: the share of exit capacity it carries, and how much
    longer clearing the site would take without it.
    """
    usable = [l for l in links if not _na(l.get("width_m"))]
    if not usable or _na(population) or population <= 0:
        return []

    flows = {l["name"]: (CAP.flow_capacity_per_min(l["width_m"]) or 0.0) for l in usable}
    total = sum(flows.values())
    if total <= 0:
        return []
    base_min = float(population) / total

    out = []
    for l in usable:
        f = flows[l["name"]]
        remaining = total - f
        if remaining <= 0:
            without, delta = None, None  # closing it strands the site entirely
        else:
            without = round(float(population) / remaining, 1)
            delta = round(without - base_min, 1)
        out.append(
            {
                "name": l["name"],
                "width_m": l["width_m"],
                "flow_per_min": round(f),
                "share_of_exit_capacity": round(f / total, 3),
                "egress_without_min": without,
                "egress_delta_min": delta,
                "strands_site": remaining <= 0,
            }
        )
    return sorted(out, key=lambda r: -r["share_of_exit_capacity"])


# --- overflow holding areas ------------------------------------------------


def overflow_criticality(
    surplus: float | None,
    spaces: Sequence[dict],
    density: float = C.OVERFLOW_HOLDING_DENSITY,
) -> list[dict]:
    """Lose each holding area in turn and see how many more are stranded.

    A maidan that is waterlogged in the monsoon, fenced off for works or taken
    for parking stops being a holding area on the day. These Snans fall in
    August and September, so that is not a hypothetical.
    """
    if _na(surplus) or surplus <= 0 or not spaces:
        return []
    base = CAP.overflow_allocation(surplus, spaces, density)
    out = []
    for i, s in enumerate(spaces):
        without = CAP.overflow_allocation(
            surplus, [x for j, x in enumerate(spaces) if j != i], density
        )
        extra = without["residual"] - base["residual"]
        if extra <= 0:
            continue
        out.append(
            {
                "name": s.get("name") or "unnamed open space",
                "kind": s.get("kind"),
                "distance_m": round(s.get("distance_m") or 0),
                "capacity": CAP.holding_capacity(s.get("area_m2"), density),
                "extra_stranded": round(extra),
                "share_of_surplus": round(extra / float(surplus), 3),
            }
        )
    return sorted(out, key=lambda r: -r["extra_stranded"])


# --- toilets and water -----------------------------------------------------


def facility_criticality(
    cluster_sizes: Sequence[int],
    users_per_hour: float | None,
    service_minutes: float,
    block_units: int = C.TOILET_BLOCK_UNITS,
) -> dict | None:
    """Lose the largest cluster of units and see what the queue does.

    When a toilet block goes out of service its demand does not vanish, it
    walks to the next one. That is how a sanitation failure becomes a crowd
    problem: people moving unpredictably through a dense site, looking.
    """
    sizes = [int(s) for s in cluster_sizes if not _na(s) and int(s) > 0]
    if not sizes or _na(users_per_hour) or users_per_hour <= 0:
        return None

    total = sum(sizes)
    largest = max(sizes)
    before = SAN.queue_state_blocked(total, users_per_hour, service_minutes, block_units)
    after = SAN.queue_state_blocked(
        total - largest, users_per_hour, service_minutes, block_units
    )
    return {
        "clusters": len(sizes),
        "units_total": total,
        "largest_cluster": largest,
        "concentration": concentration(sizes),
        "wait_before_min": before.wait_minutes if before else None,
        "wait_after_min": after.wait_minutes if after else None,
        "stable_before": before.stable if before else None,
        "stable_after": after.stable if after else None,
        "tips_into_failure": bool(before and after and before.stable and not after.stable),
    }


# --- the summary -----------------------------------------------------------


def single_point_summary(
    routes: Sequence[dict],
    overflow: Sequence[dict],
    toilets: dict | None,
    water: dict | None,
) -> dict:
    """The worst single failure at this site, and whether it is flagged.

    A site with one dominant route, one dominant holding area or one dominant
    toilet cluster has no redundancy, and redundancy is the whole of crowd
    safety planning once capacity is set.
    """
    worst_route = routes[0] if routes else None
    worst_space = overflow[0] if overflow else None

    route_share = (worst_route or {}).get("share_of_exit_capacity")
    space_share = (worst_space or {}).get("share_of_surplus")

    flagged = any(
        [
            bool(worst_route and worst_route.get("strands_site")),
            bool(route_share is not None and route_share > C.SINGLE_ROUTE_SHARE_FLAG),
            bool(space_share is not None and space_share > C.SINGLE_SPACE_SHARE_FLAG),
            bool(toilets and toilets.get("tips_into_failure")),
            bool(water and water.get("tips_into_failure")),
            bool(
                toilets
                and toilets.get("concentration") is not None
                and toilets["concentration"] > C.FACILITY_CONCENTRATION_FLAG
            ),
        ]
    )

    reasons = []
    if worst_route and worst_route.get("strands_site"):
        reasons.append(
            f"{worst_route['name']} is the only resolved way in or out — closing it strands the site"
        )
    elif route_share is not None and route_share > C.SINGLE_ROUTE_SHARE_FLAG:
        reasons.append(
            f"{worst_route['name']} carries {route_share:.0%} of exit capacity; "
            f"closing it adds {worst_route['egress_delta_min']:.0f} minutes to clearing the site"
        )
    if space_share is not None and space_share > C.SINGLE_SPACE_SHARE_FLAG:
        reasons.append(
            f"{worst_space['name']} absorbs {space_share:.0%} of the overflow; "
            f"losing it strands {worst_space['extra_stranded']:,} more people"
        )
    if toilets and toilets.get("tips_into_failure"):
        reasons.append(
            f"losing the largest toilet cluster ({toilets['largest_cluster']} units) "
            f"tips the queue from {toilets['wait_before_min']:.0f} minutes into one that never clears"
        )
    if water and water.get("tips_into_failure"):
        reasons.append("losing the largest water point cluster tips its queue into one that never clears")
    if (
        toilets
        and toilets.get("concentration") is not None
        and toilets["concentration"] > C.FACILITY_CONCENTRATION_FLAG
        and not any("toilet" in r for r in reasons)
    ):
        reasons.append(
            f"{toilets['concentration']:.0%} of mapped toilet units sit in a single cluster"
        )

    return {
        "flagged": flagged,
        "reasons": reasons,
        "worst_route": worst_route,
        "worst_space": worst_space,
        "toilets": toilets,
        "water": water,
    }
