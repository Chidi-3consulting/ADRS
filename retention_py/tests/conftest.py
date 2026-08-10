import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

os.environ["APP_ENV"] = "test"

# Add root folder to python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.config
app.config.APP_ENV = "test"

from app.database import Base, get_db
from app.models import Organization, User, DataCategory, DataRecord
from app.auth import hash_password, build_session_data
from main import app

# File-based SQLite for testing to allow thread-safe access
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    # Remove existing test DB if any
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except Exception:
            pass

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    # Seed default organization
    org = Organization(
        id=1,
        name="Test Organisation",
        slug="test-org",
        primary_domain="test.local",
        country="NG",
        tier="core",
        status="active"
    )
    session.add(org)
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)

    # Cleanup DB file
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except Exception:
            pass

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]

@pytest.fixture
def auth_user(db):
    pwd = hash_password("Password123!")
    user = User(
        organization_id=1,
        name="Test Admin User",
        email="test@admin.com",
        password_hash=pwd,
        role="admin",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def auth_header(auth_user):
    return auth_user
