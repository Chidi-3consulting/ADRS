import json
import logging
from datetime import timezone

from app.core.logging import JsonFormatter, request_id_var

UTC = timezone.utc  # noqa: UP017 - Python 3.10 compatible


def test_json_formatter_includes_request_id_and_extras():
    token = request_id_var.set("req-123")
    try:
        rec = logging.LogRecord("safedata.test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        rec.job = "retention"
        out = json.loads(JsonFormatter().format(rec))
    finally:
        request_id_var.reset(token)
    assert out["msg"] == "hello world"
    assert out["request_id"] == "req-123"
    assert out["job"] == "retention"
    assert out["level"] == "INFO"


def test_request_id_header_is_echoed_or_generated(client):
    r = client.get("/healthz", headers={"X-Request-ID": "abc-1"})
    assert r.headers["X-Request-ID"] == "abc-1"
    r2 = client.get("/healthz")
    assert len(r2.headers["X-Request-ID"]) == 32


def test_utcnow_is_naive_utc():
    from datetime import datetime

    from app.core.clock import utcnow

    now = utcnow()
    assert now.tzinfo is None
    assert abs((datetime.now(UTC).replace(tzinfo=None) - now).total_seconds()) < 5
