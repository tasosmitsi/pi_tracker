import threading
import time

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib

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
            print(f"Thread {self.target.__name__} is already running.")
        return self

    def stop(self):
        if self.thread is not None and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()
            print(f"Thread {self.target.__name__} is now stopped.")
        else:
            print(f"Thread {self.target.__name__} is already stopped.")
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
            print(f"Thread {self.target.__name__} is already running.")
        return self

    def stop(self):
        if self.thread is not None:
            GLib.source_remove(self.thread)
            self.thread = None
            print(f"Thread {self.target.__name__} is now stopped.")
            
        else:
            print(f"Thread {self.target.__name__} is already stopped.")
        return self

    def is_running(self):
        return self.thread is not None