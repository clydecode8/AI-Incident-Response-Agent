import re
from agent.models import LogEntry

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}T[\d:.]+)\s+"
    r"(?P<level>INFO|ERROR|WARN)\s+"
    r"\[(?P<thread>.*?)\]\s+"
    r"(?P<classname>[\w.]+)\s+-\s+"
    r"(?P<message>.*)$"
)

def parse_logs(lines):
    logs = []

    for line in lines:
        line = line.strip()
        match = LOG_PATTERN.match(line)

        if not match:
            print("SKIPPED:", line)
            continue

        classname = match.group("classname")
        service = classname.split(".")[-1]

        logs.append(
            LogEntry(
                timestamp=match.group("timestamp"),
                level=match.group("level"),
                service=service,
                message=match.group("message"),
                exception=match.group("message") if "Exception" in match.group("message") else "",
                cause=""
            )
        )

    return logs