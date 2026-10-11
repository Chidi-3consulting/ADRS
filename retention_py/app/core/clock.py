"""Single source of 'now'. Phase 1C switches this to timezone-aware UTC."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
