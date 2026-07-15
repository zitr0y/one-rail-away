import gzip
import json
import os
from datetime import date

import pytest
from fastapi.testclient import TestClient

from pipeline.artifacts import write_json_with_gzip
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
    out_dir = tmp / "out"
    compute_all(tmp / "graph", out_dir, feeds_path=feeds_toml)
    # rail_paths.json is written by a separate pipeline step (pipeline/railpaths.py,
    # not exercised by build()+compute_all()); hand-write it here so the
    # /api/rail-paths tests below have something to serve.
    write_json_with_gzip(out_dir / "rail_paths.json", json.dumps({
        "attribution": "© OpenStreetMap contributors (ODbL)",
        "paths": {"1111111|2222222": [[0.0, 0.0], [1.0, 1.0]]},
    }))
    test_client = TestClient(create_app(out_dir))
    test_client.data_dir = out_dir  # stashed for tests that need the on-disk files
    return test_client


def test_stations_endpoint(client):
    stations = client.get("/api/stations").json()["stations"]
    assert {s["id"] for s in stations} == {"1111111", "2222222", "3333333", "4444444"}
    alpha = next(s for s in stations if s["id"] == "1111111")
    assert "n_dest" in alpha
    assert "is_capital" in alpha


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
    # fixture likely produces only the dark tier; don't hardcode 2
    assert len(fc["features"]) > 0
    for feature in fc["features"]:
        assert "tier" in feature["properties"]


def test_coverage_gzip_compression(client):
    r = client.get("/api/coverage", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"


def test_coverage_404_when_absent(tmp_path):
    empty = TestClient(create_app(tmp_path))
    assert empty.get("/api/coverage").status_code == 404


def test_cities_endpoint_and_404_when_absent(tmp_path):
    cities = {"Paris": ["paris-nord", "paris-lyon"]}
    write_json_with_gzip(tmp_path / "cities.json", json.dumps(cities))
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/cities").json() == cities

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    empty = TestClient(create_app(empty_dir))
    assert empty.get("/api/cities").status_code == 404


def test_rail_paths_served(tmp_path):
    write_json_with_gzip(
        tmp_path / "rail_paths.json",
        '{"attribution": "© OpenStreetMap contributors (ODbL)", '
        '"paths": {"a|b": [[0, 0], [1, 1]]}}')
    client = TestClient(create_app(tmp_path))
    body = client.get("/api/rail-paths").json()
    assert body["paths"]["a|b"] == [[0, 0], [1, 1]]


def test_rail_paths_404_when_missing(tmp_path):
    client = TestClient(create_app(tmp_path))
    assert client.get("/api/rail-paths").status_code == 404


# --- AV: pre-gzipped static artifacts + HTTP caching -----------------------

ARTIFACT_ENDPOINTS = {
    "/api/rail-paths": "rail_paths.json",
    "/api/coverage": "coverage.json",
    "/api/cities": "cities.json",
    "/api/meta": "meta.json",
}


@pytest.mark.parametrize("url, filename", list(ARTIFACT_ENDPOINTS.items()))
def test_artifact_body_is_byte_identical_to_disk(client, url, filename):
    on_disk = (client.data_dir / filename).read_bytes()
    # httpx (TestClient) transparently decodes gzip, so .content is always
    # the decompressed body regardless of which representation was served.
    assert client.get(url).content == on_disk
    assert client.get(url, headers={"Accept-Encoding": "identity"}).content == on_disk


def test_reach_body_is_byte_identical_to_disk(client):
    on_disk = (client.data_dir / "reach_1111111.json").read_bytes()
    assert client.get("/api/reach/1111111").content == on_disk
    assert client.get("/api/reach/1111111", headers={"Accept-Encoding": "identity"}).content == on_disk


@pytest.mark.parametrize("url", [*ARTIFACT_ENDPOINTS, "/api/reach/1111111"])
def test_content_encoding_reflects_accept_encoding(client, url):
    r = client.get(url, headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"

    r = client.get(url, headers={"Accept-Encoding": "identity"})
    assert r.status_code == 200
    assert "content-encoding" not in r.headers


@pytest.mark.parametrize("url", [*ARTIFACT_ENDPOINTS, "/api/reach/1111111"])
def test_cache_control_header_present(client, url):
    r = client.get(url)
    assert r.headers.get("cache-control") == "public, max-age=21600"


@pytest.mark.parametrize("url", [*ARTIFACT_ENDPOINTS, "/api/reach/1111111"])
def test_conditional_request_returns_304(client, url):
    first = client.get(url)
    assert first.status_code == 200
    etag = first.headers["etag"]

    second = client.get(url, headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.content == b""

    third = client.get(url, headers={"If-Modified-Since": first.headers["last-modified"]})
    assert third.status_code == 304


def test_missing_gzip_sibling_is_a_loud_500_not_a_silent_fallback(tmp_path):
    """Deploys wipe data/out and rebuild fresh, so the pipeline always writes
    the .json and .json.gz pair together; a present .json with no .gz means
    something is broken and must be surfaced, not papered over by quietly
    serving the plain file to a gzip-accepting client."""
    (tmp_path / "coverage.json").write_text('{"type": "FeatureCollection", "features": []}')
    client = TestClient(create_app(tmp_path))

    assert client.get("/api/coverage", headers={"Accept-Encoding": "gzip"}).status_code == 500
    # A client that doesn't accept gzip is unaffected -- no gzip was ever needed.
    assert client.get("/api/coverage", headers={"Accept-Encoding": "identity"}).status_code == 200


def test_stale_gzip_sibling_is_a_loud_500(tmp_path):
    path = tmp_path / "coverage.json"
    write_json_with_gzip(path, '{"type": "FeatureCollection", "features": []}')
    # Simulate a stale .gz (older than the plain file it should mirror).
    os.utime(tmp_path / "coverage.json.gz", (path.stat().st_mtime - 10, path.stat().st_mtime - 10))
    path.write_text('{"type": "FeatureCollection", "features": [1]}')

    client = TestClient(create_app(tmp_path))
    assert client.get("/api/coverage", headers={"Accept-Encoding": "gzip"}).status_code == 500
    assert client.get("/api/coverage", headers={"Accept-Encoding": "identity"}).status_code == 200


def test_stations_and_search_mtime_cache_invalidation(tmp_path):
    stations = [
        {"id": "1", "name": "Alpha", "lat": 0, "lon": 0, "country": "AA"},
        {"id": "2", "name": "Beta", "lat": 0, "lon": 0, "country": "AA"},
    ]
    (tmp_path / "stations.json").write_text(json.dumps({"stations": stations}))
    (tmp_path / "reach_1.json").write_text("{}")
    client = TestClient(create_app(tmp_path))

    first = client.get("/api/stations").json()["stations"]
    assert {s["id"] for s in first} == {"1", "2"}
    assert next(s for s in first if s["id"] == "1")["has_reach"] is True
    assert next(s for s in first if s["id"] == "2")["has_reach"] is False
    assert client.get("/api/stations/search", params={"q": "gam"}).json()["stations"] == []

    # Rewrite stations.json (adds "Gamma") and touch its mtime forward so the
    # in-process cache is invalidated; also add reach files for "2" and "3" so
    # both become searchable, which requires the reach-id cache (keyed on the
    # containing directory's mtime) to notice too.
    stations.append({"id": "3", "name": "Gamma", "lat": 0, "lon": 0, "country": "AA"})
    (tmp_path / "stations.json").write_text(json.dumps({"stations": stations}))
    newer = (tmp_path / "stations.json").stat().st_mtime + 5
    os.utime(tmp_path / "stations.json", (newer, newer))
    (tmp_path / "reach_2.json").write_text("{}")
    (tmp_path / "reach_3.json").write_text("{}")
    # Force the containing directory's mtime forward explicitly rather than
    # relying on filesystem mtime resolution to have ticked between the two
    # writes above (coarse on some filesystems, e.g. 1s on overlayfs).
    dir_newer = tmp_path.stat().st_mtime + 5
    os.utime(tmp_path, (dir_newer, dir_newer))

    second = client.get("/api/stations").json()["stations"]
    assert {s["id"] for s in second} == {"1", "2", "3"}
    assert next(s for s in second if s["id"] == "2")["has_reach"] is True

    search_hit = client.get("/api/stations/search", params={"q": "gam"}).json()["stations"]
    assert [s["id"] for s in search_hit] == ["3"]
