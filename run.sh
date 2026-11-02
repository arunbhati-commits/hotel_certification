#!/usr/bin/env bash
# Start the Tripjack Certification V3 Hotel checker and open it in the browser.
#   ./run.sh                 -> http://127.0.0.1:8765
#   ./run.sh 9000            -> use another port
#   HOST=0.0.0.0 ./run.sh    -> let other machines on the network open it
set -euo pipefail

cd "$(dirname "$0")"

PORT="${1:-${PORT:-8765}}"
HOST="${HOST:-127.0.0.1}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not installed. Install Python 3.10+ from https://www.python.org/downloads/ and run again."
  exit 1
fi

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "Python 3.10 or newer is needed (found $(python3 --version 2>&1))."
  exit 1
fi

# Stop an older copy of the checker that is still holding the port
OLD_PIDS="$(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
if [ -n "$OLD_PIDS" ]; then
  if ps -o command= -p $OLD_PIDS | grep -q audit_ui_server.py; then
    echo "Stopping the checker already running on port $PORT ..."
    kill $OLD_PIDS 2>/dev/null || true
    sleep 1
  else
    echo "Port $PORT is used by another program. Run with a different port, e.g. ./run.sh 9000"
    exit 1
  fi
fi

echo "Starting Tripjack Certification V3 Hotel checker on http://$HOST:$PORT"
echo "Press Ctrl+C to stop."
exec python3 audit_ui_server.py --host "$HOST" --port "$PORT"
