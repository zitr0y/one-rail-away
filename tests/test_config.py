from pathlib import Path

from pipeline.config import load_feeds


def test_load_feeds_parses_repo_feeds_toml():
    feeds = load_feeds(Path("feeds.toml"))
    assert "db_fern" in feeds
    assert feeds["db_fern"].country == "DE"
    assert any(p.startswith("^ICE") for p in feeds["db_fern"].route_allow)
