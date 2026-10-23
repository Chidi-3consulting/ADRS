"""Every link a signed-in user can click must land on a page, not a 404.

Live users hit 404s from the sidebar (/docs), the login page
(/forgot-password) and onboarding notifications (/settings/team).
"""

import re
from argparse import Namespace

from app.auth import hash_password
from app.models import User

PW = "Xyq9$mNpL2!kA"


def _admin(db, name, email):
    db.add(
        User(
            organization_id=1,
            name=name,
            email=email,
            password_hash=hash_password(PW),
            role="admin",
            is_active=True,
            must_change_password=False,
        )
    )
    db.commit()


def _login(client, email):
    r = client.post("/login", data={"email": email, "password": PW}, follow_redirects=False)
    assert r.status_code == 303


def test_every_reachable_link_resolves(client, db):
    _admin(db, "Second Admin", "second@test.local")
    _login(client, "second@test.local")
    seen, queue, bad = set(), ["/dashboard", "/login"], {}
    while queue and len(seen) < 200:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        r = client.get(url, follow_redirects=True)
        if r.status_code >= 400:
            bad[url] = r.status_code
            continue
        for href in re.findall(r'href="(/[^"#?]*)', r.text):
            if href not in seen and not href.startswith(("/static", "/logout")):
                queue.append(href)
    assert bad == {}, f"links that do not resolve: {bad}"


def test_login_page_forgot_password_link_works(client):
    page = client.get("/login").text
    link = re.search(r'href="(/forgot[^"]*)"', page).group(1)
    assert client.get(link).status_code == 200


def test_onboarding_links_exist(client, db):
    from app.routes.app_pages import router  # noqa: F401
    import app.engine as engine

    src = open(engine.__file__, encoding="utf-8").read()
    assert "/settings/team" not in src
    _admin(db, "Second Admin", "second@test.local")
    _login(client, "second@test.local")
    assert client.get("/users").status_code == 200


def test_header_shows_the_signed_in_admin_not_another(client, db):
    _admin(db, "Main Admin", "main@test.local")
    _admin(db, "Second Admin", "second@test.local")
    _login(client, "second@test.local")
    page = client.get("/dashboard").text
    assert "Second Admin" in page and "Main Admin" not in page


def test_create_admin_rerun_updates_the_name(client, db, monkeypatch):
    from app import cli

    monkeypatch.setenv("SAFEDATA_AUTO_MIGRATE", "0")
    base = dict(org="Test Organisation", country="NG", password=PW)
    assert cli.cmd_create_admin(Namespace(email="boss@test.local", name="Old Name", **base)) == 0
    assert cli.cmd_create_admin(Namespace(email="boss@test.local", name="New Name", **base)) == 0
    db.expire_all()
    assert db.query(User).filter(User.email == "boss@test.local").one().name == "New Name"
    # re-running without --name must not wipe the name
    assert cli.cmd_create_admin(Namespace(email="boss@test.local", name=None, **base)) == 0
    db.expire_all()
    assert db.query(User).filter(User.email == "boss@test.local").one().name == "New Name"


def test_dsar_module_is_gone_from_code_templates_and_models():
    """SafeData does not handle data subject access requests. Old migrations keep their history."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    hits = [
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.suffix in {".py", ".html", ".js"} and "dsar" in p.read_text(encoding="utf-8", errors="ignore").lower()
    ]
    assert hits == [], f"DSAR references remain in: {hits}"
