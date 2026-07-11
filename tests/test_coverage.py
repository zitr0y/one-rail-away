import json
from datetime import date

from pipeline.build import build
from pipeline.compute import compute_all
from pipeline.coverage import COUNTRY_NAMES, build_coverage, covered_from_feeds
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml, empty_overrides


def test_build_coverage_flags_only_covered_countries():
    fc = build_coverage({"DE", "FR"})
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 42
    covered = {f["properties"]["ISO_A2_EH"] for f in fc["features"] if f["properties"]["covered"]}
    assert covered == {"DE", "FR"}


def test_build_coverage_carries_name_and_geometry_on_every_feature():
    fc = build_coverage(set())
    for f in fc["features"]:
        assert f["properties"]["name"]
        assert f["geometry"]["type"] in ("Polygon", "MultiPolygon")
    de = next(f for f in fc["features"] if f["properties"]["ISO_A2_EH"] == "DE")
    assert de["properties"]["name"] == "Germany"
    assert de["properties"]["covered"] is False


def test_country_names_covers_every_asset_iso():
    fc = build_coverage(set())
    for f in fc["features"]:
        assert f["properties"]["ISO_A2_EH"] in COUNTRY_NAMES


def test_covered_from_feeds_reads_country_fields(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    assert covered_from_feeds(feeds_toml) == {"LA", "BO"}


def test_compute_writes_coverage_json_that_survives_pruning(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    countries_toml, names_toml = empty_overrides(tmp_path)
    graph = tmp_path / "graph"
    out = tmp_path / "out"
    build(
        raw,
        graph,
        feeds_toml,
        None,
        date(2026, 7, 14),
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    compute_all(graph, out, workers=1, feeds_path=feeds_toml)
    cov = json.loads((out / "coverage.json").read_text())
    assert len(cov["features"]) == 42
    # LA/BO are fixture pseudo-codes absent from the asset, so nothing is covered.
    assert not any(f["properties"]["covered"] for f in cov["features"])
    # coverage.json is not a reach_*.json file, so the stale-reach prune leaves it.
    assert (out / "coverage.json").exists()
