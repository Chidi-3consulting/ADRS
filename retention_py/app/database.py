from sqlalchemy import create_engine
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
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
