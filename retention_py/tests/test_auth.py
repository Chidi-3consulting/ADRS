from app.models import User, Organization
from app.auth import verify_password

def test_registration_flow(client, db):
    # Perform register request with valid password meeting policy (min 10 chars, letters+numbers)
    response = client.post("/register", data={
        "org_name": "Skyline Ltd",
        "domain": "skyline.com",
        "user_name": "John Doe",
        "email": "john@skyline.com",
        "password": "Xyq9$mNpL2!k",
        "password_confirm": "Xyq9$mNpL2!k",
        "country": "NG"
    }, follow_redirects=False)

    assert response.status_code == 303

    # Check db org and user exist
    org = db.query(Organization).filter(Organization.primary_domain == "skyline.com").first()
    assert org is not None
    assert org.country == "NG"

    user = db.query(User).filter(User.email == "john@skyline.com").first()
    assert user is not None
    assert verify_password("Xyq9$mNpL2!k", user.password_hash)

def test_login_flow(client, db):
    # Register first
    client.post("/register", data={
        "org_name": "Skyline Ltd",
        "domain": "skyline.com",
        "user_name": "John Doe",
        "email": "john@skyline.com",
        "password": "Xyq9$mNpL2!k",
        "password_confirm": "Xyq9$mNpL2!k",
        "country": "NG"
    })

    # Try logging in
    response = client.post("/login", data={
        "email": "john@skyline.com",
        "password": "Xyq9$mNpL2!k"
    }, follow_redirects=False)

    assert response.status_code == 303
    assert "SafeData_session" in response.cookies


def test_login_unknown_email_is_a_normal_failure_not_a_server_error(client, db):
    """Regression: live login returned HTTP 500 for any email with no account.

    The failure branch wrote an audit row with organization_id=0. SQLite (dev)
    ignored the broken foreign key; PostgreSQL (production) rejected it, so the
    request crashed instead of showing "invalid credentials". On a fresh
    database every login is an unknown email, so nobody could sign in.
    """
    from app.models import AuditLog, LoginAttempt

    response = client.post("/login", data={"email": "nobody@example.com", "password": "Whatever-123!"},
                           follow_redirects=False)

    assert response.status_code == 200
    assert "Invalid email credentials" in response.text
    # Still counted for brute-force throttling, which is keyed on email + IP...
    assert db.query(LoginAttempt).filter(LoginAttempt.email == "nobody@example.com",
                                         LoginAttempt.success.is_(False)).count() == 1
    # ...but never attributed to an organisation it does not belong to.
    assert db.query(AuditLog).filter(AuditLog.organization_id == 0).count() == 0


def test_login_wrong_password_on_real_account_is_audited_to_its_org(client, db):
    from app.models import AuditLog

    client.post("/register", data={
        "org_name": "Skyline Ltd", "domain": "skyline.com", "user_name": "John Doe",
        "email": "john@skyline.com", "password": "Xyq9$mNpL2!k", "password_confirm": "Xyq9$mNpL2!k",
        "country": "NG",
    })
    org = db.query(Organization).filter(Organization.primary_domain == "skyline.com").one()

    response = client.post("/login", data={"email": "john@skyline.com", "password": "Wrong-Pass-123!"},
                           follow_redirects=False)

    assert response.status_code == 200
    assert "Invalid email credentials" in response.text
    assert db.query(AuditLog).filter(AuditLog.organization_id == org.id,
                                     AuditLog.action == "login_failed").count() == 1


def test_3consult_domain_and_subdomains_register_as_free_enterprise(client, db):
    for domain in ("3consult-ng.com", "labs.3consult-ng.com"):
        r = client.post("/register", data={
            "org_name": f"3C {domain}", "domain": domain, "user_name": "Staff",
            "email": f"staff@{domain}", "password": "Xyq9$mNpL2!k", "password_confirm": "Xyq9$mNpL2!k",
            "country": "NG",
        }, follow_redirects=False)
        assert r.status_code == 303, domain
        org = db.query(Organization).filter(Organization.primary_domain == domain).one()
        assert (org.tier, org.status, org.trial_ends_at) == ("enterprise", "active", None), domain


def test_lookalike_domain_does_not_get_free_tier(client, db):
    r = client.post("/register", data={
        "org_name": "Impostor", "domain": "evil3consult-ng.com", "user_name": "Mallory",
        "email": "mallory@evil3consult-ng.com", "password": "Xyq9$mNpL2!k", "password_confirm": "Xyq9$mNpL2!k",
        "country": "NG",
    }, follow_redirects=False)
    assert r.status_code == 303
    org = db.query(Organization).filter(Organization.primary_domain == "evil3consult-ng.com").one()
    assert (org.tier, org.status) == ("core", "trial")
    assert org.trial_ends_at is not None
