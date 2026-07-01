from collections import Counter

class LogAnalyzer:

    def __init__(self, logs):
        self.logs = logs

    def count_levels(self):
        return Counter(log.level for log in self.logs)

    def get_errors(self):
        return [log for log in self.logs if log.level == "ERROR"]

    def most_common_exception(self):

        exceptions = [log.exception for log in self.logs if log.exception]

        if not exceptions:
            return None

        return Counter(exceptions).most_common(1)[0]