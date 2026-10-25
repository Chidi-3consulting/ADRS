"""`python -m app.cli create-admin` must say why it failed.

Alembic's logging setup used to disable the app's loggers, so a rejected password
exited with status 1 and no message on the server.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_rejected_password_is_reported(tmp_path):
    env = dict(os.environ)
    env.update(
        DATABASE_URL="sqlite:///" + str(tmp_path / "cli.db"),
        APP_ENV="test",
        SAFEDATA_AUTO_MIGRATE="1",
        SAFEDATA_ADMIN_PASSWORD="short",
        SECRET_KEY="t" * 64,
    )
    proc = subprocess.run(
        [sys.executable, "-m", "app.cli", "create-admin", "--email", "boss@example.org"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 1
    assert "Password rejected by policy" in (proc.stderr + proc.stdout)
