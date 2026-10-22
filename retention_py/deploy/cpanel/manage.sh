#!/bin/bash
# Run a SafeData operations command on cPanel with the app's own virtualenv and .env.
#
#   bash deploy/cpanel/manage.sh create-admin --email admin@3consult-ng.com --org "3Consulting"
#   bash deploy/cpanel/manage.sh migrate
#
# Same virtualenv lookup as cron.sh, so it works without `source .../activate`.
set -euo pipefail
APP_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$APP_ROOT"

if [ ! -f .env ]; then
    echo "No .env in $APP_ROOT — copy deploy/cpanel/env.example to .env and fill it in first." >&2
    exit 1
fi

VENV="$(ls -d "$HOME/virtualenv/${APP_ROOT#"$HOME"/}"/*/ 2>/dev/null | sort -V | tail -1)"
[ -n "$VENV" ] || { echo "No cPanel virtualenv found for $APP_ROOT (create the app in Setup Python App first)" >&2; exit 1; }

# app.cli loads .env itself (app/core/envfile.py), exactly as passenger_wsgi.py does.
exec "${VENV}bin/python" -m app.cli "$@"
