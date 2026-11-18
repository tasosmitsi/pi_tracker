"""Logging for a job that keeps failing, without flooding the log."""


class FailureLog:
    """The traceback once per distinct error; while it repeats, one line after 10, 100, 1000... in a row."""

    def __init__(self, name, logger):
        self.name = name
        self._log = logger
        self._count = 0
        self._last_error = None
        self._next_report = 10

    def failed(self, exc):
        error = "%s: %s" % (type(exc).__name__, exc)
        if error != self._last_error:
            self._log.error("%s failed, it will run again", self.name, exc_info=exc)
            self._last_error = error
            self._count = 1
            self._next_report = 10
        else:
            self._count += 1
            if self._count >= self._next_report:
                self._log.error("%s has failed %d times in a row: %s", self.name, self._count, error)
                self._next_report *= 10

    def succeeded(self):
        if self._count:
            self._log.info("%s works again after %d failures", self.name, self._count)
            self._count = 0
            self._last_error = None
