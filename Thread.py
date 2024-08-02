import threading
import time

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
            print("Thread is already running")
        return self

    def stop(self):
        if self.thread is not None and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()
        else:
            print("Thread is already stopped")
        return self

    def is_running(self):
        return self.thread is not None and self.thread.is_alive()