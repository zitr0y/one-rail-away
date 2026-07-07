"""`ose compute`: run reachability from every station and write the per-station
reach files, the station registry (with `has_reach` flags), and run metadata
consumed by the server.
"""

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from pipeline.models import Destination, ReachFile, Station, Trip
from pipeline.raptor import compute_reachability


def _direct_counts(trips: list[Trip], origin: str) -> Counter:
    """Count, per destination, the number of distinct trips that serve `origin`
    and then later serve that destination in stop order (mid-route boarding
    counts; boarding must strictly precede the destination stop)."""
    counts: Counter = Counter()
    for t in trips:
        seen_origin = False
        for s in t.stops:
            if seen_origin:
                counts[s.station] += 1
            if s.station == origin:
                seen_origin = True
    return counts


def compute_all(graph_dir: Path, out_dir: Path) -> None:
    """For each station in the graph, compute reachability and, if any
    destination is reached, write `out_dir/reach_<id>.json`. Always writes
    `out_dir/stations.json` (registry with `has_reach` flags) and
    `out_dir/meta.json` (run metadata, including upstream feed metadata when
    available)."""
    graph = json.loads((graph_dir / "stations.json").read_text())
    sample_date = graph["sample_date"]
    stations = [Station(**s) for s in graph["stations"]]
    trips = [Trip(**t) for t in json.loads((graph_dir / "trips.json").read_text())["trips"]]
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    for station in stations:
        reach = compute_reachability(trips, station.id)
        if not reach:
            continue
        directs = _direct_counts(trips, station.id)
        rf = ReachFile(
            origin=station.id,
            computed_at=now,
            sample_date=sample_date,
            destinations=[
                Destination(id=dest, direct_per_day=directs.get(dest, 0), journeys=js)
                for dest, js in sorted(reach.items())
            ],
        )
        (out_dir / f"reach_{station.id}.json").write_text(rf.model_dump_json(by_alias=True))
        station.has_reach = True
        print(f"reach_{station.id}.json: {len(reach)} destinations")

    (out_dir / "stations.json").write_text(
        json.dumps({"stations": [s.model_dump() for s in stations]}, ensure_ascii=False)
    )

    fetch_meta_path = Path("data/raw/fetch_meta.json")
    feeds_meta = json.loads(fetch_meta_path.read_text()) if fetch_meta_path.exists() else {}
    (out_dir / "meta.json").write_text(
        json.dumps({"computed_at": now, "sample_date": sample_date, "feeds": feeds_meta})
    )
