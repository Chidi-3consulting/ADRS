from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_no_wrong_domain_literals_in_app():
    offenders = [
        str(p)
        for p in APP_DIR.rglob("*")
        if p.suffix in (".py", ".html") and "3consulting.com" in p.read_text(encoding="utf-8", errors="replace")
    ]
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


def _legacy(monkeypatch):
    monkeypatch.setattr("app.middleware.LEGACY_HOSTS", ["old.example.com"])
    monkeypatch.setattr("app.middleware.APP_URL", "https://safedata.3consult-ng.com")


def test_redirect_preserves_encoded_non_latin1_path(client, monkeypatch):
    _legacy(monkeypatch)
    r = client.get("/%E2%82%AC?x=1", headers={"host": "old.example.com"}, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://safedata.3consult-ng.com/%E2%82%AC?x=1"


def test_redirect_has_no_header_injection(client, monkeypatch):
    _legacy(monkeypatch)
    r = client.get("/%0d%0aX:y", headers={"host": "old.example.com"}, follow_redirects=False)
    assert r.status_code == 301
    loc = r.headers["location"]
    assert "\r" not in loc and "\n" not in loc


def test_legacy_host_with_port_and_uppercase_redirects(client, monkeypatch):
    _legacy(monkeypatch)
    r = client.get("/login", headers={"host": "OLD.example.com:443"}, follow_redirects=False)
    assert r.status_code == 301


def test_welcome_email_contains_app_url(client, monkeypatch):
    import threading

    import app.helpers as helpers

    sent = []
    monkeypatch.setattr(helpers, "send_system_email", lambda db, to, subj, html: sent.append(html))
    RealThread = threading.Thread

    class SyncThread(RealThread):
        def start(self):
            if getattr(self._target, "__name__", "") == "_send_welcome":
                self.run()
            else:
                super().start()

    monkeypatch.setattr(threading, "Thread", SyncThread)
    r = client.post(
        "/register",
        data={
            "org_name": "Welcome Ltd",
            "domain": "welcome.com",
            "user_name": "Wel Come",
            "email": "wel@welcome.com",
            "password": "Xyq9$mNpL2!k",
            "password_confirm": "Xyq9$mNpL2!k",
            "country": "NG",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    from app.config import APP_URL

    assert any(f'href="{APP_URL}"' in h and "Welcome to SafeData" in h for h in sent)
