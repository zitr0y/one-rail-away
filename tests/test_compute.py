import json
from datetime import date

from pipeline.build import build
from pipeline.capitals import load_capitals
from pipeline.compute import compute_all
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml, empty_overrides

SAMPLE = date(2026, 7, 14)


def test_compute_all_writes_reach_files(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    build(
        raw,
        tmp_path / "graph",
        feeds_toml,
        None,
        SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    compute_all(tmp_path / "graph", tmp_path / "out", feeds_path=feeds_toml)

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


def test_compute_all_prunes_stale_reach_files(tmp_path):
    # A station whose canonical id changed between runs (Konstanz alias, 2026-07-09)
    # leaves its old reach file behind; the server derives has_reach from files on
    # disk, so a stale file resurrects a dead station in search. Prune it.
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    build(
        raw,
        tmp_path / "graph",
        feeds_toml,
        None,
        SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    out = tmp_path / "out"
    out.mkdir()
    stale = out / "reach_9999999.json"
    stale.write_text("{}")
    compute_all(tmp_path / "graph", out, workers=1, feeds_path=feeds_toml)
    assert not stale.exists()
    assert (out / "reach_1111111.json").exists()  # fresh files kept


def test_compute_all_parallel_matches_serial(tmp_path):
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    build(
        raw,
        tmp_path / "graph",
        feeds_toml,
        None,
        SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    compute_all(tmp_path / "graph", tmp_path / "serial", workers=1, feeds_path=feeds_toml)
    compute_all(tmp_path / "graph", tmp_path / "par", workers=2, feeds_path=feeds_toml)

    def reach_files(d):  # computed_at differs across runs (not within), drop it
        return {
            p.name: {k: v for k, v in json.loads(p.read_text()).items() if k != "computed_at"}
            for p in d.glob("reach_*.json")
        }

    serial, par = reach_files(tmp_path / "serial"), reach_files(tmp_path / "par")
    assert serial and serial == par
    s_stations = json.loads((tmp_path / "serial" / "stations.json").read_text())
    p_stations = json.loads((tmp_path / "par" / "stations.json").read_text())
    assert s_stations == p_stations  # has_reach flags identical


def test_compute_all_writes_n_dest(tmp_path):
    """n_dest on each station equals the destination count from its reach file."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    build(
        raw,
        tmp_path / "graph",
        feeds_toml,
        None,
        SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    compute_all(tmp_path / "graph", tmp_path / "out", feeds_path=feeds_toml)

    stations = json.loads((tmp_path / "out" / "stations.json").read_text())
    alpha = next(s for s in stations["stations"] if s["id"] == "1111111")
    delta = next(s for s in stations["stations"] if s["id"] == "4444444")
    # Alpha reaches Beta, Gamma, Delta → 3 destinations
    assert alpha["n_dest"] == 3
    # Delta has no reach
    assert delta["n_dest"] == 0


def test_compute_all_sets_is_capital(tmp_path):
    """is_capital is set for stations matching capitals.toml entries."""
    raw = tmp_path / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp_path)
    countries_toml.write_text('[countries]\n1111111 = "LA"\n')
    feeds_toml = _write_feeds_toml(tmp_path, cfgs)
    build(
        raw,
        tmp_path / "graph",
        feeds_toml,
        None,
        SAMPLE,
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    # Write a capitals.toml that matches Alpha Hbf in Landia (country=LA)
    (tmp_path / "capitals.toml").write_text('[capitals]\nLA = "Alpha Hbf"\n')
    import os
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        compute_all(tmp_path / "graph", tmp_path / "out", feeds_path=feeds_toml)
    finally:
        os.chdir(old_cwd)

    stations = json.loads((tmp_path / "out" / "stations.json").read_text())
    alpha = next(s for s in stations["stations"] if s["id"] == "1111111")
    beta = next(s for s in stations["stations"] if s["id"] == "2222222")
    assert alpha["is_capital"] is True
    assert beta["is_capital"] is False


def test_load_capitals_warns_on_unmatched(tmp_path):
    """An entry in capitals.toml that matches no station produces a warning, not an error."""
    from pipeline.models import Station

    toml_path = tmp_path / "capitals.toml"
    toml_path.write_text('[capitals]\nXX = "Nonexistent Station"\nLA = "Alpha Hbf"\n')
    stations = [
        Station(id="1111111", name="Alpha Hbf", lat=50, lon=8, country="LA"),
    ]
    ids, warnings = load_capitals(toml_path, stations)
    assert ids == {"1111111"}
    assert len(warnings) == 1
    assert "XX" in warnings[0] and "Nonexistent" in warnings[0]


def test_load_capitals_missing_file(tmp_path):
    """Missing capitals.toml returns empty set and no warnings (graceful)."""
    ids, warnings = load_capitals(tmp_path / "nope.toml", [])
    assert ids == set()
    assert warnings == []
