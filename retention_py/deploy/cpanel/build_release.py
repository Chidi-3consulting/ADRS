#!/usr/bin/env python3
"""Build the SafeData cPanel release zip from the committed code.

    python retention_py/deploy/cpanel/build_release.py   # -> dist/safedata-cpanel-<commit>.zip

The zip's top level is the app folder (passenger_wsgi.py, app/, alembic/, ...). Only files
committed to git go in, so .env, test databases and uploaded files never do. Extract it
over /home/USER/safedata_app; the existing .env there is kept.
"""
import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SKIP_PARTS = {"tests", "__pycache__", "node_modules"}


def main() -> int:
    git = ["git", "-C", str(REPO)]
    commit = subprocess.run(git + ["rev-parse", "--short", "HEAD"], check=True,
                            capture_output=True, text=True).stdout.strip()
    data = subprocess.run(git + ["archive", "--format=tar", "HEAD:retention_py"], check=True,
                          capture_output=True).stdout
    out = REPO / "dist" / f"safedata-cpanel-{commit}.zip"
    out.parent.mkdir(exist_ok=True)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(data)) as t, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for m in t.getmembers():
            parts = set(Path(m.name).parts)
            if m.isfile() and not SKIP_PARTS & parts and not m.name.endswith(".db"):
                z.writestr(m.name, t.extractfile(m).read())
                count += 1
    print(f"{out} ({count} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
