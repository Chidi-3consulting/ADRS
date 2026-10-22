from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL

# Render PostgreSQL URLs use the legacy `postgres://` scheme.
# SQLAlchemy 2.x only accepts `postgresql://` — rewrite silently.
_db_url = DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = "postgresql://" + _db_url[len("postgres://"):]

# SQLite needs check_same_thread=False; PostgreSQL uses connection pooling
connect_args = {}
engine_kwargs: dict = {"pool_pre_ping": True}
if _db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine_kwargs = {}  # no pool_pre_ping for SQLite

engine = create_engine(_db_url, connect_args=connect_args, **engine_kwargs)

if engine.dialect.name == "sqlite":
    # SQLite ignores foreign keys unless asked; PostgreSQL (production) always
    # enforces them. Without this, dev and tests accept writes that crash live.
    @event.listens_for(engine, "connect")
    def _sqlite_enforce_foreign_keys(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
