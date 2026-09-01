import sys
import os
import traceback

os.environ["DATABASE_URL"] = "mysql+pymysql://SafeData_user:SafeData_pass@localhost:3306/SafeData_db"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import engine, get_db
from app.routes.app_pages import view_settings
from fastapi import Request

# Create a mock Request
request = Request(scope={
    "type": "http",
    "headers": [(b"host", b"localhost:8200"), (b"cookie", b"SafeData_session=xxx")],
    "path": "/settings"
})

# Mock session
# We can bypass auth and call view_settings directly, but we need to set get_session mock.
import app.routes.app_pages
app.routes.app_pages.get_session = lambda req: {
    "user_id": 1,
    "user_name": "Admin",
    "role": "admin",
    "org_id": 1,
    "org_name": "Test Org",
    "org_domain": "test.com",
    "org_status": "active",
    "country": "NG"
}

db = next(get_db())

try:
    res = view_settings(request, tab="organization", db=db)
    print("GET settings status code:", res.status_code)
except Exception as e:
    print("ERROR in GET settings:")
    traceback.print_exc()
