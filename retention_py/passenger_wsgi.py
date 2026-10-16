"""cPanel "Setup Python App" (Phusion Passenger) entry point for SafeData.

Passenger speaks WSGI; SafeData is an ASGI (FastAPI) app, so it is wrapped with a2wsgi.
Settings are read from a ``.env`` file in this folder (outside the web root) so the
same values are shared by the web app and the cron worker (deploy/cpanel/cron.sh).
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def _load_env(path: str) -> None:
    """Minimal KEY=VALUE loader: no new dependency, never overrides real env vars."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)


_load_env(os.path.join(ROOT, ".env"))

if os.environ.get("SAFEDATA_AUTO_MIGRATE", "1") == "1":
    # Idempotent: brings the schema to the latest Alembic revision on each (re)start.
    from app.cli import cmd_migrate

    cmd_migrate(None)

from a2wsgi import ASGIMiddleware  # noqa: E402

from main import app as asgi_app  # noqa: E402

application = ASGIMiddleware(asgi_app)
