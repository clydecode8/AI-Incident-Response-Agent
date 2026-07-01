import os
from datetime import datetime
from agent.alert_store import create_alert

LOG_SOURCES = {
    "application": "incident-demo/logs/application.log",
    "hadoop": "incident-demo/logs/hadoop.log",
    "linux": "incident-demo/logs/linux.log",
}

ERROR_PATTERNS = {
    "application": [
        "KafkaTimeoutException",
        "NullPointerException",
        "Broker unavailable",
    ],
    "hadoop": [
        "NameNode",
        "DataNode",
        "HDFS",
        "disk failure",
        "connection refused",
        "job failed",
        "timeout",
    ],
    "linux": [
        "permission denied",
        "authentication failure",
        "out of memory",
        "kernel panic",
        "disk full",
        "service failed",
    ],
}


def infer_service(source: str, content: str) -> str:
    text = content.lower()

    if source == "hadoop":
        return "Hadoop Cluster"

    if source == "linux":
        return "Linux Server"

    if "payment" in text or "kafka" in text:
        return "PaymentService"

    if "user" in text or "nullpointerexception" in text:
        return "UserService"

    return "UnknownService"


def detect_log_alert(source: str, last_position: int):
    log_path = LOG_SOURCES[source]

    if not os.path.exists(log_path):
        return None, last_position

    file_size = os.path.getsize(log_path)

    # Important: if logs were cleared/truncated, reset pointer
    if last_position > file_size:
        last_position = 0

    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        f.seek(last_position)
        new_content = f.read()
        new_position = f.tell()

    if not new_content.strip():
        return None, new_position

    for pattern in ERROR_PATTERNS[source]:
        if pattern.lower() in new_content.lower():
            return {
                "severity": "P2",
                "source": f"{source}-monitor",
                "log_source": source,
                "service": infer_service(source, new_content),
                "symptom": f"{pattern} detected in {source} logs",
                "detected_pattern": pattern,
                "timestamp": datetime.now().isoformat(),
                "raw_evidence": new_content[-1500:],
            }, new_position

    return None, new_position


def run_monitor_once(source: str, last_positions: dict):
    last_position = last_positions.get(source, 0)

    alert, new_position = detect_log_alert(source, last_position)

    new_positions = dict(last_positions)
    new_positions[source] = new_position

    return alert, new_positions


def alert_to_text(alert: dict) -> str:
    return f"""
        Source: {alert.get("source")}
        Log Source: {alert.get("log_source")}
        Service: {alert.get("service")}
        Severity: {alert.get("severity")}
        Symptom: {alert.get("symptom")}
        Detected Pattern: {alert.get("detected_pattern")}
        Timestamp: {alert.get("timestamp")}

        Evidence:
        {alert.get("raw_evidence", "")}
    """.strip()

def generate_alert_from_log(source: str, last_positions: dict):
    alert, new_positions = run_monitor_once(source, last_positions)

    if alert:
        create_alert(alert)

    return alert, new_positions