#!/bin/bash
# SafeData background jobs for cPanel (no long-running worker on shared hosting).
# cPanel -> Cron Jobs, every 5 minutes:
#   */5 * * * * /bin/bash /home/CPANELUSER/safedata_app/retention_py/deploy/cpanel/cron.sh >> /home/CPANELUSER/safedata_storage/logs/cron.log 2>&1
set -euo pipefail
APP_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$APP_ROOT"
# Shared .env with the web app
set -a; [ -f .env ] && . ./.env; set +a
# Same as passenger_wsgi.py: cPanel databases are SQL_ASCII, so force a UTF-8 client.
export PGCLIENTENCODING="${PGCLIENTENCODING:-UTF8}"
# The virtualenv cPanel created for this app: ~/virtualenv/<app root, relative to $HOME>/<python version>/
# (relative path, not basename, so a nested root like safedata_app/retention_py also works)
VENV="$(ls -d "$HOME/virtualenv/${APP_ROOT#"$HOME"/}"/*/ 2>/dev/null | sort -V | tail -1)"
[ -n "$VENV" ] || { echo "No cPanel virtualenv found for $APP_ROOT (create the app in Setup Python App first)"; exit 1; }
exec "${VENV}bin/python" -m app.worker --once
