import app.database as database


def test_app_engine_is_the_test_database():
    url = str(database.engine.url)
    assert "test" in url, f"app engine points at non-test DB: {url}"


def test_main_uses_the_same_session_factory():
    import main

    assert main.SessionLocal is database.SessionLocal


def test_password_hashing_uses_fast_rounds_in_tests():
    from app.auth import hash_password, verify_password

    h = hash_password("Xyq9$mNpL2!k")
    assert h.startswith("$2b$04$")
    assert verify_password("Xyq9$mNpL2!k", h)


def test_seeded_org_has_id_1(db):
    from app.models import Organization

    assert db.get(Organization, 1) is not None
