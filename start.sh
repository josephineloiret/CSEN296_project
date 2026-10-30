#!/bin/sh
set -eu
WORKSPACE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$WORKSPACE_DIR"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.lock.txt
fi
if .venv/bin/python -c 'import json, urllib.request
try:
    response = json.load(urllib.request.urlopen("http://localhost:8000/health", timeout=1))
    raise SystemExit(0 if response.get("application") == "refundguard" else 1)
except OSError:
    raise SystemExit(1)' 2>/dev/null; then
  .venv/bin/python manage.py open
  exit 0
fi
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
REFUNDGUARD_SERVER_PID=$!
trap 'kill "$REFUNDGUARD_SERVER_PID" 2>/dev/null || true' EXIT INT TERM
.venv/bin/python -c 'import json, time, urllib.request
for attempt in range(40):
    try:
        response = json.load(urllib.request.urlopen("http://localhost:8000/health", timeout=1))
        if response.get("application") == "refundguard":
            break
    except OSError:
        time.sleep(0.25)
else:
    raise SystemExit("The local server did not start. Check the terminal output.")'
.venv/bin/python manage.py open
wait "$REFUNDGUARD_SERVER_PID"
