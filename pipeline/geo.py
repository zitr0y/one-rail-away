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
from pathlib import Path

from pipeline.models import Station

logger = logging.getLogger(__name__)

Ring = list[tuple[float, float]]

ASSET = Path(__file__).parent / "assets" / "countries_europe_50m.geojson"


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


def assign_countries(
    stations: list[Station],
    countries: list[tuple[str, list[list[Ring]]]],
    overrides: dict[str, str],
) -> list[str]:
    """Set each station's country from geography (override table wins); return
    human-readable change-log lines for the build output."""
    changes: list[str] = []
    for s in stations:
        new = overrides.get(s.id) or country_at(s.lat, s.lon, countries)
        if new is None:
            changes.append(f"{s.id} ({s.name}): no polygon match, keeping feed country {s.country}")
        elif new != s.country:
            changes.append(f"{s.id} ({s.name}): {s.country} -> {new}")
            s.country = new
    return changes
