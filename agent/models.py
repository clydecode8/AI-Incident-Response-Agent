from dataclasses import dataclass

@dataclass
class LogEntry:
    timestamp: str
    level: str
    service: str
    message: str
    exception: str = ""
    cause: str = ""