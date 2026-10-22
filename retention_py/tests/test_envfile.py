"""The CLI and the web app must read the same .env on the server."""

import os

from app.core.envfile import load_env_file, prepare_server_environment


def test_load_env_file_parses_and_never_overrides_real_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "\n"
        "PLAIN=one\n"
        'DOUBLE="two words"\n'
        "SINGLE='three'\n"
        "export EXPORTED=four\n"
        "EQUALS=a=b=c\n"
        "ALREADY_SET=from-file\n",
        encoding="utf-8",
    )
    for key in ("PLAIN", "DOUBLE", "SINGLE", "EXPORTED", "EQUALS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ALREADY_SET", "from-real-env")

    assert load_env_file(str(env)) is True
    assert os.environ["PLAIN"] == "one"
    assert os.environ["DOUBLE"] == "two words"
    assert os.environ["SINGLE"] == "three"
    assert os.environ["EXPORTED"] == "four"
    assert os.environ["EQUALS"] == "a=b=c"
    assert os.environ["ALREADY_SET"] == "from-real-env"


def test_missing_env_file_is_not_an_error(tmp_path):
    assert load_env_file(str(tmp_path / "nope.env")) is False


def test_prepare_server_environment_sets_utf8_postgres_client(tmp_path, monkeypatch):
    monkeypatch.delenv("PGCLIENTENCODING", raising=False)
    prepare_server_environment(str(tmp_path))
    assert os.environ["PGCLIENTENCODING"] == "UTF8"


def test_cli_reads_dotenv_before_touching_the_database(monkeypatch):
    """Regression: `python -m app.cli` ignored .env, so on the server it wrote to a
    stray SQLite file instead of the live PostgreSQL database."""
    import app.cli as cli

    calls = []
    monkeypatch.setattr("app.core.envfile.prepare_server_environment",
                        lambda root: calls.append(root) or True)
    monkeypatch.setattr(cli, "cmd_migrate", lambda _args: 0)
    assert cli.main(["migrate"]) == 0
    assert calls == [cli.ROOT]
