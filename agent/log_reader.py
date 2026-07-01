from pathlib import Path

class LogReader:

    def __init__(self, logfile):
        self.logfile = Path(logfile)

    def read(self):

        if not self.logfile.exists():
            return []

        with open(self.logfile, "r", encoding="utf-8") as f:
            return f.readlines()