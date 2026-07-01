import time
import json
from agent.alert_store import list_alerts_by_status, update_alert_status
from agent.incident_monitor import alert_to_text
from agent.react_agent import run_react_agent

print("Auto investigator started. Currently Watching NEW alerts...")

def get_provider():
    try:
        with open("runtime/llm_config.json") as f:
            return json.load(f).get("provider", "groq")
    except:
        return "groq"
    
while True:
    new_alerts = list_alerts_by_status("NEW")

    for alert in new_alerts:
        alert_id = alert["id"]

        print(f"Investigating alert {alert_id}...")

        update_alert_status(alert_id, "INVESTIGATING")

        try:
            alert_text = alert_to_text(alert)
            report = run_react_agent(alert_text, get_provider())

            update_alert_status(
                alert_id,
                "RESOLVED",
                report=report
            )

            print(f"Resolved alert {alert_id}")

        except Exception as e:
            update_alert_status(
                alert_id,
                "FAILED",
                report={
                    "trace": [],
                    "report": f"Auto investigation failed: {e}"
                }
            )

            print(f"Failed alert {alert_id}: {e}")

    time.sleep(3)