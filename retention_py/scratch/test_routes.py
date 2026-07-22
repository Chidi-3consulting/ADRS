import sys
import os

# Set DATABASE_URL to MySQL
# os.environ["DATABASE_URL"] = "mysql+pymysql://adrs_user:adrs_pass@localhost:3306/adrs_db"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Login
response = client.post("/login", data={"email": "admin@testcorp.com", "password": "Password123!"})
print("Login status:", response.status_code)
cookies = response.cookies

# Test records page
response = client.get("/records", cookies=cookies)
print("Records Page status:", response.status_code)
if response.status_code != 200:
    print(response.text[:2000])

# Test settings page
response = client.get("/settings?tab=organization", cookies=cookies)
print("Settings Org tab status:", response.status_code)
if response.status_code != 200:
    print(response.text[:2000])
