import os
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]


def test_importing_main_does_not_touch_the_database(tmp_path):
    db_file = tmp_path / "untouched.db"
    env = {**os.environ, "APP_ENV": "test", "DATABASE_URL": f"sqlite:///{db_file.as_posix()}"}
    subprocess.run([sys.executable, "-c", "import main"], cwd=ROOT, env=env, check=True)
    assert not db_file.exists(), "importing main created/modified the database"


def test_migrations_match_models(tmp_path):
    from app.cli import alembic_config
    from app.database import Base
    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"models and migrations differ: {diff}"


def test_all_enums_are_non_native():
    from sqlalchemy import Enum
    import app.models  # noqa: F401
    from app.database import Base
    native = [f"{t.name}.{c.name}" for t in Base.metadata.sorted_tables for c in t.columns
              if isinstance(c.type, Enum) and c.type.native_enum]
    assert native == []