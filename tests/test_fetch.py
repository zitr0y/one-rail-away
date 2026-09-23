import json

import httpx

from pipeline.config import FeedConfig
from pipeline.fetch import TRAINLINE_STATIONS_URL, fetch_all, fetch_trainline_stations


def _cfg(url: str) -> FeedConfig:
    return FeedConfig(url=url, country="XX", license="test", route_allow=[])


def test_fetch_isolates_failures(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if "good" in str(request.url):
            return httpx.Response(200, content=b"PK\x03\x04zipbytes")
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    results = fetch_all(
        {"good": _cfg("https://x/good.zip"), "bad": _cfg("https://x/bad.zip")},
        tmp_path,
        client,
    )
    assert results == {"good": True, "bad": False}
    assert (tmp_path / "good.zip").read_bytes().startswith(b"PK")
    assert not (tmp_path / "bad.zip").exists()
    meta = json.loads((tmp_path / "fetch_meta.json").read_text())
    assert meta["good"]["ok"] and not meta["bad"]["ok"]


def test_fetch_trainline_stations_writes_file(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == TRAINLINE_STATIONS_URL
        return httpx.Response(200, content=b"id;name\n1;A\n")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert fetch_trainline_stations(tmp_path, client) is True
    assert (tmp_path / "trainline_stations.csv").read_bytes() == b"id;name\n1;A\n"


def test_fetch_trainline_stations_keeps_previous_on_failure(tmp_path):
    (tmp_path / "trainline_stations.csv").write_bytes(b"old")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    assert fetch_trainline_stations(tmp_path, client) is False
    assert (tmp_path / "trainline_stations.csv").read_bytes() == b"old"
