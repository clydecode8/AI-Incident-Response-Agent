#!/bin/sh
set -e

mkdir -p \
  runtime \
  alerts \
  logs \
  incident-demo/logs \
  incident-demo/metrics

# Repair llm_config.json if missing or invalid
if ! python -m json.tool runtime/llm_config.json >/dev/null 2>&1; then
  echo "Creating or repairing runtime/llm_config.json"

  cat > runtime/llm_config.json <<'EOF'
{
  "provider": "groq"
}
EOF
fi

# Repair services_config.json if missing or invalid
if ! python -m json.tool runtime/services_config.json >/dev/null 2>&1; then
  echo "Creating or repairing runtime/services_config.json"

  cat > runtime/services_config.json <<'EOF'
{
  "monitor_enabled": true,
  "auto_investigator_enabled": true
}
EOF
fi

# Repair monitor_status.json if missing or invalid
if ! python -m json.tool runtime/monitor_status.json >/dev/null 2>&1; then
  printf '{}\n' > runtime/monitor_status.json
fi

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

# Zeabur supplies PORT automatically
exec streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}" \
  --server.headless=true \
  --browser.gatherUsageStats=false