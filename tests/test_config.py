import re
from pathlib import Path

import pytest

from pipeline.config import FeedConfig, load_feeds


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
        "IC",
        "IC1",
        "IC9",
        "IC51",
        "IC55",
        "IC61",
        "IR",
        "IR13",
        "IR36",
        "IR38",
        "IR75",
        "ICE",
        "EC",
        "RJX",
        "NJ",
    ):
        assert allowed(name), name
    # "IC190A"/"IC190" are French Intercites carried in the Swiss feed (agency 87_LEX);
    # they must stay excluded or their bare-UIC stops duplicate SNCF stations.
    for name in ("S10", "EXT", "EV1", "PB", "SL", "GB", "R", "RE", "IC190A", "IC190"):
        assert not allowed(name), name


def test_stop_id_brand_accepts_pattern_to_brand_table():
    cfg = FeedConfig(
        url="u",
        country="XX",
        license="t",
        route_allow=["."],
        stop_id_brand={"^SP:OCETGV INOUI-": "TGV INOUI"},
    )
    assert cfg.stop_id_brand == {"^SP:OCETGV INOUI-": "TGV INOUI"}


def test_stop_id_brand_and_stop_id_allow_are_mutually_exclusive():
    # Both fields drive the same stop-id trip filter; two sources of truth would
    # let them silently disagree.
    with pytest.raises(ValueError, match="not both"):
        FeedConfig(
            url="u",
            country="XX",
            license="t",
            route_allow=["."],
            stop_id_allow=["^SP:"],
            stop_id_brand={"^SP:": "TGV"},
        )


def test_sncf_stop_id_brand_matches_real_brand_stop_ids():
    """SNCF marks brands only in StopPoint ids; the train number is in trip_headsign.
    These patterns both filter trips and label them (design 2026-07-10)."""
    feeds = load_feeds(Path("feeds.toml"))
    assert feeds["sncf"].stop_id_allow is None  # replaced by stop_id_brand
    table = feeds["sncf"].stop_id_brand

    def brand_for(stop_id):  # mirrors gtfs._brand_label: first pattern match wins
        for pattern, brand in table.items():
            if re.search(pattern, stop_id):
                return brand
        return None

    assert brand_for("StopPoint:OCETGV INOUI-87686006") == "TGV INOUI"
    assert brand_for("StopPoint:OCEOUIGO-87686006") == "OUIGO"
    assert brand_for("StopPoint:OCEICE-87113001") == "ICE"
    assert brand_for("StopPoint:OCELyria-87686006") == "TGV Lyria"
    assert brand_for("StopPoint:OCEINTERCITES-87547000") == "Intercités"
    # "de nuit" must NOT be captured by the plain INTERCITES pattern: each
    # pattern requires a hyphen immediately after its brand string.
    assert brand_for("StopPoint:OCEINTERCITES de nuit-87547000") == "Intercités de nuit"
    assert brand_for("StopPoint:OCETrain-87271007") == "IC"
    # TER and road coaches stay excluded ("Train TER" has a space, not a hyphen).
    assert brand_for("StopPoint:OCETrain TER-87271007") is None
    assert brand_for("StopPoint:OCECar TER-87271007") is None
