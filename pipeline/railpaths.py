"""Real rail geometry for reach-line hops (backlog item I).

Builds a speed-weighted rail graph from OSM extracts and writes
data/out/rail_paths.json: one polyline per unique physical hop found in the
reach files, keyed like the web's segmentKey ("idA|idB", idA < idB, path
oriented idA→idB). Unroutable hops and unsnappable stations are reported in
data/out/rail_paths_report.json instead of failing the build; the web falls
back to straight lines for anything missing.
"""

from __future__ import annotations

import itertools
import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_SPEED_KMH = 100.0
MIN_SPEED_KMH = 10.0
MAX_SPEED_KMH = 320.0

_SPEED_RE = re.compile(r"(\d+(?:\.\d+)?)")


def collect_hops(out_dir: Path) -> set[tuple[str, str]]:
    """Direction-normalized unique station-pair hops across all reach files."""
    hops: set[tuple[str, str]] = set()
    for path in sorted(out_dir.glob("reach_*.json")):
        reach = json.loads(path.read_text(encoding="utf-8"))
        for dest in reach["destinations"]:
            for journey in dest["journeys"]:
                for leg in journey["legs"]:
                    stops = [leg["from"], *leg["via"], leg["to"]]
                    for a, b in itertools.pairwise(stops):
                        if a != b:
                            hops.add((a, b) if a < b else (b, a))
    return hops


def parse_maxspeed(value: str | None) -> float:
    """OSM maxspeed tag → km/h, defaulted and clamped to sane rail bounds."""
    if not value:
        return DEFAULT_SPEED_KMH
    match = _SPEED_RE.search(value)
    if not match:
        return DEFAULT_SPEED_KMH
    speed = float(match.group(1))
    if "mph" in value:
        speed *= 1.609344
    return min(max(speed, MIN_SPEED_KMH), MAX_SPEED_KMH)
