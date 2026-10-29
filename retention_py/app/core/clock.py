"""Single source of 'now'. Phase 1C switches this to timezone-aware UTC."""

from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017 - datetime.UTC is 3.11+; keeps Python 3.10 (cPanel) working


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


# Retention dates are business dates in Nigeria (Africa/Lagos, UTC+1, no daylight saving).
# A fixed offset avoids needing a tz database on the host, and the server's own timezone
# (UTC on most hosts) must never decide which day a deletion date falls on.
BUSINESS_TZ = timezone(timedelta(hours=1), "WAT")


def business_today():
    """Today's date in Lagos."""
    return datetime.now(UTC).astimezone(BUSINESS_TZ).date()


def business_date(moment):
    """The Lagos calendar date of a naive UTC datetime (as stored in the database)."""
    if moment is None:
        return None
    if moment.tzinfo is not None:
        return moment.astimezone(BUSINESS_TZ).date()
    return (moment + timedelta(hours=1)).date()
