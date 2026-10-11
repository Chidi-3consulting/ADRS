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
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)

    def list_objects_v2(self, Bucket, Prefix):
        import datetime as dt
        return {"Contents": [{"Key": k, "LastModified": dt.datetime(2026, 1, 1)}
                             for k in self.objects if k.startswith(Prefix)]}


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
    db.add(cat); db.commit()
    rec = DataRecord(organization_id=1, category_id=cat.id, record_reference="R1")
    db.add(rec); db.commit()
    auth_user.email_verified_at = auth_user.created_at; db.commit()
    client.cookies.set("SafeData_session", serializer.dumps(build_session_data(auth_user, db.get(Organization, 1))))
    pdf = b"%PDF-1.4\n%test\n"
    r = client.post(f"/attachments/upload/{rec.id}", files={"file": ("e.pdf", pdf, "application/pdf")},
                    follow_redirects=False)
    assert r.status_code == 303
    att = db.query(Attachment).one()
    assert att.stored_filename.startswith("orgs/1/attachments/")
    assert storage.get(att.stored_filename) == pdf
    d = client.get(f"/attachments/download/{att.id}")
    assert d.status_code == 200 and d.content == pdf
