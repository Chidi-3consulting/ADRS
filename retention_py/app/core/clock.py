"""Single source of 'now'. Phase 1C switches this to timezone-aware UTC."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
