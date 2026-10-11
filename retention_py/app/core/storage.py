"""Object storage: local filesystem (dev) or S3-compatible (Cloudflare R2 / DO Spaces)."""

from __future__ import annotations

import functools
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _check_key(key: str) -> str:
    if not key or not _SAFE_KEY.match(key) or ".." in key.split("/") or "\\" in key:
        raise ValueError(f"unsafe storage key: {key!r}")
    return key


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def list(self, prefix: str) -> list[tuple[str, datetime]]: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / _check_key(key)).resolve()
        if self.root not in p.parents:
            raise ValueError(f"unsafe storage key: {key!r}")
        return p

    def put(self, key, data, content_type):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key):
        return self._path(key).read_bytes()

    def delete(self, key):
        self._path(key).unlink(missing_ok=True)

    def list(self, prefix):
        base = self.root
        out = []
        for f in base.rglob("*"):
            if f.is_file():
                k = f.relative_to(base).as_posix()
                if k.startswith(prefix):
                    out.append((k, datetime.fromtimestamp(f.stat().st_mtime, UTC).replace(tzinfo=None)))
        return sorted(out)


class S3Storage:
    def __init__(self, bucket: str, client):
        self.bucket, self.client = bucket, client

    def put(self, key, data, content_type):
        self.client.put_object(Bucket=self.bucket, Key=_check_key(key), Body=data, ContentType=content_type)

    def get(self, key):
        from botocore.exceptions import ClientError

        try:
            return self.client.get_object(Bucket=self.bucket, Key=_check_key(key))["Body"].read()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound"):
                raise FileNotFoundError(key) from exc
            raise

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=_check_key(key))

    def list(self, prefix):
        resp = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
        return sorted((o["Key"], o["LastModified"].replace(tzinfo=None)) for o in resp.get("Contents", []))


@functools.lru_cache(maxsize=4)
def _s3_client(endpoint_url, region_name, access_key_id, secret_access_key):
    """One client per process per config (boto3 default-session client creation is not thread-safe)."""
    import boto3

    return boto3.session.Session().client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region_name,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )


def get_storage() -> Storage:
    from app import config

    if config.STORAGE_BACKEND == "s3":
        client = _s3_client(
            config.S3_ENDPOINT_URL or None,
            config.S3_REGION,
            config.S3_ACCESS_KEY_ID,
            config.S3_SECRET_ACCESS_KEY,
        )
        return S3Storage(config.S3_BUCKET, client)
    return LocalStorage(config.STORAGE_LOCAL_ROOT)
