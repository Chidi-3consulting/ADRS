import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

# Add root folder to python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, get_db
from app.models import Organization, User, DataCategory
from app.auth import hash_password
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
    
    # Seed default organizations & regulations
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
def auth_header(db):
    # Setup test admin and return API key placeholder
    pwd = hash_password("test_admin_pass")
    user = User(
        organization_id=1,
        name="Test User",
        email="test@admin.com",
        password_hash=pwd,
        role="admin",
        is_active=True
    )
    db.add(user)
    db.commit()
    return user
