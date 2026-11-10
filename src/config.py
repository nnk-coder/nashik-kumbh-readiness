"""Every number a reviewer might argue with, in one file.

Sources are named inline so each threshold can be challenged on its merits
rather than taken on trust. Nothing here is an official figure of the
Nashik-Trimbakeshwar Kumbh Mela Authority.
"""

from __future__ import annotations

# --- The event -------------------------------------------------------------

EVENT_NAME = "Nashik-Trimbakeshwar Simhastha"
EVENT_START = "2026-10-31"
EVENT_END = "2028-07-24"

# Amrit Snan ("royal bath") days carry the crush risk. Source: Maharashtra
# government schedule announced 1 June 2025.
AMRIT_SNAN = [
    ("2027-08-02", "First Amrit Snan", "nashik"),
    ("2027-08-31", "Second Amrit Snan", "nashik"),
    ("2027-09-11", "Third Amrit Snan", "nashik"),
    ("2027-09-12", "Third Amrit Snan", "trimbakeshwar"),
]

# Attendance. 2015 drew about 2.5 crore. The Chief Minister's Office expects
# four to five times that; the state has publicly used ~12 crore.
ATTENDANCE_2015 = 25_000_000
ATTENDANCE_EXPECTED = 120_000_000

# Share of total attendance arriving on the single busiest day. Prayagraj 2025
# saw roughly 100 million of 400 million expected on Mauni Amavasya, about
# 25%. Nashik spreads over more Snan days, so 15% is the working assumption.
PEAK_DAY_SHARE = 0.15

# Share of a peak day's bathers in the busiest hour. Bathing concentrates in
# the pre-dawn Brahma Muhurta window.
PEAK_HOUR_SHARE = 0.20

# --- Crowd density ---------------------------------------------------------

# Fruin level of service for standing and queuing areas, in persons per m2.
# Standard planning bands, widely reproduced in crowd-safety practice.
FRUIN_BANDS = (
    (0.00, 0.83, "A", "free circulation"),
    (0.83, 1.11, "B", "restricted circulation"),
    (1.11, 1.43, "C", "movement restricted to the crowd's pace"),
    (1.43, 3.33, "D", "touching unavoidable, movement severely restricted"),
    (3.33, 5.00, "E", "shuffling only, no counter-flow possible"),
    (5.00, 99.0, "F", "involuntary contact, progressive crowd collapse risk"),
)

# Flow peaks then falls as density rises. G. Keith Still places the critical
# value at about 2-3 persons/m2; above it, adding people reduces throughput.
DENSITY_CRITICAL = 2.5

# Planning ceiling for a managed, stewarded standing crowd.
DENSITY_PLANNING = 4.0

# Above this, crowd-collapse incidents become likely. This is the number the
# 2003 Ramkund and 2025 Prayagraj failures sit above.
DENSITY_DANGER = 5.0

# --- Pedestrian flow -------------------------------------------------------

# Maximum sustainable specific flow through a constriction, persons per metre
# of effective width per minute. 82 is the conventional ceiling; planning uses
# a margin below it.
SPECIFIC_FLOW_MAX = 82.0
SPECIFIC_FLOW_PLANNING = 60.0

# Crowds do not use the full width of a route: a boundary layer is lost at
# each edge to walls, railings, stalls and street furniture.
BOUNDARY_LAYER_M = 0.20

# Minutes a bather occupies the ghat, arrival to departure. Drives throughput,
# which matters more than instantaneous capacity.
GHAT_DWELL_MINUTES = 20.0

# --- Sanitation: CPHEEO norms ---------------------------------------------

# Central Public Health and Environmental Engineering Organisation, Advisory
# on Public and Community Toilets. Public toilet norms (Table 2.3, from
# CPHEEO 2013), assuming two-thirds male and one-third female users.
MALE_SHARE = 0.60  # mass bathing skews less male than CPHEEO's two-thirds

# Men: one WC per 100 up to 400 persons; above that one per 250 or part.
PT_MEN_WC_FIRST_BLOCK = 400
PT_MEN_WC_PER_FIRST = 100
PT_MEN_WC_PER_ABOVE = 250

# Women: two WCs per 100 up to 200 persons; above that one per 100 or part.
PT_WOMEN_WC_FIRST_BLOCK = 200
PT_WOMEN_WC_PER_FIRST = 100
PT_WOMEN_WC_PER_ABOVE = 100

# Men's urinals: one per 50 persons or part thereof.
PT_MEN_URINAL_PER = 50

# Community toilet norms (Table 2.4, SBM-Urban 2014) — the closer analogue for
# a temporary settlement.
CT_SEATS_PER_MAN = 35
CT_SEATS_PER_WOMAN = 25
CT_URINAL_PER = 250

# One water tap with drainage for every 50 persons or part thereof.
WATER_TAP_PER = 50

# Walking distance: community toilets within 500 m of the settlement they
# serve, public toilets within 1 km.
CT_WALK_DISTANCE_M = 500.0
PT_WALK_DISTANCE_M = 1_000.0

# Toilets are designed for peak-hour demand against a 5-10 minute wait.
TARGET_QUEUE_WAIT_MIN = 10.0

# People queue at the block in front of them, not at a city-wide pool. Pooling
# every unit on the site into one queue is the single most flattering
# assumption this model could make, so demand is split across blocks of this
# size and the wait is computed per block.
TOILET_BLOCK_UNITS = 20
WATER_BLOCK_UNITS = 10

# --- Sanitation: demand behaviour -----------------------------------------

# Share of people present in the peak hour who use a toilet in that hour.
TOILET_USE_RATE_PEAK_HOUR = 0.25

# Minutes of occupancy per use, including entry and exit.
TOILET_SERVICE_MINUTES = 3.0

# Share of people present who draw drinking water in the peak hour, and how
# long a tap is occupied per use.
WATER_USE_RATE_PEAK_HOUR = 0.40
WATER_SERVICE_MINUTES = 1.0

# --- Prayagraj 2025 benchmark ---------------------------------------------

# Published preparation figures, used only to sanity-check orders of
# magnitude. Not a target.
PRAYAGRAJ_2025 = {
    "pilgrims_expected": 400_000_000,
    "toilets": 150_000,
    "tents": 160_000,
    "water_pipeline_km": 1_250,
    "sanitation_workers": 15_000,
    "area_hectares": 4_000,
    "duration_days": 45,
}

# --- Sites -----------------------------------------------------------------

# Coordinates are approximate centroids for a first pass and are resolved
# against OpenStreetMap at run time. Weight is the share of peak-hour arrivals
# assumed to present at each site; it is a planning assumption, not an
# observation, and it sums to 1.0.
SITES = [
    {
        "id": "ramkund",
        "name": "Ramkund",
        "city": "Nashik",
        "lat": 19.9977,
        "lon": 73.7905,
        "osm_query": "Ramkund",
        "weight": 0.40,
        "note": "Site of the 2003 stampede: 39 died when about 30,000 were held on a narrow approach street.",
    },
    {
        "id": "kushavarta",
        "name": "Kushavarta Kund",
        "city": "Trimbakeshwar",
        "lat": 19.9320,
        "lon": 73.5310,
        "osm_query": "Kushavarta",
        "weight": 0.20,
        "note": "The Trimbakeshwar bathing kund; the smallest footprint of the four and the hardest to widen.",
    },
    {
        "id": "tapovan",
        "name": "Tapovan / Sadhugram",
        "city": "Nashik",
        "lat": 20.0150,
        "lon": 73.8120,
        "osm_query": "Tapovan",
        "weight": 0.25,
        "note": "Akhara camping ground and secondary bathing area; the main temporary settlement.",
    },
    {
        "id": "someshwar",
        "name": "Someshwar",
        "city": "Nashik",
        "lat": 20.0094,
        "lon": 73.7472,
        "osm_query": "Someshwar",
        "weight": 0.15,
        "note": "Upstream Godavari ghat used to relieve Ramkund.",
    },
]

# --- Overflow --------------------------------------------------------------

# How far a diverted crowd can reasonably be walked to a holding area.
OVERFLOW_WALK_RADIUS_M = 1_200.0

# Density used when sizing a holding area, below the planning ceiling because
# a holding crowd waits longer and is less tolerant of compression.
OVERFLOW_HOLDING_DENSITY = 2.0

# OpenStreetMap tags treated as usable open space for overflow holding.
OVERFLOW_LANDUSE = (
    "park", "recreation_ground", "pitch", "common", "village_green",
    "grass", "sports_centre", "stadium", "school", "college", "parking",
)

# --- OpenStreetMap ---------------------------------------------------------

# Carriageway width in metres by highway class, used only where OSM carries no
# `width` tag. Indian street data almost never does, so most links fall back to
# these. They are the weakest numbers in the model and the first thing a site
# visit should replace.
WIDTH_BY_HIGHWAY = {
    "motorway": 14.0, "trunk": 12.0, "primary": 10.0, "secondary": 8.5,
    "tertiary": 7.0, "unclassified": 5.0, "residential": 5.5,
    "living_street": 4.0, "service": 4.0, "pedestrian": 6.0,
    "footway": 2.5, "path": 2.0, "steps": 2.0, "track": 3.0,
    "primary_link": 7.0, "secondary_link": 6.0, "tertiary_link": 5.0,
}

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OSM_RADIUS_M = 1_500  # how far around a site we pull OSM data

# The bathing precinct itself. Crowd capacity is measured inside this, not
# across the whole query radius: a ghat is a precinct of a couple of hundred
# metres, and sizing it at 1.5 km would make any site look like it had room.
ASSEMBLY_RADIUS_M = 250
OVERPASS_TIMEOUT_S = 180

# --- Scoring ---------------------------------------------------------------

# Weights sum to 100. Higher means more to resolve before the Snan.
READINESS_WEIGHTS = {
    "throughput_shortfall": 35.0,
    "egress_time": 20.0,
    "chokepoint": 15.0,
    "toilet_gap": 15.0,
    "water_gap": 15.0,
}

TRAFFIC_LIGHT_BANDS = ((0.0, 25.0, "green"), (25.0, 55.0, "amber"), (55.0, 100.1, "red"))

# Thresholds at which each check is raised.
EGRESS_TIME_FLAG_MIN = 60.0       # minutes to clear the site
CHOKEPOINT_MIN_WIDTH_M = 6.0      # narrowest link on a main approach
THROUGHPUT_SHORTFALL_FLAG = 0.0   # any shortfall against peak-hour arrivals
TOILET_GAP_FLAG = 0.20            # share of required units missing
WATER_GAP_FLAG = 0.20
