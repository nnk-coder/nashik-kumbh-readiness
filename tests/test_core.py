"""Unit tests for the pure analysis layer.

    python -m pytest -q

No network, no OpenStreetMap, no credentials.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config as C  # noqa: E402
from src import capacity as CAP  # noqa: E402
from src import sanitation as SAN  # noqa: E402


# --- density ---------------------------------------------------------------


def test_fruin_bands_are_contiguous_and_cover_zero_upward():
    lo_prev = None
    for lo, hi, _letter, _meaning in C.FRUIN_BANDS:
        if lo_prev is not None:
            assert math.isclose(lo, lo_prev)
        lo_prev = hi
    assert C.FRUIN_BANDS[0][0] == 0.0


def test_fruin_band_letters():
    assert CAP.fruin_band(0.5)[0] == "A"
    assert CAP.fruin_band(2.0)[0] == "D"
    assert CAP.fruin_band(4.0)[0] == "E"
    assert CAP.fruin_band(7.0)[0] == "F"


def test_fruin_band_handles_missing():
    assert CAP.fruin_band(None) is None
    assert CAP.fruin_band(float("nan")) is None


def test_danger_density_sits_above_planning_which_sits_above_critical():
    assert C.DENSITY_CRITICAL < C.DENSITY_PLANNING < C.DENSITY_DANGER


def test_holding_capacity_scales_with_area():
    assert CAP.holding_capacity(1000, 4.0) == 4000
    assert CAP.holding_capacity(0) is None
    assert CAP.holding_capacity(None) is None


def test_density_at_is_the_inverse_of_capacity():
    assert CAP.density_at(1000, 4000) == 4.0


# --- flow ------------------------------------------------------------------


def test_effective_width_removes_a_boundary_layer_each_side():
    assert CAP.effective_width(4.0) == round(4.0 - 2 * C.BOUNDARY_LAYER_M, 2)


def test_effective_width_never_negative():
    assert CAP.effective_width(0.1) == 0.0


def test_flow_capacity_scales_with_effective_width():
    narrow = CAP.flow_capacity_per_min(3.0)
    wide = CAP.flow_capacity_per_min(9.0)
    assert wide > narrow > 0


def test_flow_capacity_none_for_a_width_all_boundary_layer():
    assert CAP.flow_capacity_per_min(0.2) is None


def test_egress_time_grows_with_population_and_falls_with_width():
    a = CAP.egress_time_min(100_000, 10.0)
    b = CAP.egress_time_min(200_000, 10.0)
    c = CAP.egress_time_min(100_000, 20.0)
    assert b > a > c


def test_egress_time_zero_for_empty_site():
    assert CAP.egress_time_min(0, 10.0) == 0.0


def test_egress_time_unknown_when_no_exit_width():
    assert CAP.egress_time_min(1000, None) is None


# --- throughput ------------------------------------------------------------


def test_throughput_is_capacity_times_turnover():
    # 1000 m2 at 4/m2 = 4000 people, 20-minute dwell = 3 turns an hour
    assert CAP.site_throughput_per_hour(1000, 20.0, 4.0) == 12000


def test_shorter_dwell_raises_throughput():
    slow = CAP.site_throughput_per_hour(1000, 30.0)
    fast = CAP.site_throughput_per_hour(1000, 10.0)
    assert fast > slow


def test_peak_hour_arrivals_respects_weights():
    whole = CAP.peak_hour_arrivals(120_000_000, 1.0)
    part = CAP.peak_hour_arrivals(120_000_000, 0.40)
    assert math.isclose(part, whole * 0.40, rel_tol=1e-6)


def test_site_weights_sum_to_one():
    assert math.isclose(sum(s["weight"] for s in C.SITES), 1.0, rel_tol=1e-9)


# --- breach ----------------------------------------------------------------


def test_breach_reports_surplus_and_ratio():
    b = CAP.breach(demand=120_000, capacity=40_000)
    assert b.surplus == 80_000
    assert b.ratio == 3.0


def test_no_breach_when_capacity_exceeds_demand():
    b = CAP.breach(demand=1000, capacity=5000)
    assert b.surplus == 0


def test_breach_none_on_missing_input():
    assert CAP.breach(None, 100) is None
    assert CAP.breach(100, None) is None


# --- overflow --------------------------------------------------------------


def _spaces():
    return [
        {"name": "far field", "area_m2": 20_000, "distance_m": 1100},
        {"name": "near maidan", "area_m2": 10_000, "distance_m": 300},
        {"name": "mid park", "area_m2": 5_000, "distance_m": 700},
    ]


def test_overflow_fills_nearest_first():
    out = CAP.overflow_allocation(40_000, _spaces(), density=2.0)
    assert out["allocated"][0]["name"] == "near maidan"
    assert out["allocated"][1]["name"] == "mid park"


def test_overflow_absorbed_plus_residual_equals_surplus():
    out = CAP.overflow_allocation(200_000, _spaces(), density=2.0)
    assert out["absorbed"] + out["residual"] == out["surplus"]


def test_overflow_leaves_residual_when_spaces_are_too_small():
    out = CAP.overflow_allocation(500_000, _spaces(), density=2.0)
    assert out["residual"] > 0


def test_overflow_is_a_noop_without_surplus():
    out = CAP.overflow_allocation(0, _spaces())
    assert out["allocated"] == [] and out["residual"] == 0


def test_overflow_ignores_unusable_spaces():
    out = CAP.overflow_allocation(1000, [{"name": "x", "area_m2": None, "distance_m": 10}])
    assert out["residual"] == 1000


def test_hold_upstream_duration():
    assert CAP.hold_upstream_duration_min(60_000, 60_000) == 60.0
    assert CAP.hold_upstream_duration_min(0, 1000) == 0.0
    assert CAP.hold_upstream_duration_min(100, 0) is None


# --- chokepoints -----------------------------------------------------------


def test_narrowest_link_is_found_and_annotated():
    worst = CAP.narrowest_link([
        {"name": "wide road", "width_m": 12.0},
        {"name": "temple lane", "width_m": 3.5},
        {"name": "bridge", "width_m": 8.0},
    ])
    assert worst["name"] == "temple lane"
    assert worst["effective_width_m"] == 3.1
    assert worst["flow_per_min"] > 0


def test_narrowest_link_none_when_no_widths():
    assert CAP.narrowest_link([{"name": "unknown"}]) is None


# --- sanitation: required counts ------------------------------------------


def test_public_wc_men_follows_the_two_part_cpheeo_rule():
    assert SAN.public_wc_men(100) == 1
    assert SAN.public_wc_men(400) == 4
    assert SAN.public_wc_men(650) == 5      # 4 for the first 400, +1 for the next 250
    assert SAN.public_wc_men(651) == 6      # "or part thereof"


def test_public_wc_women_start_at_two_per_hundred():
    assert SAN.public_wc_women(100) == 2
    assert SAN.public_wc_women(200) == 4
    assert SAN.public_wc_women(300) == 5


def test_women_are_required_more_wcs_than_men_at_the_same_headcount():
    assert SAN.public_wc_women(5000) > SAN.public_wc_men(5000)


def test_urinals_one_per_fifty():
    assert SAN.urinals_men(50) == 1
    assert SAN.urinals_men(51) == 2


def test_community_seats_demand_far_more_than_public_toilet_norms():
    p = 100_000
    ct = SAN.community_seats(p)["total"]
    pt = SAN.toilets_required(p)["public_wc_total"]
    assert ct > pt * 5


def test_toilets_required_none_without_people():
    assert SAN.toilets_required(0) is None
    assert SAN.toilets_required(None) is None


def test_water_taps_one_per_fifty_rounding_up():
    assert SAN.water_taps_required(100) == 2
    assert SAN.water_taps_required(101) == 3
    assert SAN.water_taps_required(None) is None


# --- sanitation: queueing --------------------------------------------------


def test_erlang_c_is_a_probability():
    for load, servers in ((1.0, 5), (4.5, 5), (0.1, 2)):
        assert 0.0 <= SAN.erlang_c(load, servers) <= 1.0


def test_erlang_c_is_one_when_overloaded():
    assert SAN.erlang_c(10.0, 5) == 1.0


def test_queue_is_unstable_when_demand_exceeds_capacity():
    q = SAN.queue_state(units=10, users_per_hour=100_000, service_minutes=3.0)
    assert q.stable is False
    assert q.wait_minutes is None
    assert q.backlog_per_hour > 0


def test_queue_wait_falls_as_units_rise():
    few = SAN.queue_state(520, 10_000, 3.0)
    many = SAN.queue_state(700, 10_000, 3.0)
    assert few.stable and many.stable
    assert many.wait_minutes < few.wait_minutes


def test_pooling_every_unit_understates_the_wait():
    """The reason queue_state_blocked exists: one pooled queue over hundreds
    of units reports a wait nobody has ever experienced at a mela."""
    pooled = SAN.queue_state(600, 10_000, 3.0)
    blocked = SAN.queue_state_blocked(600, 10_000, 3.0, block_units=20)
    assert pooled.wait_minutes < blocked.wait_minutes


def test_blocked_queue_keeps_site_wide_totals():
    q = SAN.queue_state_blocked(600, 10_000, 3.0, block_units=20)
    assert q.units == 600
    assert q.demand_per_hour == 10_000


def test_blocked_queue_unstable_when_each_block_is_swamped():
    q = SAN.queue_state_blocked(100, 500_000, 3.0, block_units=20)
    assert q.stable is False
    assert q.backlog_per_hour > 0


def test_queue_handles_thousands_of_units_without_overflow():
    q = SAN.queue_state(20_000, 300_000, 3.0)
    assert q is not None and q.stable
    assert q.wait_minutes is not None and q.wait_minutes >= 0


def test_units_for_target_wait_meets_the_target():
    n = SAN.units_for_target_wait(50_000, 3.0, target_wait_min=10.0)
    assert n is not None
    q = SAN.queue_state(n, 50_000, 3.0)
    assert q.stable and q.wait_minutes <= 10.0


def test_units_for_target_wait_exceeds_bare_capacity():
    """Sizing to raw throughput leaves an unbounded queue; the target needs more."""
    bare = 50_000 / (60.0 / 3.0)
    assert SAN.units_for_target_wait(50_000, 3.0) > bare


# --- sanitation: gaps ------------------------------------------------------


def test_gap_reports_shortfall_and_share():
    g = SAN.gap(required=1000, mapped=250)
    assert g["shortfall"] == 750
    assert g["share_missing"] == 0.75


def test_gap_treats_missing_mapping_as_zero_not_as_unknown():
    g = SAN.gap(required=100, mapped=None)
    assert g["mapped"] == 0 and g["shortfall"] == 100


def test_gap_never_negative_when_oversupplied():
    g = SAN.gap(required=100, mapped=500)
    assert g["shortfall"] == 0


def test_coverage_share_capped_at_one():
    assert SAN.coverage_share(1000, 10_000) == 1.0


def test_coverage_share_partial():
    s = SAN.coverage_share(1, 10_000_000, radius_m=500)
    assert 0.0 < s < 1.0


# --- scoring ---------------------------------------------------------------


def test_readiness_weights_sum_to_one_hundred():
    assert math.isclose(sum(C.READINESS_WEIGHTS.values()), 100.0)


def test_traffic_light_bands_are_contiguous():
    lo_prev = None
    for lo, hi, _ in C.TRAFFIC_LIGHT_BANDS:
        if lo_prev is not None:
            assert math.isclose(lo, lo_prev)
        lo_prev = hi
