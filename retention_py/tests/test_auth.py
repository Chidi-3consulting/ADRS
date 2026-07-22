from app.models import User, Organization
from app.auth import verify_password

def test_registration_flow(client, db):
    # Perform register request
    response = client.post("/register", data={
        "org_name": "Skyline Ltd",
        "domain": "skyline.local",
        "user_name": "John Doe",
        "email": "john@skyline.com",
        "password": "supersecurepassword",
        "country": "NG"
    }, follow_redirects=False)
    
    assert response.status_code == 303
    
    # Check db org and user exist
    org = db.query(Organization).filter(Organization.primary_domain == "skyline.local").first()
    assert org is not None
    assert org.country == "NG"
    
    user = db.query(User).filter(User.email == "john@skyline.com").first()
    assert user is not None
    assert verify_password("supersecurepassword", user.password_hash)

def test_login_flow(client, db):
    # Register first
    client.post("/register", data={
        "org_name": "Skyline Ltd",
        "domain": "skyline.local",
        "user_name": "John Doe",
        "email": "john@skyline.com",
        "password": "supersecurepassword",
        "country": "NG"
    })
    
    # Try logging in
    response = client.post("/login", data={
        "email": "john@skyline.com",
        "password": "supersecurepassword"
    }, follow_redirects=False)
    
    assert response.status_code == 303
    assert "adrs_session" in response.cookies
