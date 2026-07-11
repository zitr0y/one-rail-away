import json
from datetime import date

from shapely.geometry import Point, shape

from pipeline.build import build
from pipeline.compute import compute_all
from pipeline.coverage import build_coverage, covered_from_feeds
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml, empty_overrides


def test_build_coverage_two_tiers():
    # with covered={'DE'}, reachable={'IT'}:
    # exactly 2 features, first properties {'tier':'light'} containing Rome Point(12.5,41.9),
    # second {'tier':'dark'} containing Hargeisa Point(44.06,9.56) and NOT containing Rome
    # or Berlin Point(13.4,52.5); light feature does NOT contain Berlin.
    fc = build_coverage(covered={"DE"}, reachable={"IT"})
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 2

    light_feat = fc["features"][0]
    dark_feat = fc["features"][1]

    assert light_feat["properties"] == {"tier": "light"}
    assert dark_feat["properties"] == {"tier": "dark"}

    light_geom = shape(light_feat["geometry"])
    dark_geom = shape(dark_feat["geometry"])

    rome = Point(12.5, 41.9)
    berlin = Point(13.4, 52.5)
    hargeisa = Point(44.06, 9.56)

    assert light_geom.contains(rome)
    assert not light_geom.contains(berlin)

    assert dark_geom.contains(hargeisa)
    assert not dark_geom.contains(rome)
    assert not dark_geom.contains(berlin)


def test_build_coverage_one_tier():
    # With covered={'FR','NL'}, reachable=set():
    # 1 feature, tier dark, containing Cayenne Point(-52.3,4.9) and Bonaire Point(-68.26,12.2),
    # not Paris Point(2.35,48.85).
    fc = build_coverage(covered={"FR", "NL"}, reachable=set())
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1

    dark_feat = fc["features"][0]
    assert dark_feat["properties"] == {"tier": "dark"}

    dark_geom = shape(dark_feat["geometry"])

    cayenne = Point(-52.3, 4.9)
    bonaire = Point(-68.26, 12.2)
    paris = Point(2.35, 48.85)

    assert dark_geom.contains(cayenne)
    assert dark_geom.contains(bonaire)
    assert not dark_geom.contains(paris)


def test_covered_from_feeds_reads_country_fields(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    assert covered_from_feeds(feeds_toml) == {"LA", "BO"}


def test_compute_writes_coverage_json_two_tier(tmp_path):
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
    assert len(cov["features"]) > 0
    for feature in cov["features"]:
        assert "tier" in feature["properties"]
    # coverage.json is not a reach_*.json file, so the stale-reach prune leaves it.
    assert (out / "coverage.json").exists()
