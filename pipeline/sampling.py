"""Deterministic GTFS service-week selection."""

from datetime import date, timedelta


def service_week_dates(
    anchor: date, window: tuple[str, str] | None = None
) -> list[date]:
    """Return one consecutive, fully covered service week for a feed.

    The Monday containing ``anchor`` is preferred.  A published calendar
    horizon moves that week to the nearest seven-day interval it can wholly
    cover; a shorter horizon contributes its complete consecutive span.  This
    is deliberately independent of the clock, so rebuilding a snapshot is
    reproducible.
    """
    target = anchor - timedelta(days=anchor.weekday())
    if window is None:
        return [target + timedelta(days=offset) for offset in range(7)]

    start = date.fromisoformat(f"{window[0][:4]}-{window[0][4:6]}-{window[0][6:]}")
    end = date.fromisoformat(f"{window[1][:4]}-{window[1][4:6]}-{window[1][6:]}")
    if (end - start).days < 6:
        return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    first = start
    last = end - timedelta(days=6)
    week_start = min(max(target, first), last)
    return [week_start + timedelta(days=offset) for offset in range(7)]
