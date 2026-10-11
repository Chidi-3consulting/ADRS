def test_healthz_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["database"] == "ok"


def test_healthz_degraded_when_db_down(client, monkeypatch):
    import main

    def broken():
        raise RuntimeError("db down")
    monkeypatch.setattr(main, "_db_ping", broken)
    r = client.get("/healthz")
    assert r.status_code == 503
    assert r.json() == {"status": "degraded", "database": "error"}
