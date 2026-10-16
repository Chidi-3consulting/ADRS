# retention_py/tests/test_foundation_storage.py
import io

import pytest
from cryptography.fernet import Fernet

from app.core.storage import LocalStorage, S3Storage


def test_local_storage_roundtrip(tmp_path):
    s = LocalStorage(str(tmp_path))
    s.put("orgs/1/attachments/a.pdf", b"%PDF-1.4 x", "application/pdf")
    assert s.get("orgs/1/attachments/a.pdf") == b"%PDF-1.4 x"
    assert [k for k, _ in s.list("orgs/1/")] == ["orgs/1/attachments/a.pdf"]
    s.delete("orgs/1/attachments/a.pdf")
    with pytest.raises(FileNotFoundError):
        s.get("orgs/1/attachments/a.pdf")


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "orgs/../../x", "C:\\x", ""])
def test_local_storage_rejects_traversal(tmp_path, bad):
    with pytest.raises(ValueError):
        LocalStorage(str(tmp_path)).put(bad, b"x", "text/plain")


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            from botocore.exceptions import ClientError

            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "x"}}, "GetObject")
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def list_objects_v2(self, Bucket, Prefix):
        import datetime as dt

        return {
            "Contents": [
                {"Key": k, "LastModified": dt.datetime(2026, 1, 1)} for k in self.objects if k.startswith(Prefix)
            ]
        }


def test_s3_storage_roundtrip():
    fake = FakeS3()
    s = S3Storage("bucket", fake)
    s.put("backups/a.enc", b"data", "application/octet-stream")
    assert s.get("backups/a.enc") == b"data"
    assert [k for k, _ in s.list("backups/")] == ["backups/a.enc"]


def test_backup_is_encrypted_and_restorable(db, tmp_path, monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr("app.backups.BACKUP_ENCRYPTION_KEY", key)
    from app.backups import backup_database

    storage = LocalStorage(str(tmp_path))
    result = backup_database(db, storage)
    assert result["status"] == "success", result
    blob = storage.get(result["key"])
    assert b"CREATE TABLE" not in blob  # encrypted at rest
    decrypted = Fernet(key.encode()).decrypt(blob)
    if db.get_bind().dialect.name == "sqlite":
        assert b"CREATE TABLE" in decrypted
    else:
        assert decrypted.startswith(b"PGDMP")


def test_attachment_upload_and_download_use_storage(client, db, auth_user, tmp_path, monkeypatch):
    from app.auth import build_session_data, serializer
    from app.models import Attachment, DataCategory, DataRecord, Organization

    storage = LocalStorage(str(tmp_path))
    monkeypatch.setattr("app.routes.records.get_storage", lambda: storage)
    cat = DataCategory(organization_id=1, name="C", retention_period_days=30)
    db.add(cat)
    db.commit()
    rec = DataRecord(organization_id=1, category_id=cat.id, record_reference="R1")
    db.add(rec)
    db.commit()
    auth_user.email_verified_at = auth_user.created_at
    db.commit()
    client.cookies.set("SafeData_session", serializer.dumps(build_session_data(auth_user, db.get(Organization, 1))))
    pdf = b"%PDF-1.4\n%test\n"
    r = client.post(
        f"/attachments/upload/{rec.id}", files={"file": ("e.pdf", pdf, "application/pdf")}, follow_redirects=False
    )
    assert r.status_code == 303
    att = db.query(Attachment).one()
    assert att.stored_filename.startswith("orgs/1/attachments/")
    assert storage.get(att.stored_filename) == pdf
    d = client.get(f"/attachments/download/{att.id}")
    assert d.status_code == 200 and d.content == pdf


def test_s3_get_missing_vs_error():
    from botocore.exceptions import ClientError

    class Fake:
        code = "NoSuchKey"

        def get_object(self, Bucket, Key):
            raise ClientError({"Error": {"Code": self.code, "Message": "x"}}, "GetObject")

    f = Fake()
    s = S3Storage("b", f)
    with pytest.raises(FileNotFoundError):
        s.get("a/b.txt")
    f.code = "AccessDenied"
    with pytest.raises(ClientError):
        s.get("a/b.txt")


def test_pg_dump_command_keeps_password_out_of_argv():
    from sqlalchemy.engine import make_url

    from app.backups import _pg_dump_command

    cmd, env = _pg_dump_command(make_url("postgresql+psycopg2://u:SECRETPW@h:5432/db"))
    assert "SECRETPW" not in " ".join(cmd)
    assert env["PGPASSWORD"] == "SECRETPW"
    assert any("h:5432/db" in a for a in cmd)


def _pg_session(db, monkeypatch, exc):
    from sqlalchemy.engine import make_url

    from app import backups

    class Dialect:
        name = "postgresql"

    class Eng:
        dialect = Dialect()
        url = make_url("postgresql+psycopg2://u:SECRETPW@h/db")

    class Wrap:
        def __getattr__(self, n):
            return getattr(db, n)

        def get_bind(self):
            return Eng()

    def boom(*a, **k):
        raise exc

    monkeypatch.setattr(backups.subprocess, "run", boom)
    return Wrap()


def test_pg_dump_failure_does_not_leak_password(db, tmp_path, monkeypatch):
    import subprocess

    from app.backups import backup_database
    from app.models import BackupLog

    exc = subprocess.CalledProcessError(
        1, ["pg_dump", "postgresql://u:SECRETPW@h/db"], stderr=b"FATAL: password authentication failed"
    )
    result = backup_database(_pg_session(db, monkeypatch, exc), LocalStorage(str(tmp_path)))
    assert result["status"] == "failed"
    assert "SECRETPW" not in result["message"] and "password authentication failed" in result["message"]
    row = db.query(BackupLog).filter(BackupLog.status == "failed").order_by(BackupLog.id.desc()).first()
    assert "SECRETPW" not in row.message and "password authentication failed" in row.message


def test_pg_dump_timeout_does_not_leak_command(db, tmp_path, monkeypatch):
    import subprocess

    from app.backups import backup_database

    exc = subprocess.TimeoutExpired(["pg_dump", "postgresql://u:SECRETPW@h/db"], 1800)
    result = backup_database(_pg_session(db, monkeypatch, exc), LocalStorage(str(tmp_path)))
    assert "SECRETPW" not in result["message"] and "timed out" in result["message"]


def _import_config(**env):
    import os
    import subprocess
    import sys

    base = {k: v for k, v in os.environ.items() if not k.startswith(("S3_", "STORAGE_"))}
    base.update(
        {
            "APP_ENV": "production",
            "SECRET_KEY": "x" * 64,
            "BACKUP_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "DATABASE_URL": "postgresql://u:p@localhost/db",
        }
    )
    base.update(env)
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", "import app.config"],
        env=base,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )


def test_production_requires_s3_storage():
    r = _import_config()
    assert r.returncode != 0 and "STORAGE_BACKEND" in r.stderr
    r = _import_config(STORAGE_BACKEND="S3", S3_BUCKET="b", S3_ACCESS_KEY_ID="k", S3_SECRET_ACCESS_KEY="s")  # noqa: S106
    assert r.returncode == 0, r.stderr


def test_production_local_storage_requires_explicit_persistent_opt_in(tmp_path):
    r = _import_config(STORAGE_BACKEND="local")
    assert r.returncode != 0 and "STORAGE_BACKEND" in r.stderr
    r = _import_config(STORAGE_BACKEND="local", STORAGE_LOCAL_PERSISTENT="1")
    assert r.returncode != 0 and "STORAGE_LOCAL_ROOT" in r.stderr
    r = _import_config(STORAGE_BACKEND="local", STORAGE_LOCAL_PERSISTENT="1", STORAGE_LOCAL_ROOT=str(tmp_path))
    assert r.returncode == 0, r.stderr


def test_download_non_latin_filename(client, db, auth_user, tmp_path, monkeypatch):
    from app.auth import build_session_data, serializer
    from app.models import Attachment, DataCategory, DataRecord, Organization

    storage = LocalStorage(str(tmp_path))
    monkeypatch.setattr("app.routes.records.get_storage", lambda: storage)
    cat = DataCategory(organization_id=1, name="C", retention_period_days=30)
    db.add(cat)
    db.commit()
    rec = DataRecord(organization_id=1, category_id=cat.id, record_reference="R1")
    db.add(rec)
    db.commit()
    auth_user.email_verified_at = auth_user.created_at
    db.commit()
    client.cookies.set("SafeData_session", serializer.dumps(build_session_data(auth_user, db.get(Organization, 1))))
    pdf = b"%PDF-1.4\n%test\n"
    r = client.post(
        f"/attachments/upload/{rec.id}", files={"file": ("报告.pdf", pdf, "application/pdf")}, follow_redirects=False
    )
    assert r.status_code == 303
    att = db.query(Attachment).one()
    d = client.get(f"/attachments/download/{att.id}")
    assert d.status_code == 200 and d.content == pdf
    assert "filename*=UTF-8''%E6%8A%A5%E5%91%8A.pdf" in d.headers["content-disposition"]
