"""`coverage.json` emission: dissolve non-covered country polygons into a single
veil MultiPolygon that covers all land except covered countries.

World asset provenance: pipeline/assets/countries_world_10m.geojson is derived
from ne_10m_admin_0_countries.geojson (Natural Earth, public domain):
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson

Built one-off with:
  npx -y mapshaper ne_10m_admin_0_countries.geojson \\
    -filter-fields ISO_A2_EH \\
    -simplify visvalingam 40% keep-shapes \\
    -o precision=0.0001 format=geojson \\
    pipeline/assets/countries_world_10m.geojson

Properties reduced to ISO_A2_EH, simplified to 40% retention (visvalingam, keep-shapes),
coordinates rounded to 4 decimals (~11 m). The existing
countries_europe_50m.geojson is untouched — geo.py station->country assignment
keeps using it.
"""

import json
from pathlib import Path

from shapely import unary_union
from shapely.geometry import shape

from pipeline.config import load_feeds

WORLD_ASSET = Path(__file__).parent / "assets" / "countries_world_10m.geojson"


def build_coverage(covered: set[str], asset_path: Path = WORLD_ASSET) -> dict:
    """GeoJSON FeatureCollection with one Feature: a dissolved MultiPolygon of
    every country NOT in `covered`. Ocean is never veiled. Returns a single-
    feature FeatureCollection with empty properties."""
    fc = json.loads(asset_path.read_text(encoding="utf-8"))
    non_covered_geoms = []
    for f in fc["features"]:
        iso = f["properties"].get("ISO_A2_EH")
        if not iso or iso == "-99" or iso in covered:
            continue
        non_covered_geoms.append(shape(f["geometry"]))
    if not non_covered_geoms:
        return {"type": "FeatureCollection", "features": []}
    dissolved = unary_union(non_covered_geoms)
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(json.dumps(dissolved.__geo_interface__)),
                "properties": {},
            }
        ],
    }


def covered_from_feeds(feeds_path: Path) -> set[str]:
    """The set of `country` fields declared across all feeds in a feeds.toml."""
    return {cfg.country for cfg in load_feeds(feeds_path).values()}
