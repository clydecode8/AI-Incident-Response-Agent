#!/bin/sh
set -e

mkdir -p \
  runtime \
  alerts \
  logs \
  incident-demo/logs \
  incident-demo/metrics

# Create llm_config.json only when it does not already exist
if [ ! -f runtime/llm_config.json ]; then
  cat > runtime/llm_config.json <<'EOF'
{
  "provider": "groq"
}
EOF
fi

# Create services_config.json only when it does not already exist
if [ ! -f runtime/services_config.json ]; then
  cat > runtime/services_config.json <<'EOF'
{
  "monitor_enabled": true,
  "auto_investigator_enabled": true
}
EOF
fi

# Create runtime state files only when missing
if [ ! -f runtime/monitor_status.json ]; then
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