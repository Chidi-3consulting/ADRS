import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "sqlite:///" + os.path.join(ROOT, "test.db").replace("\\", "/")
)
sys.path.insert(0, ROOT)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.models  # noqa: E402,F401  (register all models)
from app.auth import hash_password  # noqa: E402
from app.database import Base, SessionLocal, engine, get_db  # noqa: E402
from app.models import Organization, SystemSetting, User  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _truncate_all():
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        else:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture(scope="function")
def db():
    _truncate_all()
    session = SessionLocal()
    org = Organization(name="Test Organisation", slug="test-org", primary_domain="test.local",
                       country="NG", tier="core", status="active")
    session.add(org)
    session.add(SystemSetting(setting_key="setup_complete", setting_value="1"))
    session.commit()
    assert org.id == 1, "seed organisation must receive id 1"
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_user(db):
    user = User(organization_id=1, name="Test Admin User", email="test@admin.com",
                password_hash=hash_password("Str0ng!Pass#99"), role="admin", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_header(auth_user):
    return auth_user
