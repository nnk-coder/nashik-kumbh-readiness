"""Orchestration: one site in, one readiness record out.

The only module that touches both the network and the analysis. Per-site
failures are caught and recorded rather than ending the run.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
from pathlib import Path
from typing import Any, Sequence

from . import capacity as CAP
from . import config as C
from . import geo, sanitation as SAN


def _na(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def traffic_light(score: float) -> str:
    for lo, hi, label in C.TRAFFIC_LIGHT_BANDS:
        if lo <= score < hi:
            return label
    return "red"


def assess_site(
    site: dict,
    elements: Sequence[dict] | None = None,
    attendance: float = C.ATTENDANCE_EXPECTED,
    as_of: str | None = None,
) -> dict:
    """Measure one bathing site and apply the rubric."""
    as_of = as_of or _dt.date.today().isoformat()
    lat, lon = site["lat"], site["lon"]

    rec: dict[str, Any] = {
        **{k: site[k] for k in ("id", "name", "city", "lat", "lon", "weight", "note")},
        "as_of": as_of,
        "radius_m": C.OSM_RADIUS_M,
        "assembly_radius_m": C.ASSEMBLY_RADIUS_M,
        "errors": [],
    }

    if elements is None:
        from . import osm
        try:
            elements = osm.fetch(lat, lon, C.OSM_RADIUS_M)
        except Exception as exc:  # noqa: BLE001
            rec["errors"].append(f"overpass: {exc}")
            elements = []
    rec["osm_elements"] = len(elements)

    # --- the ground ------------------------------------------------------
    try:
        area = geo.assembly_area_m2(elements, lat, lon, C.ASSEMBLY_RADIUS_M)
        rec.update(area)
    except Exception as exc:  # noqa: BLE001
        rec["errors"].append(f"area: {exc}")
        rec["open_m2"] = None

    # --- the routes ------------------------------------------------------
    try:
        links = geo.approach_links(elements, lat, lon, C.OSM_RADIUS_M)
        rec["approach_links"] = links[:12]
        rec["approach_count"] = len(links)
        rec["total_approach_width_m"] = round(sum(l["width_m"] for l in links), 1) or None
        rec["narrowest"] = CAP.narrowest_link(links)
        rec["inferred_width_share"] = (
            round(sum(1 for l in links if l["width_source"] != "tagged") / len(links), 2)
            if links else None
        )
    except Exception as exc:  # noqa: BLE001
        rec["errors"].append(f"links: {exc}")
        rec["narrowest"] = None
        rec["total_approach_width_m"] = None

    # --- demand against capacity ----------------------------------------
    rec["peak_hour_arrivals"] = CAP.peak_hour_arrivals(attendance, site["weight"])
    rec["holding_capacity"] = CAP.holding_capacity(rec.get("open_m2"))
    rec["throughput_per_hour"] = CAP.site_throughput_per_hour(rec.get("open_m2"))
    rec["density_if_all_present"] = CAP.density_at(
        rec.get("open_m2"), rec["peak_hour_arrivals"]
    )
    band = CAP.fruin_band(rec["density_if_all_present"])
    rec["fruin_band"] = band[0] if band else None
    rec["fruin_meaning"] = band[1] if band else None

    b = CAP.breach(rec["peak_hour_arrivals"], rec["throughput_per_hour"])
    rec["breach"] = b.as_dict() if b else None

    rec["egress_time_min"] = CAP.egress_time_min(
        rec["holding_capacity"], rec.get("total_approach_width_m")
    )

    # --- what happens when it breaches -----------------------------------
    try:
        spaces = geo.open_spaces(elements, lat, lon)
        rec["open_spaces"] = spaces[:10]
        surplus = (rec["breach"] or {}).get("surplus")
        rec["overflow"] = CAP.overflow_allocation(surplus, spaces)
        rec["hold_upstream_min"] = CAP.hold_upstream_duration_min(
            rec["overflow"]["residual"], rec["throughput_per_hour"]
        )
    except Exception as exc:  # noqa: BLE001
        rec["errors"].append(f"overflow: {exc}")
        rec["overflow"] = None

    # --- toilets and water -----------------------------------------------
    # People present at once, not arrivals over the hour: sanitation is sized
    # on who is standing there.
    present = rec["holding_capacity"] or rec["peak_hour_arrivals"]
    rec["present_for_sanitation"] = present

    try:
        req = SAN.toilets_required(present)
        rec["toilets_required"] = req
        toilets = geo.amenity_points(elements, "toilets")
        rec["toilets_mapped"] = len(toilets)
        rec["toilet_gap"] = SAN.gap(
            req["community_seats_total"] if req else None, len(toilets)
        )
        users = SAN.toilet_users_per_hour(present)
        rec["toilet_users_per_hour"] = users
        q_mapped = SAN.queue_state_blocked(len(toilets), users, C.TOILET_SERVICE_MINUTES)
        rec["toilet_queue_as_mapped"] = q_mapped.as_dict() if q_mapped else None
        q_norm = SAN.queue_state_blocked(
            (req or {}).get("community_seats_total"), users, C.TOILET_SERVICE_MINUTES
        )
        rec["toilet_queue_at_norm"] = q_norm.as_dict() if q_norm else None
        rec["toilets_for_target_wait"] = SAN.units_for_target_wait(
            users, C.TOILET_SERVICE_MINUTES
        )
    except Exception as exc:  # noqa: BLE001
        rec["errors"].append(f"toilets: {exc}")
        rec["toilet_gap"] = None

    try:
        taps_req = SAN.water_taps_required(present)
        rec["water_taps_required"] = taps_req
        taps = geo.amenity_points(elements, "drinking_water")
        rec["water_points_mapped"] = len(taps)
        rec["water_gap"] = SAN.gap(taps_req, len(taps))
        wusers = SAN.water_users_per_hour(present)
        rec["water_users_per_hour"] = wusers
        q = SAN.queue_state_blocked(
            len(taps), wusers, C.WATER_SERVICE_MINUTES, C.WATER_BLOCK_UNITS
        )
        rec["water_queue_as_mapped"] = q.as_dict() if q else None
        rec["water_points_for_target_wait"] = SAN.units_for_target_wait(
            wusers, C.WATER_SERVICE_MINUTES, block_units=C.WATER_BLOCK_UNITS
        )
    except Exception as exc:  # noqa: BLE001
        rec["errors"].append(f"water: {exc}")
        rec["water_gap"] = None

    # --- rubric ------------------------------------------------------------
    flags = {
        "throughput_shortfall": bool(
            rec.get("breach") and rec["breach"]["surplus"] > C.THROUGHPUT_SHORTFALL_FLAG
        ),
        "egress_time": bool(
            not _na(rec.get("egress_time_min"))
            and rec["egress_time_min"] > C.EGRESS_TIME_FLAG_MIN
        ),
        "chokepoint": bool(
            rec.get("narrowest")
            and not _na(rec["narrowest"].get("width_m"))
            and rec["narrowest"]["width_m"] < C.CHOKEPOINT_MIN_WIDTH_M
        ),
        "toilet_gap": bool(
            rec.get("toilet_gap")
            and rec["toilet_gap"]["share_missing"] > C.TOILET_GAP_FLAG
        ),
        "water_gap": bool(
            rec.get("water_gap") and rec["water_gap"]["share_missing"] > C.WATER_GAP_FLAG
        ),
    }
    rec["flags"] = flags
    rec["score"] = round(
        min(100.0, sum(C.READINESS_WEIGHTS[k] for k, v in flags.items() if v)), 1
    )
    rec["traffic_light"] = traffic_light(rec["score"])

    resolved = [
        rec.get("open_m2"),
        rec.get("total_approach_width_m"),
        (rec.get("narrowest") or {}).get("width_m"),
        rec.get("toilet_gap"),
        rec.get("water_gap"),
    ]
    rec["evidence_completeness"] = round(
        sum(1 for v in resolved if v is not None) / len(resolved), 2
    )
    return rec


def assess_all(
    sites: Sequence[dict] | None = None,
    attendance: float = C.ATTENDANCE_EXPECTED,
    as_of: str | None = None,
) -> list[dict]:
    out = []
    for s in sites or C.SITES:
        rec = assess_site(s, attendance=attendance, as_of=as_of)
        out.append(rec)
        print(
            f"  {rec['name'][:26]:<26} score {rec['score']:>5.1f} "
            f"{rec['traffic_light']:<5} open {(rec.get('open_m2') or 0):>9,} m2"
            + (f"  [{len(rec['errors'])} error(s)]" if rec["errors"] else "")
        )
    return out


def save_results(records: list[dict], outputs_dir: str = "outputs") -> dict:
    out = Path(outputs_dir)
    out.mkdir(parents=True, exist_ok=True)

    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, float) and math.isnan(o):
            return None
        return o

    jp = out / "results.json"
    jp.write_text(json.dumps(clean(records), indent=2, default=str))

    import pandas as pd

    flat = [
        {
            "id": r.get("id"), "name": r.get("name"), "city": r.get("city"),
            "open_m2": r.get("open_m2"),
            "peak_hour_arrivals": r.get("peak_hour_arrivals"),
            "throughput_per_hour": r.get("throughput_per_hour"),
            "surplus": (r.get("breach") or {}).get("surplus"),
            "demand_capacity_ratio": (r.get("breach") or {}).get("ratio"),
            "density_if_all_present": r.get("density_if_all_present"),
            "fruin_band": r.get("fruin_band"),
            "narrowest_m": (r.get("narrowest") or {}).get("width_m"),
            "egress_time_min": r.get("egress_time_min"),
            "overflow_absorbed": (r.get("overflow") or {}).get("absorbed"),
            "overflow_residual": (r.get("overflow") or {}).get("residual"),
            "hold_upstream_min": r.get("hold_upstream_min"),
            "toilets_required": (r.get("toilets_required") or {}).get("community_seats_total"),
            "toilets_mapped": r.get("toilets_mapped"),
            "toilets_for_target_wait": r.get("toilets_for_target_wait"),
            "water_taps_required": r.get("water_taps_required"),
            "water_points_mapped": r.get("water_points_mapped"),
            "score": r.get("score"), "traffic_light": r.get("traffic_light"),
            "evidence_completeness": r.get("evidence_completeness"),
            **{f"flag_{k}": v for k, v in (r.get("flags") or {}).items()},
        }
        for r in records
    ]
    cp = out / "results.csv"
    pd.DataFrame(flat).to_csv(cp, index=False)
    return {"json": str(jp), "csv": str(cp)}
