from datetime import date

import pytest
from fastapi.testclient import TestClient

from pipeline.build import build
from pipeline.compute import compute_all
from server.app import create_app
from tests.fixtures import make_fixture_feeds
from tests.test_build import _write_feeds_toml


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("world")
    raw = tmp / "raw"
    cfgs = make_fixture_feeds(raw)
    build(raw, tmp / "graph", _write_feeds_toml(tmp, cfgs), None, date(2026, 7, 14))
    compute_all(tmp / "graph", tmp / "out")
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
