from datetime import date

import pytest
from fastapi.testclient import TestClient

from pipeline.build import build
from pipeline.compute import compute_all
from server.app import create_app
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml, empty_overrides


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("world")
    raw = tmp / "raw"
    cfgs = make_fixture_feeds(raw)
    countries_toml, names_toml = empty_overrides(tmp)
    feeds_toml = _write_feeds_toml(tmp, cfgs)
    build(
        raw,
        tmp / "graph",
        feeds_toml,
        None,
        date(2026, 7, 14),
        station_names_path=names_toml,
        station_countries_path=countries_toml,
    )
    compute_all(tmp / "graph", tmp / "out", feeds_path=feeds_toml)
    return TestClient(create_app(tmp / "out"))


def test_stations_endpoint(client):
    stations = client.get("/api/stations").json()["stations"]
    assert {s["id"] for s in stations} == {"1111111", "2222222", "3333333", "4444444"}


def test_reach_endpoint(client):
    r = client.get("/api/reach/1111111")
    assert r.status_code == 200 and r.json()["origin"] == "1111111"
    assert client.get("/api/reach/9999999").status_code == 404


def test_meta_and_503(client, tmp_path):
    assert client.get("/api/meta").json()["sample_date"] == "2026-07-14"
    empty = TestClient(create_app(tmp_path))
    assert empty.get("/api/meta").status_code == 503


def test_coverage_endpoint(client):
    r = client.get("/api/coverage")
    assert r.status_code == 200
    fc = r.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    assert fc["features"][0]["properties"] == {}


def test_coverage_404_when_absent(tmp_path):
    empty = TestClient(create_app(tmp_path))
    assert empty.get("/api/coverage").status_code == 404
