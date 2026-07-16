from pipeline.cities import load_cities
from pipeline.models import Station


def _station(sid: str, name: str) -> Station:
    return Station(id=sid, name=name, lat=0, lon=0, country="FR")


def test_load_cities_resolves_members_and_skips_invalid_groups(tmp_path):
    path = tmp_path / "cities.toml"
    path.write_text(
        '[cities]\n'
        'Paris = ["Paris Nord", "Paris Lyon", "Unknown Station"]\n'
        'Solo = ["Paris Nord"]\n',
    )
    stations = [_station("nord", "Paris Nord"), _station("lyon", "Paris Lyon")]

    groups, warnings = load_cities(path, stations)

    assert groups == {"Paris": ["nord", "lyon"]}
    assert any("Unknown Station" in warning for warning in warnings)
    assert any("Solo" in warning and "<2 stations" in warning for warning in warnings)


def test_munchen_city_group_resolves():
    from pathlib import Path

    cities_path = Path(__file__).parent.parent / "cities.toml"
    assert cities_path.exists()

    stations = [
        _station("m-hbf", "München Hbf"),
        _station("m-ost", "München Ostbahnhof"),
        _station("g-ost", "Graz Ostbahnhof"),
    ]
    groups, warnings = load_cities(cities_path, stations)

    assert groups["München"] == ["m-hbf", "m-ost"]


def test_rome_city_group_resolves():
    from pathlib import Path

    cities_path = Path(__file__).parent.parent / "cities.toml"
    assert cities_path.exists()

    # Case A: all stations exist (should resolve all 4 to the Roma group)
    stations_all = [
        _station("roma-t", "ROMA TERMINI"),
        _station("roma-tib", "ROMA TIBURTINA"),
        _station("roma-o", "ROMA OSTIENSE"),
        _station("roma-obb", "Roma, Stazione di Roma Tiburtina"),
    ]
    groups, warnings = load_cities(cities_path, stations_all)
    assert groups["Roma"] == ["roma-t", "roma-tib", "roma-o", "roma-obb"]

    # Case B: only ÖBB leak duplicate station exists (fewer than 2 matched, should skip Roma group with warning)
    stations_partial = [
        _station("roma-obb", "Roma, Stazione di Roma Tiburtina"),
    ]
    groups, warnings = load_cities(cities_path, stations_partial)
    assert "Roma" not in groups
    assert any("ROMA TERMINI" in warning for warning in warnings)
    assert any("Roma" in warning and "<2 stations" in warning for warning in warnings)
