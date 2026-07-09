import json

from pipeline.geo import assign_countries, country_at, load_countries
from pipeline.models import Station


def _fixture(tmp_path):
    # DE: unit-ish square with a hole; FR adjacent square. GeoJSON is [lon, lat].
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                # Natural Earth quirk under test: ISO_A2 is "-99" for FR/NO,
                # ISO_A2_EH carries the real code.
                "properties": {"ISO_A2_EH": "DE", "ISO_A2": "-99"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
                        [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
                    ],
                },
            },
            {
                "type": "Feature",
                "properties": {"ISO_A2_EH": "FR"},
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[[[10, 0], [20, 0], [20, 10], [10, 10], [10, 0]]]],
                },
            },
        ],
    }
    p = tmp_path / "countries.geojson"
    p.write_text(json.dumps(fc))
    return load_countries(p)


def test_point_in_polygon(tmp_path):
    countries = _fixture(tmp_path)
    assert country_at(2.0, 2.0, countries) == "DE"  # lat=2, lon=2
    assert country_at(5.0, 15.0, countries) == "FR"


def test_point_in_hole_matches_nothing(tmp_path):
    assert country_at(5.0, 5.0, _fixture(tmp_path)) is None


def test_point_outside_matches_nothing(tmp_path):
    assert country_at(50.0, 50.0, _fixture(tmp_path)) is None


def test_iso_a2_eh_preferred(tmp_path):
    # The DE feature carries ISO_A2 "-99"; loader must use ISO_A2_EH.
    assert {iso for iso, _ in _fixture(tmp_path)} == {"DE", "FR"}


def _station(sid, lat, lon, country):
    return Station(id=sid, name=sid, lat=lat, lon=lon, country=country)


def test_assign_countries_corrects_and_logs(tmp_path):
    countries = _fixture(tmp_path)
    s = _station("a", 2.0, 12.0, "DE")  # geographically in FR square
    changes = assign_countries([s], countries, {})
    assert s.country == "FR"
    assert changes == ["a (a): DE -> FR"]


def test_assign_countries_override_wins(tmp_path):
    countries = _fixture(tmp_path)
    s = _station("a", 2.0, 12.0, "DE")
    assign_countries([s], countries, {"a": "CH"})
    assert s.country == "CH"


def test_assign_countries_no_match_keeps_feed_country(tmp_path):
    countries = _fixture(tmp_path)
    s = _station("a", 50.0, 50.0, "DE")
    changes = assign_countries([s], countries, {})
    assert s.country == "DE"
    assert "no polygon match" in changes[0]
