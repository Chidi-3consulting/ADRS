"""SafeData operations CLI: python -m app.cli <command>."""
from __future__ import annotations

import argparse
import logging
import os
import sys

from alembic import command
from alembic.config import Config

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log = logging.getLogger("safedata.cli")


def alembic_config(url: str | None = None) -> Config:
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "alembic"))
    if url:
        cfg.set_main_option("sqlalchemy.url_override", url)
    return cfg


def cmd_migrate(_args) -> int:
    command.upgrade(alembic_config(), "head")
    return 0


def cmd_adopt_legacy_db(_args) -> int:
    """For databases created by the old import-time create_all: patch legacy columns,
    create any missing tables, verify no drift, then stamp the baseline."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    import app.models  # noqa: F401
    from app.core.legacy_schema import ensure_legacy_columns
    from app.database import Base, engine

    ensure_legacy_columns(engine)
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    if diff:
        log.error("Legacy DB still differs from models; not stamping: %s", diff)
        return 1
    command.stamp(alembic_config(), "0001_baseline")
    command.upgrade(alembic_config(), "head")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate").set_defaults(fn=cmd_migrate)
    sub.add_parser("adopt-legacy-db").set_defaults(fn=cmd_adopt_legacy_db)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())