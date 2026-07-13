#!/bin/sh
set -e

mkdir -p \
  runtime \
  alerts \
  logs \
  incident-demo/logs \
  incident-demo/metrics

# Start the background services
python monitor_worker.py >> runtime/monitor-worker.log 2>&1 &
MONITOR_PID=$!

python auto_investigator.py >> runtime/auto-investigator.log 2>&1 &
INVESTIGATOR_PID=$!

cleanup() {
  echo "Stopping background workers..."
  kill "$MONITOR_PID" "$INVESTIGATOR_PID" 2>/dev/null || true
}

trap cleanup TERM INT EXIT

# Zeabur supplies PORT automatically. Streamlit must listen on all interfaces.
exec streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}" \
  --server.headless=true \
  --browser.gatherUsageStats=false