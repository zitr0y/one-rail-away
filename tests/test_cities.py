import logging

from pipeline.cities import load_cities, load_transfers
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


def test_load_transfers_resolves_names_to_post_merge_ids_and_seconds(tmp_path):
    path = tmp_path / "cities.toml"
    path.write_text(
        "[cities]\n"
        'Metroville = ["South Terminal", "North Terminal"]\n'
        "[transfers]\n"
        'Metroville = [["South Terminal", "North Terminal", "metro", 17]]\n',
    )
    stations = [
        _station("merged-south", "South Terminal"),
        _station("merged-north", "North Terminal"),
    ]

    transfers, warnings = load_transfers(path, stations)

    assert transfers == [("merged-south", "merged-north", 1020, "metro")]
    assert warnings == []


def test_load_transfers_warns_and_skips_unresolved_station(tmp_path, caplog):
    path = tmp_path / "cities.toml"
    path.write_text(
        "[cities]\n"
        'Metroville = ["South Terminal", "Missing Terminal"]\n'
        "[transfers]\n"
        'Metroville = [["South Terminal", "Missing Terminal", "metro", 17]]\n',
    )
    stations = [_station("synthetic-id", "South Terminal")]

    with caplog.at_level(logging.WARNING, logger="pipeline.cities"):
        transfers, warnings = load_transfers(path, stations)

    assert transfers == []
    assert len(warnings) == 1
    assert "Metroville" in warnings[0]
    assert "Missing Terminal" in warnings[0]
    assert "no station matches transfer" in warnings[0]
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_load_transfers_warns_and_skips_pair_outside_declared_city_group(
    tmp_path, caplog
):
    path = tmp_path / "cities.toml"
    path.write_text(
        "[cities]\n"
        'Metroville = ["South Terminal"]\n'
        'Elsewhere = ["North Terminal"]\n'
        "[transfers]\n"
        'Metroville = [["South Terminal", "North Terminal", "metro", 17]]\n',
    )
    stations = [
        _station("synthetic-id", "South Terminal"),
        _station("synthetic-north", "North Terminal"),
    ]

    with caplog.at_level(logging.WARNING, logger="pipeline.cities"):
        transfers, warnings = load_transfers(path, stations)

    assert transfers == []
    assert len(warnings) == 1
    assert "does not share" in warnings[0]
    assert "Metroville" in warnings[0]
    assert len(caplog.records) == 1
    assert caplog.records[0].levelno == logging.WARNING


def test_load_transfers_warns_and_skips_invalid_entries(tmp_path, caplog):
    path = tmp_path / "cities.toml"
    path.write_text(
        "[cities]\n"
        'Metroville = ["South Terminal", "North Terminal"]\n'
        "[transfers]\n"
        "Metroville = [\n"
        '  ["South Terminal", "North Terminal", "metro"],\n'
        '  ["South Terminal", "North Terminal", "taxi", 17],\n'
        '  ["South Terminal", "North Terminal", "metro", 0],\n'
        '  ["South Terminal", "North Terminal", "metro", "17"],\n'
        "]\n",
    )
    stations = [
        _station("synthetic-id", "South Terminal"),
        _station("synthetic-north", "North Terminal"),
    ]

    with caplog.at_level(logging.WARNING, logger="pipeline.cities"):
        transfers, warnings = load_transfers(path, stations)

    assert transfers == []
    assert len(warnings) == 4
    assert len(caplog.records) == 4
    assert all(record.levelno == logging.WARNING for record in caplog.records)


def test_load_transfers_missing_file_is_empty(tmp_path):
    transfers, warnings = load_transfers(tmp_path / "missing.toml", [])

    assert (transfers, warnings) == ([], [])


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
