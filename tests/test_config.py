import re
from pathlib import Path

from pipeline.config import load_feeds


def test_load_feeds_parses_repo_feeds_toml():
    feeds = load_feeds(Path("feeds.toml"))
    assert "db_fern" in feeds
    assert feeds["db_fern"].country == "DE"
    assert any(p.startswith("^ICE") for p in feeds["db_fern"].route_allow)


def test_sbb_route_allow_matches_spaceless_swiss_labels():
    """SBB brands domestic lines without a space (IC1, IR16); '^IC\\b' never matches a
    letter->digit boundary, which silently dropped Swiss domestic service (2026-07-09)."""
    feeds = load_feeds(Path("feeds.toml"))
    patterns = feeds["sbb"].route_allow

    def allowed(name):  # mirrors pipeline/gtfs.py load_feed: any(p.search(...) for p in allow)
        return any(re.search(p, name) for p in patterns)

    for name in (
        "IC", "IC1", "IC9", "IC51", "IC55", "IC61", "IR", "IR13", "IR36", "IR38", "IR75",
        "ICE", "EC", "RJX", "NJ",
    ):
        assert allowed(name), name
    # "IC190A"/"IC190" are French Intercites carried in the Swiss feed (agency 87_LEX);
    # they must stay excluded or their bare-UIC stops duplicate SNCF stations.
    for name in ("S10", "EXT", "EV1", "PB", "SL", "GB", "R", "RE", "IC190A", "IC190"):
        assert not allowed(name), name
