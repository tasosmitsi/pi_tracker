import threading
import logging
import signal
import time

import gi
gi.require_version('GLib', '2.0')
from gi.repository import GLib

from pi_tracker.failure_log import FailureLog

log = logging.getLogger(__name__)

def run_with_main_loop(work, stop_timeout_s=15):
    """Run work(stop_event) in a thread while the GLib main loop runs; return the exit code.

    SIGINT (Ctrl+C) and SIGTERM (systemctl stop) set stop_event, and the loop ends
    when work returns. A second signal, or work still busy stop_timeout_s after the
    first, ends it without waiting. The exit code is 1 when work failed, ended by
    itself or had to be abandoned, so systemd can restart the app; 0 after a clean stop.
    """
    loop = GLib.MainLoop()
    stop_event = threading.Event()
    failed = []        # appended to by the worker thread or by give_up()
    timeouts = []

    def give_up(reason):
        log.error("%s, exiting without waiting for the worker", reason)
        failed.append(reason)
        loop.quit()
        return False   # a one-off GLib timeout

    def on_signal(signum, frame):
        name = signal.Signals(signum).name
        if stop_event.is_set():
            give_up("%s again" % name)
            return
        log.info("%s received, stopping", name)
        stop_event.set()
        timeouts.append(GLib.timeout_add(int(stop_timeout_s * 1000), give_up,
                                         "Still stopping after %s s" % stop_timeout_s))

    def worker():
        try:
            work(stop_event)
        except BaseException:
            log.exception("The worker failed, exiting")
            failed.append('failed')
        else:
            if not stop_event.is_set():
                log.error("The worker ended without being asked to, exiting")
                failed.append('ended')
        finally:
            GLib.idle_add(loop.quit)

    previous = {signum: signal.signal(signum, on_signal) for signum in (signal.SIGINT, signal.SIGTERM)}
    thread = threading.Thread(target=worker, name='worker', daemon=True)  # daemon: a stuck one can't block the exit
    try:
        thread.start()
        loop.run()
        if not failed:
            thread.join(1)
    finally:
        for source in timeouts:
            if GLib.MainContext.default().find_source_by_id(source):  # it's gone once it has fired
                GLib.source_remove(source)
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return 1 if failed or thread.is_alive() else 0


class StoppableRestartableGiThread:
    def __init__(self, target, args=(), kwargs=None):
        if kwargs is None:
            kwargs = {}
        self.target = target
        self.args = args
        self.kwargs = kwargs
        self.thread = None
        self._failures = FailureLog("Thread %s" % target.__name__, log)


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
        try:
            keep_going = self.target(*self.args, **self.kwargs)
        except Exception as e:
            self._failures.failed(e)
            return True

        self._failures.succeeded()
        if not keep_going:
            # GLib removes the timer itself when the callback returns a false value
            self.thread = None
        return keep_going
