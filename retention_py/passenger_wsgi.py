"""cPanel "Setup Python App" (Phusion Passenger) entry point for SafeData.

Passenger speaks WSGI; SafeData is an ASGI (FastAPI) app, so it is wrapped with a2wsgi.
Settings are read from a ``.env`` file in this folder (outside the web root) so the
same values are shared by the web app and the cron worker (deploy/cpanel/cron.sh).
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


from app.core.envfile import prepare_server_environment  # noqa: E402

# .env next to this file, plus the UTF-8 client encoding cPanel PostgreSQL needs.
# The CLI calls the same function, so both always talk to the same database.
prepare_server_environment(ROOT)

if os.environ.get("SAFEDATA_AUTO_MIGRATE", "1") == "1":
    # Idempotent: brings the schema to the latest Alembic revision on each (re)start.
    from app.cli import cmd_migrate

    # Passenger may start several workers at once; only one may run migrations at a time.
    try:
        import fcntl

        _lock = open(os.path.join(ROOT, ".migrate.lock"), "w")
        fcntl.flock(_lock, fcntl.LOCK_EX)
    except (ImportError, OSError):
        _lock = None
    try:
        cmd_migrate(None)
    finally:
        if _lock is not None:
            _lock.close()

from a2wsgi import ASGIMiddleware  # noqa: E402

from main import app as asgi_app  # noqa: E402

application = ASGIMiddleware(asgi_app)
