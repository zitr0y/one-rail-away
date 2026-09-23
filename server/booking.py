"""Trainline booking handoff target (backlog N).

The results-URL format is verified (2026-09-23) but not officially documented
by Trainline, so every failure path falls back to the homepage. Affiliate
tracking is a prefix supplied via env once Partnerize approves us; nothing
affiliate-related is hardcoded here.
"""

from datetime import date, timedelta
from urllib.parse import quote, urlencode

HOMEPAGE = "https://www.thetrainline.com/"
RESULTS = "https://www.thetrainline.com/book/results"


def booking_target(
    from_id: str, to_id: str, date_str: str, ids: dict[str, str], today: date, prefix: str
) -> tuple[str, bool]:
    """(url to redirect to, whether it is a prefilled results search)."""
    origin, destination = ids.get(from_id), ids.get(to_id)
    try:
        travel = date.fromisoformat(date_str)
    except ValueError:
        travel = None
    # One day of slack: `today` is Berlin's, and a user west of it picking their
    # local today late in the evening is already on Berlin's tomorrow.
    matched = bool(origin and destination and travel and travel >= today - timedelta(days=1))
    if matched:
        target = RESULTS + "?" + urlencode({
            "journeySearchType": "single",
            "origin": f"urn:trainline:generic:loc:{origin}",
            "destination": f"urn:trainline:generic:loc:{destination}",
            "outwardDate": f"{travel.isoformat()}T06:00:00",
            "outwardDateType": "departAfter",
            "selectedTab": "train",
            # One adult; Trainline asks for a date of birth per passenger.
            "passengers[]": date(today.year - 30, 1, 1).isoformat(),
        })
    else:
        target = HOMEPAGE
    if prefix:
        target = prefix + quote(target, safe="")
    return target, matched
