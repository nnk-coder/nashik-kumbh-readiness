"""Geometry over OpenStreetMap elements. No network.

Coordinates are projected onto a local tangent plane in metres, which is
accurate to well under a metre over the 1.5 km around a site — far finer than
the uncertainty in the OSM data itself, and it avoids a projection dependency.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from . import config as C

EARTH_R = 6_378_137.0


# --- projection ------------------------------------------------------------


def to_xy(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Metres east and north of the origin, on a local tangent plane."""
    x = math.radians(lon - lon0) * EARTH_R * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * EARTH_R
    return (x, y)


def ring_to_xy(coords: Sequence[tuple[float, float]], lat0: float, lon0: float):
    return [to_xy(la, lo, lat0, lon0) for la, lo in coords]


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


# --- OSM elements → polygons ----------------------------------------------


def _way_coords(el: dict, nodes: dict) -> list[tuple[float, float]]:
    out = []
    for nid in el.get("nodes", []):
        n = nodes.get(nid)
        if n:
            out.append((n["lat"], n["lon"]))
    if el.get("geometry"):
        out = [(g["lat"], g["lon"]) for g in el["geometry"]]
    return out


def _polygon(coords, lat0, lon0) -> Polygon | None:
    if len(coords) < 4:
        return None
    try:
        poly = Polygon(ring_to_xy(coords, lat0, lon0))
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly if (poly.is_valid and poly.area > 0) else None
    except Exception:  # noqa: BLE001
        return None


def index_nodes(elements: Iterable[dict]) -> dict:
    return {e["id"]: e for e in elements if e.get("type") == "node"}


def polygons_matching(
    elements: Sequence[dict], predicate, lat0: float, lon0: float
) -> list[Polygon]:
    """Every closed way satisfying `predicate(tags)`, as local-metre polygons."""
    nodes = index_nodes(elements)
    out = []
    for el in elements:
        if el.get("type") not in ("way", "relation"):
            continue
        tags = el.get("tags") or {}
        if not predicate(tags):
            continue
        poly = _polygon(_way_coords(el, nodes), lat0, lon0)
        if poly is not None:
            out.append(poly)
    return out


def is_building(tags: dict) -> bool:
    return "building" in tags or tags.get("building:part") == "yes"


def is_water(tags: dict) -> bool:
    return (
        tags.get("natural") == "water"
        or tags.get("waterway") in ("riverbank", "river")
        or tags.get("landuse") == "reservoir"
    )


def is_open_space(tags: dict) -> bool:
    for key in ("leisure", "landuse", "amenity"):
        if tags.get(key) in C.OVERFLOW_LANDUSE:
            return True
    return False


# --- the measurements ------------------------------------------------------


def assembly_area_m2(
    elements: Sequence[dict], lat0: float, lon0: float, radius_m: float
) -> dict:
    """Open ground within `radius_m` of the site: the circle, less buildings
    and open water.

    This is the honest version of "how big is the ghat". It counts every
    square metre a person could physically stand on, including carriageway,
    so it is an upper bound: the usable figure is smaller once vehicle routes,
    barriers and akhara enclosures are taken out.
    """
    circle = Point(0.0, 0.0).buffer(radius_m, quad_segs=64)
    buildings = polygons_matching(elements, is_building, lat0, lon0)
    water = polygons_matching(elements, is_water, lat0, lon0)

    built = unary_union(buildings).intersection(circle) if buildings else None
    wet = unary_union(water).intersection(circle) if water else None

    open_area = circle
    if built is not None and not built.is_empty:
        open_area = open_area.difference(built)
    if wet is not None and not wet.is_empty:
        open_area = open_area.difference(wet)

    return {
        "circle_m2": round(circle.area),
        "building_m2": round(built.area) if built is not None else 0,
        "water_m2": round(wet.area) if wet is not None else 0,
        "open_m2": round(open_area.area),
        "building_count": len(buildings),
    }


def approach_links(
    elements: Sequence[dict], lat0: float, lon0: float, radius_m: float
) -> list[dict]:
    """Roads and lanes crossing into the site, with a width for each.

    OSM carries an explicit `width` on very few Indian streets, so where it is
    absent the width is inferred from the highway class. That inference is the
    weakest number in this whole model and the one to verify on the ground
    first; every link says which of the two it used.
    """
    nodes = index_nodes(elements)
    out = []
    for el in elements:
        if el.get("type") != "way":
            continue
        tags = el.get("tags") or {}
        hw = tags.get("highway")
        if not hw or hw in ("proposed", "construction"):
            continue
        coords = _way_coords(el, nodes)
        if len(coords) < 2:
            continue
        xy = ring_to_xy(coords, lat0, lon0)
        # Distance to the line itself, not to its vertices: a straight road
        # through the site may have no vertex anywhere near the centre.
        try:
            near = LineString(xy).distance(Point(0.0, 0.0))
        except Exception:  # noqa: BLE001
            continue
        far = max(math.hypot(x, y) for x, y in xy)
        # keep ways that touch the site and reach beyond it: these carry crowd in
        if near > radius_m or far < radius_m * 0.5:
            continue

        width, source = None, None
        for key in ("width", "est_width"):
            if tags.get(key):
                try:
                    width, source = float(str(tags[key]).split()[0]), "tagged"
                    break
                except (TypeError, ValueError):
                    pass
        if width is None:
            width = C.WIDTH_BY_HIGHWAY.get(hw)
            source = "inferred from highway class" if width else None
        if width is None:
            continue

        out.append(
            {
                "name": tags.get("name") or f"unnamed {hw}",
                "highway": hw,
                "width_m": width,
                "width_source": source,
                "oneway": tags.get("oneway") == "yes",
            }
        )
    # de-duplicate by name, keeping the narrowest segment of each street
    best: dict[str, dict] = {}
    for link in out:
        k = link["name"]
        if k not in best or link["width_m"] < best[k]["width_m"]:
            best[k] = link
    return sorted(best.values(), key=lambda l: l["width_m"])


def amenity_points(elements: Sequence[dict], value: str) -> list[dict]:
    """Mapped facilities of one kind, from nodes and from polygon centroids."""
    out = []
    for el in elements:
        tags = el.get("tags") or {}
        if tags.get("amenity") != value:
            continue
        if el.get("type") == "node":
            out.append({"lat": el["lat"], "lon": el["lon"], "name": tags.get("name")})
        elif el.get("center"):
            out.append(
                {"lat": el["center"]["lat"], "lon": el["center"]["lon"], "name": tags.get("name")}
            )
    return out


def open_spaces(
    elements: Sequence[dict], lat0: float, lon0: float, min_area_m2: float = 500.0
) -> list[dict]:
    """Candidate overflow holding areas, with area and distance from the site."""
    nodes = index_nodes(elements)
    out = []
    for el in elements:
        if el.get("type") not in ("way", "relation"):
            continue
        tags = el.get("tags") or {}
        if not is_open_space(tags) or is_building(tags):
            continue
        poly = _polygon(_way_coords(el, nodes), lat0, lon0)
        if poly is None or poly.area < min_area_m2:
            continue
        cx, cy = poly.centroid.x, poly.centroid.y
        out.append(
            {
                "name": tags.get("name") or f"unnamed {tags.get('leisure') or tags.get('landuse') or tags.get('amenity')}",
                "area_m2": round(poly.area),
                "distance_m": round(math.hypot(cx, cy)),
                "kind": tags.get("leisure") or tags.get("landuse") or tags.get("amenity"),
            }
        )
    return sorted(out, key=lambda s: s["distance_m"])


def count_within(points: Sequence[dict], lat0: float, lon0: float, radius_m: float) -> int:
    return sum(
        1 for p in points if haversine_m(p["lat"], p["lon"], lat0, lon0) <= radius_m
    )


def cluster_points(
    points: Sequence[dict],
    lat0: float,
    lon0: float,
    link_distance_m: float = C.FACILITY_CLUSTER_DISTANCE_M,
) -> list[dict]:
    """Group facilities that sit close enough to fail together.

    Single-link clustering: two facilities join the same cluster when they are
    within `link_distance_m` of each other. Blocks that close together usually
    share a water tanker, a desludging route and a power feed, so this is the
    unit that goes out of service, not the individual cubicle.
    """
    pts = [
        (to_xy(p["lat"], p["lon"], lat0, lon0), p)
        for p in points
        if p.get("lat") is not None and p.get("lon") is not None
    ]
    if not pts:
        return []

    parent = list(range(len(pts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            (xi, yi), _ = pts[i]
            (xj, yj), _ = pts[j]
            if math.hypot(xi - xj, yi - yj) <= link_distance_m:
                union(i, j)

    groups: dict[int, list] = {}
    for i, (xy, p) in enumerate(pts):
        groups.setdefault(find(i), []).append((xy, p))

    out = []
    for members in groups.values():
        xs = [m[0][0] for m in members]
        ys = [m[0][1] for m in members]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        out.append(
            {
                "count": len(members),
                "distance_m": round(math.hypot(cx, cy)),
                "name": next((m[1].get("name") for m in members if m[1].get("name")), None),
            }
        )
    return sorted(out, key=lambda c: -c["count"])
