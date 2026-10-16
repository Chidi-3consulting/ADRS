import os
import signal
import socket
import sys

from app.config import IS_PRODUCTION
from app.core.logging import configure_logging
from app.database import SessionLocal
from app.worker.jobs import JOBS
from app.worker.runner import run_forever, run_once

_stop = False


def _handle(_sig, _frm):
    global _stop
    _stop = True


if __name__ == "__main__":
    configure_logging(json_output=IS_PRODUCTION)
    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    holder = f"{socket.gethostname()}:{os.getpid()}"
    if "--once" in sys.argv[1:]:
        # cron mode: run whatever is due, then exit (shared hosting has no daemons)
        results = run_once(SessionLocal, holder, JOBS)
        print(" ".join(f"{k}={v}" for k, v in results.items()))
        sys.exit(1 if "failed" in results.values() or "error" in results.values() else 0)
    run_forever(SessionLocal, holder, JOBS, stop=lambda: _stop)
