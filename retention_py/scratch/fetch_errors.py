import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

# Set is_platform_admin = 1 on admin@testcorp.com
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

db_url = os.environ.get("DATABASE_URL", "sqlite:///retention.db")
engine = create_engine(db_url)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()
try:
    from app.models import User
    user = db.query(User).filter(User.email == "admin@testcorp.com").first()
    if user:
        user.is_platform_admin = True
        db.commit()
        print("Set is_platform_admin=True for admin@testcorp.com")
finally:
    db.close()

client = httpx.Client(base_url="http://localhost:8200")

# Login
r = client.post("/login", data={"email": "admin@testcorp.com", "password": "Password123!"})
print("Login status:", r.status_code)
cookies = r.cookies

# Get settings
r = client.get("/settings?tab=organization", cookies=cookies)
print("Settings status:", r.status_code)
if r.status_code != 200:
    print("Settings failed:", r.text[:500])

# Get platform admin dashboard
r = client.get("/platform", cookies=cookies)
print("Platform dashboard status:", r.status_code)
if r.status_code != 200:
    print("Platform failed:", r.text[:500])

# Get platform organizations
r = client.get("/platform/organizations", cookies=cookies)
print("Platform organizations status:", r.status_code)
if r.status_code != 200:
    print("Platform orgs failed:", r.text[:500])
