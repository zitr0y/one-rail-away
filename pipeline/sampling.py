"""Deterministic, season-aware GTFS service-date sampling."""

from datetime import date, timedelta

# One Tuesday and one Saturday in each quarter.  This deliberately samples both
# a normal weekday and a weekend, while avoiding a misleading contiguous week.
SEASON_MONTHS = (1, 4, 7, 10)
SAMPLE_WEEKDAYS = (1, 5)  # Tuesday, Saturday (datetime.date weekday numbers)


def service_year_sample_dates(anchor: date) -> list[date]:
    """Return the eight fixed service-date probes for ``anchor.year``.

    Each date is the first requested weekday on or after the 8th of Jan/Apr/
    Jul/Oct.  Keeping this independent of today makes rebuilds reproducible.
    """
    dates: list[date] = []
    for month in SEASON_MONTHS:
        start = date(anchor.year, month, 8)
        for weekday in SAMPLE_WEEKDAYS:
            dates.append(start + timedelta(days=(weekday - start.weekday()) % 7))
    return sorted(dates)
