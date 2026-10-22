"""Load a KEY=VALUE settings file into os.environ.

Shared by every way SafeData starts on cPanel — the web app (passenger_wsgi.py)
and the operations CLI (python -m app.cli) — so they always read the same
database and secrets. Before this existed, the CLI ignored .env and silently
fell back to a local SQLite file, so `create-admin` run on the server created
the account in the wrong database.

Deliberately tiny: no new dependency, and real environment variables always win
over the file (os.environ.setdefault), so cPanel's own env settings are respected.
"""

from __future__ import annotations

import os


def load_env_file(path: str) -> bool:
    """Apply settings from ``path``; return False if the file does not exist."""
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key.startswith("export "):
                key = key[len("export ") :].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key, value)
    return True


def prepare_server_environment(app_root: str) -> bool:
    """Load ``<app_root>/.env`` and apply cPanel database defaults."""
    loaded = load_env_file(os.path.join(app_root, ".env"))
    # cPanel creates PostgreSQL databases as SQL_ASCII, which makes psycopg2 fall
    # back to the ascii codec and fail on any non-ASCII text (accented names, etc.).
    # libpq reads this on every connect, so the whole process talks UTF-8.
    os.environ.setdefault("PGCLIENTENCODING", "UTF8")
    return loaded
