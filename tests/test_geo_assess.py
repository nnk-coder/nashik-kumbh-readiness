"""Geometry and end-to-end tests against a synthetic OpenStreetMap extract.

No network: the extract is fabricated here, so the whole pipeline from OSM
elements to a scored record runs offline and deterministically.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import assess as A  # noqa: E402
from src import config as C  # noqa: E402
from src import geo as G  # noqa: E402

LAT0, LON0 = 20.0, 73.8
M_PER_DEG_LAT = math.radians(1) * 6_378_137.0  # match geo.py's sphere


def _dlat(m):
    return m / M_PER_DEG_LAT


def _dlon(m):
    return m / (111_320.0 * math.cos(math.radians(LAT0)))


def _square(cx_m, cy_m, side_m, wid, tags):
    """A closed square way, centred cx/cy metres from the origin."""
    h = side_m / 2
    corners = [(-h, -h), (h, -h), (h, h), (-h, h), (-h, -h)]
    geom = [
        {"lat": LAT0 + _dlat(cy_m + dy), "lon": LON0 + _dlon(cx_m + dx)}
        for dx, dy in corners
    ]
    return {"type": "way", "id": wid, "tags": tags, "geometry": geom}


def _line(x0, y0, x1, y1, wid, tags):
    return {
        "type": "way",
        "id": wid,
        "tags": tags,
        "geometry": [
            {"lat": LAT0 + _dlat(y0), "lon": LON0 + _dlon(x0)},
            {"lat": LAT0 + _dlat(y1), "lon": LON0 + _dlon(x1)},
        ],
    }


def _node(x_m, y_m, nid, tags):
    return {
        "type": "node",
        "id": nid,
        "lat": LAT0 + _dlat(y_m),
        "lon": LON0 + _dlon(x_m),
        "tags": tags,
    }


def extract():
    els = []
    # four 40 m buildings near the centre
    for i, (x, y) in enumerate([(-80, -80), (80, -80), (-80, 80), (80, 80)]):
        els.append(_square(x, y, 40, 100 + i, {"building": "yes"}))
    # the river, a 200 m block south of centre
    els.append(_square(0, -400, 200, 200, {"natural": "water"}))
    # approach routes: one wide road, one narrow lane, both reaching past the radius
    R = C.OSM_RADIUS_M
    els.append(_line(-R * 1.2, 0, R * 1.2, 0, 300,
                     {"highway": "primary", "name": "Main Road"}))
    els.append(_line(0, -R * 1.2, 0, R * 1.2, 301,
                     {"highway": "residential", "name": "Temple Lane", "width": "3.5"}))
    els.append(_line(-R * 1.2, -R * 1.2, R * 1.2, R * 1.2, 302,
                     {"highway": "service", "name": "Back Alley"}))
    # a park for overflow
    els.append(_square(500, 500, 120, 400, {"leisure": "park", "name": "Maidan"}))
    els.append(_square(-900, 300, 80, 401, {"amenity": "parking", "name": "Bus Parking"}))
    # mapped facilities
    for i in range(6):
        els.append(_node(50 * i, 60, 500 + i, {"amenity": "toilets"}))
    for i in range(3):
        els.append(_node(-50 * i, -60, 600 + i, {"amenity": "drinking_water"}))
    return els


def dense_extract():
    """A built-up precinct: Ramkund sits inside a historic city, not a field."""
    els = [e for e in extract() if "building" not in (e.get("tags") or {})]
    wid = 2000
    for i in range(-6, 7):
        for j in range(-6, 7):
            els.append(_square(i * 40, j * 40, 36, wid, {"building": "yes"}))
            wid += 1
    return els


EXTRACT = extract()
DENSE = dense_extract()
SITE = {
    "id": "test", "name": "Test Ghat", "city": "Nashik",
    "lat": LAT0, "lon": LON0, "weight": 0.40, "note": "synthetic",
}


# --- projection ------------------------------------------------------------


def test_to_xy_origin_is_zero():
    assert G.to_xy(LAT0, LON0, LAT0, LON0) == (0.0, 0.0)


def test_to_xy_is_metric_north_and_east():
    x, y = G.to_xy(LAT0 + _dlat(100), LON0 + _dlon(250), LAT0, LON0)
    assert abs(y - 100) < 1.0
    assert abs(x - 250) < 1.0


def test_haversine_matches_the_local_plane_at_short_range():
    d = G.haversine_m(LAT0, LON0, LAT0 + _dlat(300), LON0)
    assert abs(d - 300) < 1.0


# --- area ------------------------------------------------------------------


def test_assembly_area_subtracts_buildings_and_water():
    a = G.assembly_area_m2(EXTRACT, LAT0, LON0, 600)
    assert a["building_count"] == 4
    assert a["building_m2"] > 0
    assert a["water_m2"] > 0
    assert a["open_m2"] < a["circle_m2"]
    assert a["open_m2"] + a["building_m2"] + a["water_m2"] <= a["circle_m2"] * 1.01


def test_assembly_area_of_empty_extract_is_the_whole_circle():
    a = G.assembly_area_m2([], LAT0, LON0, 500)
    assert a["building_m2"] == 0 and a["water_m2"] == 0
    assert abs(a["open_m2"] - a["circle_m2"]) < 2


# --- links -----------------------------------------------------------------


def test_approach_links_found_and_sorted_narrowest_first():
    links = G.approach_links(EXTRACT, LAT0, LON0, C.OSM_RADIUS_M)
    names = [l["name"] for l in links]
    assert "Main Road" in names and "Temple Lane" in names
    assert links[0]["width_m"] <= links[-1]["width_m"]


def test_tagged_width_beats_the_class_default():
    links = {l["name"]: l for l in G.approach_links(EXTRACT, LAT0, LON0, C.OSM_RADIUS_M)}
    assert links["Temple Lane"]["width_m"] == 3.5
    assert links["Temple Lane"]["width_source"] == "tagged"
    assert links["Main Road"]["width_source"].startswith("inferred")
    assert links["Main Road"]["width_m"] == C.WIDTH_BY_HIGHWAY["primary"]


def test_links_ignore_ways_that_do_not_reach_the_site():
    els = [_line(5000, 5000, 6000, 6000, 900, {"highway": "primary", "name": "Far Road"})]
    assert G.approach_links(els, LAT0, LON0, C.OSM_RADIUS_M) == []


# --- amenities and open space ---------------------------------------------


def test_amenity_points_counted():
    assert len(G.amenity_points(EXTRACT, "toilets")) == 6
    assert len(G.amenity_points(EXTRACT, "drinking_water")) == 3
    assert G.amenity_points(EXTRACT, "hospital") == []


def test_open_spaces_found_with_area_and_distance():
    spaces = G.open_spaces(EXTRACT, LAT0, LON0)
    names = [s["name"] for s in spaces]
    assert "Maidan" in names and "Bus Parking" in names
    assert all(s["area_m2"] > 0 and s["distance_m"] >= 0 for s in spaces)


def test_open_spaces_sorted_nearest_first():
    spaces = G.open_spaces(EXTRACT, LAT0, LON0)
    assert spaces == sorted(spaces, key=lambda s: s["distance_m"])


def test_count_within_radius():
    pts = G.amenity_points(EXTRACT, "toilets")
    assert G.count_within(pts, LAT0, LON0, 10_000) == 6
    assert G.count_within(pts, LAT0, LON0, 1) == 0


# --- end to end ------------------------------------------------------------


def test_assess_site_produces_a_scored_record():
    r = A.assess_site(SITE, elements=EXTRACT, attendance=120_000_000)
    assert r["errors"] == []
    assert r["open_m2"] > 0
    assert r["peak_hour_arrivals"] > 0
    assert 0.0 <= r["score"] <= 100.0
    assert r["traffic_light"] in ("green", "amber", "red")
    assert 0.0 <= r["evidence_completeness"] <= 1.0


def test_a_built_up_precinct_breaches_at_the_expected_attendance():
    """The whole point: 1.4 million arrivals an hour against the open ground
    left between buildings cannot clear."""
    r = A.assess_site(SITE, elements=DENSE, attendance=120_000_000)
    assert r["breach"]["surplus"] > 0
    assert r["flags"]["throughput_shortfall"] is True


def test_an_open_site_absorbs_what_a_built_up_one_cannot():
    """The model has to discriminate, or it is just asserting the conclusion."""
    dense = A.assess_site(SITE, elements=DENSE, attendance=120_000_000)
    open_ = A.assess_site(SITE, elements=EXTRACT, attendance=120_000_000)
    assert open_["open_m2"] > dense["open_m2"] * 3
    assert open_["throughput_per_hour"] > dense["throughput_per_hour"]
    assert dense["breach"]["surplus"] > open_["breach"]["surplus"]


def test_density_rises_as_open_ground_falls():
    dense = A.assess_site(SITE, elements=DENSE, attendance=120_000_000)
    open_ = A.assess_site(SITE, elements=EXTRACT, attendance=120_000_000)
    assert dense["density_if_all_present"] > open_["density_if_all_present"]


def test_overflow_absorbed_plus_residual_equals_surplus():
    r = A.assess_site(SITE, elements=DENSE, attendance=120_000_000)
    o = r["overflow"]
    assert o["absorbed"] + o["residual"] == o["surplus"]


def test_small_attendance_clears_without_a_breach():
    r = A.assess_site(SITE, elements=EXTRACT, attendance=10_000)
    assert r["breach"]["surplus"] == 0
    assert r["flags"]["throughput_shortfall"] is False


def test_assess_site_identifies_the_narrowest_link():
    r = A.assess_site(SITE, elements=EXTRACT, attendance=120_000_000)
    assert r["narrowest"]["name"] == "Temple Lane"   # 3.5 m tagged, below the 4 m service default
    assert r["flags"]["chokepoint"] is True


def test_sanitation_gaps_are_computed():
    r = A.assess_site(SITE, elements=EXTRACT, attendance=120_000_000)
    assert r["toilet_gap"]["required"] > r["toilet_gap"]["mapped"]
    assert r["water_gap"]["required"] > r["water_gap"]["mapped"]
    assert r["flags"]["toilet_gap"] is True


def test_queue_at_mapped_units_is_unstable_but_the_norm_is_not():
    r = A.assess_site(SITE, elements=EXTRACT, attendance=120_000_000)
    assert r["toilet_queue_as_mapped"]["stable"] is False
    assert r["toilet_queue_at_norm"]["stable"] is True


def test_assess_site_survives_an_empty_extract():
    r = A.assess_site(SITE, elements=[], attendance=120_000_000)
    assert r["narrowest"] is None
    assert r["evidence_completeness"] < 1.0
    assert isinstance(r["score"], float)


def test_save_results_round_trips(tmp_path):
    import json

    recs = [A.assess_site(SITE, elements=EXTRACT, attendance=120_000_000)]
    paths = A.save_results(recs, outputs_dir=str(tmp_path))
    data = json.loads(Path(paths["json"]).read_text())
    assert data[0]["name"] == "Test Ghat"
    assert Path(paths["csv"]).exists()
