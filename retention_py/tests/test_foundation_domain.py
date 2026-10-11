from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_no_wrong_domain_literals_in_app():
    offenders = [str(p) for p in APP_DIR.rglob("*") if p.suffix in (".py", ".html")
                 and "3consulting.com" in p.read_text(encoding="utf-8", errors="replace")]
    assert offenders == []


def test_legacy_host_redirects_to_canonical(client, monkeypatch):
    monkeypatch.setattr("app.middleware.LEGACY_HOSTS", ["old.example.com"])
    monkeypatch.setattr("app.middleware.APP_URL", "https://safedata.3consult-ng.com")
    r = client.get("/login?next=/records", headers={"host": "old.example.com"}, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://safedata.3consult-ng.com/login?next=/records"


def test_canonical_host_not_redirected(client):
    r = client.get("/login", follow_redirects=False)
    assert r.status_code == 200


def test_default_sender_uses_mail_domain():
    from app import config
    assert config.SMTP_FROM_EMAIL == f"noreply@{config.MAIL_DOMAIN}"  # SMTP_FROM_EMAIL unset in tests


def test_canonical_host_is_outermost_then_request_id():
    from main import app
    names = [m.cls.__name__ for m in app.user_middleware]  # outermost first
    assert names[0] == "CanonicalHostMiddleware"
    assert names[1] == "RequestIdMiddleware"
