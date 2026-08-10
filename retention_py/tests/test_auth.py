from app.models import User, Organization
from app.auth import verify_password

def test_registration_flow(client, db):
    # Perform register request with valid password meeting policy (min 10 chars, letters+numbers)
    response = client.post("/register", data={
        "org_name": "Skyline Ltd",
        "domain": "skyline.com",
        "user_name": "John Doe",
        "email": "john@skyline.com",
        "password": "SuperSecurePassword123!",
        "password_confirm": "SuperSecurePassword123!",
        "country": "NG"
    }, follow_redirects=False)

    assert response.status_code == 303

    # Check db org and user exist
    org = db.query(Organization).filter(Organization.primary_domain == "skyline.com").first()
    assert org is not None
    assert org.country == "NG"

    user = db.query(User).filter(User.email == "john@skyline.com").first()
    assert user is not None
    assert verify_password("SuperSecurePassword123!", user.password_hash)

def test_login_flow(client, db):
    # Register first
    client.post("/register", data={
        "org_name": "Skyline Ltd",
        "domain": "skyline.com",
        "user_name": "John Doe",
        "email": "john@skyline.com",
        "password": "SuperSecurePassword123!",
        "password_confirm": "SuperSecurePassword123!",
        "country": "NG"
    })

    # Try logging in
    response = client.post("/login", data={
        "email": "john@skyline.com",
        "password": "SuperSecurePassword123!"
    }, follow_redirects=False)

    assert response.status_code == 303
    assert "adrs_session" in response.cookies
