import os
import json
import time
from datetime import datetime

from agent.incident_monitor import run_monitor_once, LOG_SOURCES
from agent.alert_store import create_alert

STATUS_PATH = "runtime/monitor_status.json"
LOG_SOURCES_LIST = ["application", "hadoop", "linux"]
os.makedirs("runtime", exist_ok=True)

def get_initial_positions():
    positions = {}

    for source, path in LOG_SOURCES.items():
        if os.path.exists(path):
            positions[source] = os.path.getsize(path)
        else:
            positions[source] = 0

    return positions


def write_status(last_log_positions):
    os.makedirs("alerts", exist_ok=True)

    status = {
        "status": "RUNNING",
        "updated_at": datetime.now().isoformat(),
        "watching": LOG_SOURCES_LIST,
        "last_log_positions": last_log_positions,
    }

    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)


last_log_positions = get_initial_positions()

print("Background monitor worker started.")
print("Watching application logs...")

while True:
    write_status(last_log_positions)

    for source in LOG_SOURCES_LIST:
        alert, new_positions = run_monitor_once(source, last_log_positions)
        last_log_positions = new_positions

        if alert:
            alert_id = create_alert(alert)
            print(
                f"New alert created: {alert_id} | "
                f"{alert.get('service')} | {alert.get('symptom')}"
            )

    time.sleep(3)