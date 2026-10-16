#!/bin/bash
# SafeData background jobs for cPanel (no long-running worker on shared hosting).
# cPanel -> Cron Jobs, every 5 minutes:
#   */5 * * * * /bin/bash /home/CPANELUSER/safedata_app/deploy/cpanel/cron.sh >> /home/CPANELUSER/safedata_storage/logs/cron.log 2>&1
set -euo pipefail
APP_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$APP_ROOT"
# Shared .env with the web app
set -a; [ -f .env ] && . ./.env; set +a
# The virtualenv cPanel created for this app: ~/virtualenv/<app root name>/<python version>/
VENV="$(ls -d "$HOME"/virtualenv/"$(basename "$APP_ROOT")"/*/ 2>/dev/null | sort -V | tail -1)"
exec "${VENV}bin/python" -m app.worker --once
