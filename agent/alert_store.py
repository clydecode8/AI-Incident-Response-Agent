import os
import json
import uuid
from datetime import datetime

ALERT_DIR = "alerts"

os.makedirs(ALERT_DIR, exist_ok=True)

def get_alert(alert_id: str):
    path = os.path.join(ALERT_DIR, f"{alert_id}.json")

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_alerts_by_status(status: str):
    return [
        alert for alert in list_alerts()
        if alert.get("status") == status
    ]

def create_alert(alert: dict) -> str:
    alert_id = str(uuid.uuid4())[:8]

    alert["id"] = alert_id
    alert["status"] = "NEW"
    alert["created_at"] = datetime.now().isoformat()

    path = os.path.join(ALERT_DIR, f"{alert_id}.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(alert, f, indent=2)

    return alert_id

def list_alerts():
    alerts = []

    for file in os.listdir(ALERT_DIR):
        if not file.endswith(".json"):
            continue

        # Skip non-alert metadata/status files
        if file == "monitor_status.json":
            continue

        path = os.path.join(ALERT_DIR, file)

        with open(path, "r", encoding="utf-8") as f:
            alert = json.load(f)

        # Skip anything that is not a real alert
        if not alert.get("id") or not alert.get("service") or not alert.get("symptom"):
            continue

        alerts.append(alert)

    return sorted(alerts, key=lambda x: x.get("created_at", ""), reverse=True)

def update_alert_status(alert_id: str, status: str, report=None):
    path = os.path.join(ALERT_DIR, f"{alert_id}.json")

    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        alert = json.load(f)

    alert["status"] = status
    alert["updated_at"] = datetime.now().isoformat()

    if report is not None:
        alert["report"] = report

    with open(path, "w", encoding="utf-8") as f:
        json.dump(alert, f, indent=2)

def clear_alerts():
    for file in os.listdir(ALERT_DIR):
        if not file.endswith(".json"):
            continue

        # Do not delete monitor worker heartbeat/status file
        if file == "monitor_status.json":
            continue

        os.remove(os.path.join(ALERT_DIR, file))