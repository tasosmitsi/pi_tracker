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


    def start(self, delay):
        if self.thread is None:
            self.thread = GLib.timeout_add_seconds(delay, lambda: (self.target(*self.args, **self.kwargs)))
            
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