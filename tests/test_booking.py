from datetime import date
from urllib.parse import parse_qs, urlsplit

from server.booking import HOMEPAGE, booking_target

IDS = {"x:berlin": "7630", "x:munich": "7480"}
TODAY = date(2026, 9, 23)


def test_matched_pair_builds_results_url():
    url, matched = booking_target("x:berlin", "x:munich", "2026-09-29", IDS, TODAY, "")
    assert matched is True
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://www.thetrainline.com/book/results"
    q = parse_qs(parts.query)
    assert q["journeySearchType"] == ["single"]
    assert q["origin"] == ["urn:trainline:generic:loc:7630"]
    assert q["destination"] == ["urn:trainline:generic:loc:7480"]
    assert q["outwardDate"] == ["2026-09-29T06:00:00"]
    assert q["outwardDateType"] == ["departAfter"]
    assert q["selectedTab"] == ["train"]
    assert q["passengers[]"] == ["1996-01-01"]


def test_today_is_allowed():
    _, matched = booking_target("x:berlin", "x:munich", "2026-09-23", IDS, TODAY, "")
    assert matched is True


def test_unmatched_station_falls_back_to_homepage():
    result = booking_target("x:berlin", "x:nowhere", "2026-09-29", IDS, TODAY, "")
    assert result == (HOMEPAGE, False)


def test_yesterday_is_allowed_for_timezone_slack():
    _, matched = booking_target("x:berlin", "x:munich", "2026-09-22", IDS, TODAY, "")
    assert matched is True


def test_past_date_falls_back_to_homepage():
    assert booking_target("x:berlin", "x:munich", "2026-09-21", IDS, TODAY, "") == (HOMEPAGE, False)


def test_malformed_date_falls_back_to_homepage():
    assert booking_target("x:berlin", "x:munich", "29.09.2026", IDS, TODAY, "") == (HOMEPAGE, False)


def test_prefix_wraps_and_encodes_target():
    url, _ = booking_target("x:berlin", "x:nowhere", "2026-09-29", IDS, TODAY,
                            "https://prf.hn/click/camref:ABC/destination:")
    assert url == "https://prf.hn/click/camref:ABC/destination:https%3A%2F%2Fwww.thetrainline.com%2F"
