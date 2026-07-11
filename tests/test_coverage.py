import json
from datetime import date

from shapely.geometry import Point, shape

from pipeline.build import build
from pipeline.compute import compute_all
from pipeline.coverage import build_coverage, covered_from_feeds
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml, empty_overrides


def test_build_coverage_returns_single_feature_featurecollection():
    fc = build_coverage({"DE", "FR"})
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    feat = fc["features"][0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] in ("Polygon", "MultiPolygon")
    assert feat["properties"] == {}


def test_veil_excludes_covered_country():
    """A point inside Germany (covered) must fall OUTSIDE the veil geometry."""
    fc = build_coverage({"DE"})
    veil = shape(fc["features"][0]["geometry"])
    berlin = Point(13.4, 52.5)
    assert not veil.contains(berlin)


def test_veil_includes_non_covered_country():
    """A point inside Italy (not covered) must fall INSIDE the veil geometry."""
    fc = build_coverage({"DE"})
    veil = shape(fc["features"][0]["geometry"])
    rome = Point(12.5, 41.9)
    assert veil.contains(rome)


def test_veil_excludes_ocean():
    """A point in the Atlantic Ocean must fall OUTSIDE the veil geometry."""
    fc = build_coverage(set())
    veil = shape(fc["features"][0]["geometry"])
    atlantic = Point(-30.0, 40.0)
    assert not veil.contains(atlantic)


def test_veil_overseas_and_uncovered_territories():
    fc_covered = build_coverage({"FR", "NL"})
    veil_covered = shape(fc_covered["features"][0]["geometry"])
    assert not veil_covered.contains(Point(2.35, 48.85))  # Paris (covered, in Europe)
    assert veil_covered.contains(Point(-52.3, 4.9))  # Cayenne (overseas, outside Europe)
    assert veil_covered.contains(Point(-68.26, 12.2))  # Bonaire (overseas, outside Europe)

    fc_empty = build_coverage(set())
    veil_empty = shape(fc_empty["features"][0]["geometry"])
    assert veil_empty.contains(Point(44.06, 9.56))  # Hargeisa, Somaliland (missing/uncovered)


def test_covered_from_feeds_reads_country_fields(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    assert covered_from_feeds(feeds_toml) == {"LA", "BO"}


def test_compute_writes_coverage_json_single_feature(tmp_path):
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
    assert cov["type"] == "FeatureCollection"
    assert len(cov["features"]) == 1
    assert cov["features"][0]["properties"] == {}
    # coverage.json is not a reach_*.json file, so the stale-reach prune leaves it.
    assert (out / "coverage.json").exists()
