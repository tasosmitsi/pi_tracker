import threading
import logging
import time

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib

log = logging.getLogger(__name__)

class StoppableRestartableThread:
    def __init__(self, target, args=(), kwargs=None):
        if kwargs is None:
            kwargs = {}
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.stop_event.clear()
            self.kwargs['stop_event'] = self.stop_event
            self.thread = threading.Thread(target=self.target, args=self.args, kwargs=self.kwargs)
            self.thread.start()
        else:
            log.warning("Thread %s is already running.", self.target.__name__)
        return self

    def stop(self):
        if self.thread is not None and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()
            log.info("Thread %s is now stopped.", self.target.__name__)
        else:
            log.warning("Thread %s is already stopped.", self.target.__name__)
        return self

    def is_running(self):
        return self.thread is not None and self.thread.is_alive()


class StoppableRestartableGiThread:
    def __init__(self, target, args=(), kwargs=None):
        if kwargs is None:
            kwargs = {}
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.thread = None
        self._failures = 0
        self._last_error = None
        self._next_report = 10


    def start(self, delay):
        if self.thread is None:
            self.thread = GLib.timeout_add_seconds(delay, self._run)
            
        else:
            log.warning("Thread %s is already running.", self.target.__name__)
        return self

    def stop(self):
        if self.thread is not None:
            GLib.source_remove(self.thread)
            self.thread = None
            log.info("Thread %s is now stopped.", self.target.__name__)
            
        else:
            log.warning("Thread %s is already stopped.", self.target.__name__)
        return self

    def is_running(self):
        return self.thread is not None

    def _run(self):
        # GLib drops a timer for good when its callback raises, so a single failed
        # read would stop it. Log the error and keep the timer running instead.
        # The traceback is logged once per distinct error; while the same error
        # repeats, only a short line after 10, 100, 1000... failures in a row.
        name = self.target.__name__
        try:
            keep_going = self.target(*self.args, **self.kwargs)
        except Exception as e:
            error = "%s: %s" % (type(e).__name__, e)
            if error != self._last_error:
                log.exception("Thread %s failed, it will run again", name)
                self._last_error = error
                self._failures = 1
                self._next_report = 10
            else:
                self._failures += 1
                if self._failures >= self._next_report:
                    log.error("Thread %s has failed %d times in a row: %s", name, self._failures, error)
                    self._next_report *= 10
            return True

        if self._failures:
            log.info("Thread %s works again after %d failures", name, self._failures)
            self._failures = 0
            self._last_error = None
        if not keep_going:
            # GLib removes the timer itself when the callback returns a false value
            self.thread = None
        return keep_going
