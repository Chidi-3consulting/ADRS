"""Single source of 'now'. Phase 1C switches this to timezone-aware UTC."""

from datetime import datetime, timezone

UTC = timezone.utc  # datetime.UTC is 3.11+; this keeps Python 3.10 (cPanel) working


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
