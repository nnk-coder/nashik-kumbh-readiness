"""Single-point-of-failure tests. No network."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config as C  # noqa: E402
from src import geo as G  # noqa: E402
from src import resilience as R  # noqa: E402
from src import sanitation as SAN  # noqa: E402


# --- concentration ---------------------------------------------------------


def test_concentration_is_one_when_a_single_item_carries_everything():
    assert R.concentration([10]) == 1.0
    assert R.concentration([10, 0, 0]) == 1.0


def test_concentration_falls_with_redundancy():
    assert R.concentration([5, 5]) == 0.5
    assert R.concentration([1, 1, 1, 1]) == 0.25


def test_concentration_none_without_values():
    assert R.concentration([]) is None
    assert R.concentration([None, float("nan")]) is None


# --- routes ----------------------------------------------------------------


LINKS = [
    {"name": "Main Road", "width_m": 10.0},
    {"name": "Temple Lane", "width_m": 3.5},
    {"name": "Back Alley", "width_m": 4.0},
]


def test_route_shares_sum_to_one_and_sort_descending():
    rows = R.route_criticality(LINKS, 100_000)
    assert math.isclose(sum(r["share_of_exit_capacity"] for r in rows), 1.0, abs_tol=0.01)
    assert rows == sorted(rows, key=lambda r: -r["share_of_exit_capacity"])
    assert rows[0]["name"] == "Main Road"


def test_closing_a_route_always_lengthens_egress():
    for r in R.route_criticality(LINKS, 100_000):
        assert r["egress_delta_min"] > 0


def test_a_sole_route_strands_the_site():
    rows = R.route_criticality([{"name": "Only Way", "width_m": 6.0}], 50_000)
    assert rows[0]["strands_site"] is True
    assert rows[0]["egress_without_min"] is None


def test_route_criticality_empty_without_population_or_links():
    assert R.route_criticality(LINKS, None) == []
    assert R.route_criticality([], 1000) == []


# --- overflow holding areas ------------------------------------------------


SPACES = [
    {"name": "Big Maidan", "area_m2": 50_000, "distance_m": 300, "kind": "park"},
    {"name": "Small Park", "area_m2": 4_000, "distance_m": 500, "kind": "park"},
]


def test_losing_the_largest_holding_area_strands_the_most():
    rows = R.overflow_criticality(200_000, SPACES)
    assert rows[0]["name"] == "Big Maidan"
    assert rows[0]["extra_stranded"] > 0


def test_a_space_that_was_never_used_is_not_reported():
    """With a tiny surplus the nearest space absorbs it all; the rest are
    irrelevant and should not appear as critical."""
    rows = R.overflow_criticality(1_000, SPACES)
    assert all(r["name"] != "Small Park" for r in rows)


def test_overflow_criticality_empty_without_surplus():
    assert R.overflow_criticality(0, SPACES) == []
    assert R.overflow_criticality(None, SPACES) == []


def test_shares_of_surplus_never_exceed_one():
    for r in R.overflow_criticality(200_000, SPACES):
        assert 0 < r["share_of_surplus"] <= 1.0


# --- facilities ------------------------------------------------------------


def test_facility_criticality_reports_concentration():
    out = R.facility_criticality([40, 10, 10], 5_000, 3.0)
    assert out["clusters"] == 3
    assert out["units_total"] == 60
    assert out["largest_cluster"] == 40
    assert out["concentration"] == round(40 / 60, 3)


def test_losing_the_largest_cluster_can_tip_a_working_queue_into_failure():
    """Sized just above demand, losing the biggest block breaks it. This is
    how a sanitation outage becomes a crowd problem."""
    users = 10_000
    need = SAN.units_for_target_wait(users, 3.0)
    out = R.facility_criticality([need // 2, need // 2 + need % 2], users, 3.0)
    assert out["stable_before"] is True
    assert out["tips_into_failure"] is True


def test_a_well_distributed_estate_does_not_tip():
    users = 5_000
    need = SAN.units_for_target_wait(users, 3.0) * 3
    sizes = [need // 10] * 10
    out = R.facility_criticality(sizes, users, 3.0)
    assert out["stable_before"] is True
    assert out["tips_into_failure"] is False


def test_facility_criticality_none_without_units_or_demand():
    assert R.facility_criticality([], 1000, 3.0) is None
    assert R.facility_criticality([10], None, 3.0) is None


# --- the summary -----------------------------------------------------------


def test_summary_flags_a_dominant_route():
    routes = R.route_criticality(
        [{"name": "Only Big Road", "width_m": 20.0}, {"name": "Lane", "width_m": 2.5}],
        100_000,
    )
    out = R.single_point_summary(routes, [], None, None)
    assert out["flagged"] is True
    assert any("exit capacity" in r for r in out["reasons"])


def test_summary_flags_a_dominant_holding_area():
    spaces = R.overflow_criticality(200_000, SPACES)
    out = R.single_point_summary([], spaces, None, None)
    assert out["flagged"] is True
    assert any("overflow" in r for r in out["reasons"])


def test_summary_flags_a_toilet_estate_in_one_cluster():
    crit = R.facility_criticality([60], 5_000, 3.0)
    out = R.single_point_summary([], [], crit, None)
    assert out["flagged"] is True


def test_summary_clean_when_everything_is_redundant():
    routes = R.route_criticality(
        [{"name": f"Road {i}", "width_m": 8.0} for i in range(5)], 10_000
    )
    users = 5_000
    need = SAN.units_for_target_wait(users, 3.0) * 3
    crit = R.facility_criticality([need // 10] * 10, users, 3.0)
    out = R.single_point_summary(routes, [], crit, None)
    assert out["flagged"] is False
    assert out["reasons"] == []


def test_summary_reports_the_worst_route_first():
    routes = R.route_criticality(LINKS, 100_000)
    out = R.single_point_summary(routes, [], None, None)
    assert out["worst_route"]["name"] == "Main Road"


# --- clustering ------------------------------------------------------------


LAT0, LON0 = 20.0, 73.8


def _pt(x_m, y_m, name=None):
    dlat = y_m / (math.radians(1) * 6_378_137.0)
    dlon = x_m / (111_320.0 * math.cos(math.radians(LAT0)))
    return {"lat": LAT0 + dlat, "lon": LON0 + dlon, "name": name}


def test_nearby_points_form_one_cluster():
    pts = [_pt(0, 0), _pt(30, 0), _pt(60, 0)]
    clusters = G.cluster_points(pts, LAT0, LON0, link_distance_m=120)
    assert len(clusters) == 1 and clusters[0]["count"] == 3


def test_distant_points_form_separate_clusters():
    pts = [_pt(0, 0), _pt(30, 0), _pt(900, 0)]
    clusters = G.cluster_points(pts, LAT0, LON0, link_distance_m=120)
    assert len(clusters) == 2
    assert clusters[0]["count"] == 2  # sorted largest first


def test_clusters_chain_through_intermediate_points():
    """Single-link: A-B-C chain into one cluster even though A and C are far."""
    pts = [_pt(0, 0), _pt(100, 0), _pt(200, 0)]
    clusters = G.cluster_points(pts, LAT0, LON0, link_distance_m=120)
    assert len(clusters) == 1 and clusters[0]["count"] == 3


def test_cluster_points_empty_input():
    assert G.cluster_points([], LAT0, LON0) == []


def test_cluster_carries_a_name_when_one_is_mapped():
    clusters = G.cluster_points([_pt(0, 0), _pt(20, 0, "Ghat Toilet Block")], LAT0, LON0)
    assert clusters[0]["name"] == "Ghat Toilet Block"


# --- weights ---------------------------------------------------------------


def test_weights_still_sum_to_one_hundred_after_rebalancing():
    assert math.isclose(sum(C.READINESS_WEIGHTS.values()), 100.0)


def test_single_point_failure_is_weighted():
    assert C.READINESS_WEIGHTS["single_point_failure"] > 0
