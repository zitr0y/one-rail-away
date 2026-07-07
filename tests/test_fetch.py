import json

import httpx

from pipeline.config import FeedConfig
from pipeline.fetch import fetch_all


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
