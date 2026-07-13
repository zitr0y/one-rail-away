"""Geographic country assignment for canonical stations.

merge_stations labels every station with its FEED's country (a db_fern station
is "DE"), which is wrong for foreign stops that leak in via cross-border trips
(2026-07 build evidence: Praha hl.n. tagged DE, Venezia Santa Lucia tagged AT,
Barcelone-Sants tagged FR). Fix by point-in-polygon against a bundled Natural
Earth 50m admin_0 subset.

Asset provenance: pipeline/assets/countries_europe_50m.geojson is derived from
https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson
(public domain), filtered to European ISO_A2_EH codes, properties reduced to
ISO_A2_EH, coordinates rounded to 3 decimals (~110 m — well inside the 50m
dataset's own accuracy).

50m boundaries are only ~1 km accurate: a station closer than that to a border
belongs in pipeline/station_countries.toml with an evidence comment; overrides
win over the polygon lookup. A station matching no polygon (offshore artifact
of the simplified coastline) keeps its feed country, logged for review.
"""

import json
import logging
import math
from pathlib import Path

from pipeline.models import CountryOverride, Station

logger = logging.getLogger(__name__)

Ring = list[tuple[float, float]]

ASSET = Path(__file__).parent / "assets" / "countries_europe_50m.geojson"

OVERRIDE_RADIUS_M = 500


def load_countries(path: Path) -> list[tuple[str, list[list[Ring]]]]:
    """[(iso2, polygons)]; polygon = [exterior_ring, *hole_rings]; ring = [(lon, lat)].

    Natural Earth quirk: ISO_A2 is "-99" for France and Norway; ISO_A2_EH carries
    the real code, so prefer it and skip features with no usable code.
    """
    fc = json.loads(path.read_text(encoding="utf-8"))
    out: list[tuple[str, list[list[Ring]]]] = []
    for f in fc["features"]:
        props = f["properties"]
        iso = props.get("ISO_A2_EH") or props.get("ISO_A2")
        if not iso or iso == "-99":
            continue
        geom = f["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        out.append((iso, [[[(x, y) for x, y in ring] for ring in poly] for poly in polys]))
    return out


def _in_ring(lon: float, lat: float, ring: Ring) -> bool:
    """Ray-cast point-in-ring test (even-odd rule)."""
    inside = False
    for k in range(len(ring)):
        x1, y1 = ring[k - 1]
        x2, y2 = ring[k]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def country_at(lat: float, lon: float, countries: list[tuple[str, list[list[Ring]]]]) -> str | None:
    for iso, polys in countries:
        for rings in polys:
            if _in_ring(lon, lat, rings[0]) and not any(_in_ring(lon, lat, h) for h in rings[1:]):
                return iso
    return None


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two latitude/longitude points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * 6_371_000 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def assign_countries(
    stations: list[Station],
    countries: list[tuple[str, list[list[Ring]]]],
    overrides: list[CountryOverride],
) -> list[str]:
    """Set station countries from coordinate overrides, then geography.

    Overrides match the nearest station within OVERRIDE_RADIUS_M and always emit
    an audit line. Non-overridden stations retain the existing polygon behavior.
    Returned lines are printed by the build stage, including unused/ambiguous warnings.
    """
    changes: list[str] = []
    overridden_ids: set[str] = set()

    for override in overrides:
        distances = sorted(
            (
                (_haversine_m(override.lat, override.lon, station.lat, station.lon), station)
                for station in stations
            ),
            key=lambda item: item[0],
        )
        within_radius = [item for item in distances if item[0] <= OVERRIDE_RADIUS_M]
        if not within_radius:
            changes.append(
                f"unused override {override.name!r} ({override.lat:.6f}, {override.lon:.6f}): "
                f"no station within {OVERRIDE_RADIUS_M}m"
            )
            continue

        _, nearest = within_radius[0]
        if len(within_radius) > 1:
            candidates = ", ".join(
                f"{station.id} ({station.name})" for _, station in within_radius
            )
            changes.append(
                f"ambiguous override {override.name!r} "
                f"({override.lat:.6f}, {override.lon:.6f}): "
                f"{len(within_radius)} stations within {OVERRIDE_RADIUS_M}m "
                f"({candidates}); using {nearest.id} ({nearest.name})"
            )

        old = nearest.country
        nearest.country = override.country
        overridden_ids.add(nearest.id)
        changes.append(f"{nearest.id} ({nearest.name}): {old} -> {override.country}")

    for station in stations:
        if station.id in overridden_ids:
            continue
        new = country_at(station.lat, station.lon, countries)
        if new is None:
            changes.append(
                f"{station.id} ({station.name}): no polygon match, "
                f"keeping feed country {station.country}"
            )
        elif new != station.country:
            changes.append(f"{station.id} ({station.name}): {station.country} -> {new}")
            station.country = new
    return changes
