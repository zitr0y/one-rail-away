import json

from pipeline.geo import assign_countries, country_at, load_countries
from pipeline.models import CountryOverride, Station


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
    changes = assign_countries([s], countries, [])
    assert s.country == "FR"
    assert changes == ["a (a): DE -> FR"]


def test_assign_countries_override_wins(tmp_path):
    countries = _fixture(tmp_path)
    s = _station("a", 2.0, 12.0, "DE")
    override = CountryOverride(name="A border override", lat=2.0, lon=12.0, country="CH")
    changes = assign_countries([s], countries, [override])
    assert s.country == "CH"
    assert changes == ["a (a): DE -> CH"]


def test_assign_countries_override_matches_station_within_radius(tmp_path):
    countries = _fixture(tmp_path)
    s = _station("a", 2.001, 12.0, "DE")  # about 111m north of the override
    override = CountryOverride(name="Nearby override", lat=2.0, lon=12.0, country="CH")
    changes = assign_countries([s], countries, [override])
    assert s.country == "CH"
    assert changes == ["a (a): DE -> CH"]


def test_assign_countries_unmatched_override_warns_and_continues(tmp_path):
    countries = _fixture(tmp_path)
    s = _station("a", 2.0, 12.0, "DE")  # polygon lookup must still change it to FR
    override = CountryOverride(name="Nowhere", lat=50.0, lon=50.0, country="CH")
    changes = assign_countries([s], countries, [override])
    assert s.country == "FR"
    assert changes == [
        "unused override 'Nowhere' (50.000000, 50.000000): no station within 500m",
        "a (a): DE -> FR",
    ]


def test_assign_countries_ambiguous_override_warns_and_nearest_wins():
    near = _station("near", 2.0002, 12.0, "DE")
    far = _station("far", 2.001, 12.0, "DE")
    override = CountryOverride(name="Border", lat=2.0, lon=12.0, country="CH")
    changes = assign_countries([near, far], [], [override])
    assert near.country == "CH"
    assert far.country == "DE"
    assert changes[0] == (
        "ambiguous override 'Border' (2.000000, 12.000000): 2 stations within 500m "
        "(near (near), far (far)); using near (near)"
    )
    assert changes[1] == "near (near): DE -> CH"


def test_assign_countries_no_match_keeps_feed_country(tmp_path):
    countries = _fixture(tmp_path)
    s = _station("a", 50.0, 50.0, "DE")
    changes = assign_countries([s], countries, [])
    assert s.country == "DE"
    assert "no polygon match" in changes[0]
