import json
from datetime import date

from pipeline.build import build
from pipeline.compute import compute_all
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml

SAMPLE = date(2026, 7, 14)


def test_compute_all_writes_reach_files(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    build(raw, tmp_path / "graph", _write_feeds_toml(tmp_path, cfgs), None, SAMPLE)
    compute_all(tmp_path / "graph", tmp_path / "out")

    reach = json.loads((tmp_path / "out" / "reach_1111111.json").read_text())
    beta = next(d for d in reach["destinations"] if d["id"] == "2222222")
    assert beta["direct_per_day"] == 2  # IC 100 + IC 101
    assert beta["journeys"][0]["legs"][0]["from"] == "1111111"  # alias serialization

    stations = json.loads((tmp_path / "out" / "stations.json").read_text())
    alpha = next(s for s in stations["stations"] if s["id"] == "1111111")
    delta = next(s for s in stations["stations"] if s["id"] == "4444444")
    assert alpha["has_reach"] is True and delta["has_reach"] is False

    meta = json.loads((tmp_path / "out" / "meta.json").read_text())
    assert meta["sample_date"] == "2026-07-14" and "computed_at" in meta
