"""`coverage.json` emission: turn the bundled Natural Earth country subset into a
GeoJSON FeatureCollection flagged with which countries are in our system.

The bundled asset (pipeline/assets/countries_europe_50m.geojson) carries only an
ISO_A2_EH property per feature (no display name), so display names come from the
COUNTRY_NAMES table below. "Covered" means a feed in feeds.toml declares that
country; see docs/superpowers/specs/2026-07-11-country-greying-design.md.
"""

import json
from pathlib import Path

from pipeline.config import load_feeds
from pipeline.geo import ASSET

# English display names for every ISO_A2_EH code present in the bundled asset
# (42 features). Verified against the asset's code set on 2026-07-11.
COUNTRY_NAMES: dict[str, str] = {
    "AD": "Andorra",
    "AL": "Albania",
    "AT": "Austria",
    "BA": "Bosnia and Herzegovina",
    "BE": "Belgium",
    "BG": "Bulgaria",
    "BY": "Belarus",
    "CH": "Switzerland",
    "CZ": "Czechia",
    "DE": "Germany",
    "DK": "Denmark",
    "EE": "Estonia",
    "ES": "Spain",
    "FI": "Finland",
    "FR": "France",
    "GB": "United Kingdom",
    "GR": "Greece",
    "HR": "Croatia",
    "HU": "Hungary",
    "IE": "Ireland",
    "IT": "Italy",
    "LI": "Liechtenstein",
    "LT": "Lithuania",
    "LU": "Luxembourg",
    "LV": "Latvia",
    "MC": "Monaco",
    "MD": "Moldova",
    "ME": "Montenegro",
    "MK": "North Macedonia",
    "NL": "Netherlands",
    "NO": "Norway",
    "PL": "Poland",
    "PT": "Portugal",
    "RO": "Romania",
    "RS": "Serbia",
    "SE": "Sweden",
    "SI": "Slovenia",
    "SK": "Slovakia",
    "SM": "San Marino",
    "TR": "Turkey",
    "UA": "Ukraine",
    "XK": "Kosovo",
}


def build_coverage(covered: set[str], asset_path: Path = ASSET) -> dict:
    """GeoJSON FeatureCollection: one feature per bundled country, geometry kept,
    properties reduced to {ISO_A2_EH, name, covered}. `covered` is True when the
    feature's ISO code is in `covered`."""
    fc = json.loads(asset_path.read_text(encoding="utf-8"))
    features = []
    for f in fc["features"]:
        iso = f["properties"]["ISO_A2_EH"]
        features.append(
            {
                "type": "Feature",
                "geometry": f["geometry"],
                "properties": {
                    "ISO_A2_EH": iso,
                    "name": COUNTRY_NAMES.get(iso, iso),
                    "covered": iso in covered,
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def covered_from_feeds(feeds_path: Path) -> set[str]:
    """The set of `country` fields declared across all feeds in a feeds.toml."""
    return {cfg.country for cfg in load_feeds(feeds_path).values()}
