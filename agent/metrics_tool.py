import json
from pathlib import Path

def read_metrics(metrics_path="incident-demo/metrics/metrics.json"):
    path = Path(metrics_path)

    if not path.exists():
        return {"status": "No metrics found"}

    content = path.read_text(encoding="utf-8").strip()

    if not content:
        return {"status": "Metrics file is empty"}

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        return {
            "status": "Invalid metrics JSON",
            "error": str(e),
            "raw_content": content
        }


def summarize_metrics(metrics: dict) -> str:
    if metrics.get("status"):
        return metrics["status"]

    return f"""
        Service: {metrics.get("service")}
        CPU Usage: {metrics.get("cpu_usage")}%
        Memory Usage: {metrics.get("memory_usage")}%
        Latency: {metrics.get("latency_ms")} ms
        Error Rate: {metrics.get("error_rate")}%
        Requests/sec: {metrics.get("requests_per_second")}
        Service Status: {metrics.get("service_status")}
    """